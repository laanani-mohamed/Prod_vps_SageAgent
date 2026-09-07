"""
api/referentiel/router.py — Routeur FastAPI pour le module Référentiel.

Routes legacy (rétro-compatibilité) :
  POST /api/referentiel/articles          → ReferentielRequest
  POST /api/referentiel/clients           → ReferentielRequest (alias vers /comptes-tiers)
  POST /api/referentiel/depots            → ReferentielRequest

Nouvelles routes v2 (schémas spécifiques par ressource) :
  POST /api/referentiel/comptes-tiers     → ComptesTiersRequest
  POST /api/referentiel/collaborateurs    → CollaborateurRequest 
  POST /api/referentiel/articles/detail   → ArticleDetailRequest (avec stock/lots)
  POST /api/referentiel/familles          → FamilleRequest
  POST /api/referentiel/lots-series       → LotSerieRequest
  POST /api/referentiel/documents-entete  → DocEnteteRequest
  POST /api/referentiel/documents-ligne   → DocLigneRequest
  POST /api/referentiel/stock-depot       → StockDepotRequest

Route utilitaire :
  GET  /api/referentiel/types-tiers       → Dictionnaire CT_Type (statique)
  GET  /api/referentiel/types-documents   → Dictionnaire DO_Type (statique)
"""
import logging
from fastapi import APIRouter, HTTPException, Request, Depends

from api.auth.dependencies import require_role
from api.auth.schemas import TokenData
from api._base_router import secured_handle

from api.referentiel.schemas import (
    ReferentielResponse,
    ComptesTiersRequest, CollaborateurRequest, ArticleDetailRequest,
    FamilleRequest, LotSerieRequest, DocEnteteRequest,
    DocLigneRequest, StockDepotRequest, ReglementRequest,
)
from api.referentiel.service import get_specific

logger = logging.getLogger("api.referentiel.router")
router = APIRouter(prefix="/api/referentiel", tags=["Référentiel"])


# ===========================================================================
# ROUTES NOUVELLES v2
# ===========================================================================

@router.post(
    "/comptes-tiers",
    response_model=ReferentielResponse,
    summary="Comptes tiers enrichi (clients, fournisseurs, salariés)",
    description="""
Recherche complète dans **F_COMPTET** avec tous les filtres disponibles.

**Paramètres clés** :
- `ct_type` : `[0]`=clients, `[1]`=fournisseurs, `[0,1]`=les deux
- `ct_ville` : recherche partielle (ex: `"casa"` → Casablanca)
- `ct_identifiant` : numéro ICE exact
- `co_no_representant` : filtrer par vendeur attitré
- `montant_regle_unpaid` : uniquement les comptes avec encours

**Source** : `db_latest` (PostgreSQL) ou `archive` (snapshot horodaté)
    """,
)
def get_comptes_tiers(
    req: ComptesTiersRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> ReferentielResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/referentiel/comptes-tiers",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/collaborateurs",
    response_model=ReferentielResponse,
    summary="Collaborateurs enrichi (vendeurs, acheteurs, matricule)",
    description="""
Recherche dans **F_COLLABORATEUR** avec filtres métier.

**Paramètres clés** :
- `co_vendeur=1` : uniquement les commerciaux
- `co_acheteur=1` : uniquement les acheteurs
- `co_fonction` : recherche partielle (ex: `"directeur"`)
- `co_matricule` : recherche partielle (ex: `"MAT"` → `"MAT001"`, `"AAMAT02"`)

**Source** : `db_latest` ou `archive`
    """,
)
def get_collaborateurs(
    req: CollaborateurRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> ReferentielResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/referentiel/collaborateurs",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/articles/detail",
    response_model=ReferentielResponse,
    summary="Articles avec stock et lots (enrichi)",
    description="""
Recherche dans **F_ARTICLE** avec options d'enrichissement stock et lots.

**Options** :
- `with_stock=true` : ajoute `qte_stock_totale` (F_ARTSTOCK)
- `with_lots=true` : ajoute `lots_actifs`, `lots_perimes`, `prochaine_peremption` (F_LOTSERIE)
- `depot_ids` : restreindre le stock à certains dépôts si `with_stock=true`

**Filtres** : `ar_design` (ILIKE), `ar_nature`, `ar_type`, `ar_suivistock`, `fa_codefamille`

**Source** : `db_latest` ou `archive`
    """,
)
def get_articles_detail(
    req: ArticleDetailRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> ReferentielResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/referentiel/articles/detail",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/familles",
    response_model=ReferentielResponse,
    summary="Familles d'articles avec comptage",
    description="""
Accès direct à **F_FAMILLE** avec arborescence centralisatrice.

**Paramètres clés** :
- `fa_type` : `[0]`=Détail, `[1]`=Total, `[2]`=Centralisateur
- `fa_central` : code de la famille parente (exact)
- `with_articles_count=true` : ajoute `nb_articles` (COUNT F_ARTICLE actifs)

**Source** : `db_latest` ou `archive`
    """,
)
def get_familles(
    req: FamilleRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> ReferentielResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/referentiel/familles",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/lots-series",
    response_model=ReferentielResponse,
    summary="Lots et séries (traçabilité, péremption)",
    description="""
Recherche dans **F_LOTSERIE** pour la traçabilité et le contrôle qualité.

**Paramètres clés** :
- `only_active=true` (défaut) : uniquement les lots non épuisés
- `ls_noserie` : numéro de lot/série partiel (ILIKE)
- `peremption_before` : alertes de péremption imminente (YYYY-MM-DD)
- `qte_restant_min` : seuil minimum de quantité restante

Colonne calculée : `jours_avant_peremption` (négatif = déjà périmé)

**Source** : `db_latest` ou `archive`
    """,
)
def get_lots_series(
    req: LotSerieRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> ReferentielResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/referentiel/lots-series",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/documents-entete",
    response_model=ReferentielResponse,
    summary="Entêtes de documents (factures, BL, BC, devis…)",
    description="""
Recherche dans **F_DOCENTETE** avec filtres riches et calcul du reste à payer.

**Paramètres clés** :
- `do_domaine` : `[0]`=Vente, `[1]`=Achat, `[3]`=Ticket
- `do_type` : Vente 0-7, Achat 10-17 (voir dictionnaire `/types-documents`)
- `montant_regle_unpaid=true` : uniquement les documents non entièrement réglés

Colonne calculée : `reste_a_payer = DO_TotalTTC - DO_MontantRegle`

**Source** : `db_latest` ou `archive`
    """,
)
def get_documents_entete(
    req: DocEnteteRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> ReferentielResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/referentiel/documents-entete",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/documents-ligne",
    response_model=ReferentielResponse,
    summary="Lignes de documents avec option entête",
    description="""
Recherche dans **F_DOCLIGNE** (niveau ligne). Option `with_entete` pour afficher l'entête.

**Paramètres clés** :
- `do_piece` : numéro(s) de pièce — filtre fort recommandé
- `ar_ref` : article(s) à rechercher dans tous les documents
- `with_entete=true` : ajoute DO_TotalTTC, DO_MontantRegle, reste_a_payer
  *(nécessite au moins un filtre fort : do_piece, ar_ref, ct_num ou période)*
- `dl_nonlivre=1` : uniquement les lignes non encore livrées

**Source** : `db_latest` ou `archive` (RAM-safe : filtre avant join)
    """,
)
def get_documents_ligne(
    req: DocLigneRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> ReferentielResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/referentiel/documents-ligne",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/stock-depot",
    response_model=ReferentielResponse,
    summary="Stock physique par article et par dépôt",
    description="""
Vue directe de **F_ARTSTOCK** enrichie avec F_ARTICLE, F_DEPOT et F_FAMILLE.

**Paramètres clés** :
- `de_no` : filtrer sur un ou plusieurs dépôts
- `only_rupture=true` : uniquement les articles en rupture (as_qtesto <= 0)
- `qte_min=0.01` : articles effectivement en stock (> 0)
- `fa_codefamille` : filtrer par famille

Colonnes calculées : `valeur_stock_achat`, `valeur_stock_vente`

**Source** : `db_latest` ou `archive`
    """,
)
def get_stock_depot(
    req: StockDepotRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> ReferentielResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/referentiel/stock-depot",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/reglements",
    response_model=ReferentielResponse,
    summary="Règlements/échéances (F_REGLECH) enrichis",
    description="""
Recherche dans **F_REGLECH** avec jointure sur F_DOCENTETE et F_COMPTET pour les détails de règlement.
    """,
)
def get_reglements(
    req: ReglementRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> ReferentielResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/referentiel/reglements",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


# ===========================================================================
# ROUTES UTILITAIRES (statiques)
# ===========================================================================

@router.get(
    "/types-tiers",
    summary="Dictionnaire des types de tiers (CT_Type)",
    description="Retourne le dictionnaire des valeurs CT_Type pour F_COMPTET.",
)
def get_types_tiers():
    return {
        "0": "Client",
        "1": "Fournisseur",
        "2": "Salarié",
        "3": "Autre",
    }


@router.get(
    "/types-documents",
    summary="Dictionnaire des types de documents (DO_Type)",
    description="Retourne le dictionnaire complet des types de documents par domaine.",
)
def get_types_documents():
    return {
        "vente": {
            "0": "Devis",
            "1": "Bon de commande",
            "2": "Préparation de livraison",
            "3": "Bon de livraison",
            "4": "Bon de retour",
            "5": "Bon d'avoir",
            "6": "Facture",
            "7": "Facture comptabilisée",
            "8": "Archive",
        },
        "achat": {
            "10": "Demande d'achat",
            "11": "Préparation de commande",
            "12": "Bon de commande",
            "13": "Bon de livraison",
            "14": "Bon de retour",
            "15": "Bon d'avoir",
            "16": "Facture",
            "17": "Facture comptabilisée",
            "18": "Archive",
        },
        "ticket": {
            "30": "Ticket de caisse",
        },
    }
