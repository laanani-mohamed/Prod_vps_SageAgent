"""
bi/referentiel/schemas.py — Modèles Pydantic pour le module Référentiel.

Architecture v2 :
  - BaseReferentielRequest : socle commun (client_schema, source, limit)
  - ReferentielRequest     : modèle LEGACY inchangé (rétro-compatibilité /articles, /clients, /depots)
  - Schémas spécifiques par ressource (pattern identique à /bi/stock) :
      ComptesTiersRequest   → bi/referentiel/comptes-tiers
      CollaborateurRequest  → bi/referentiel/collaborateurs
      ArticleDetailRequest  → bi/referentiel/articles/detail
      FamilleRequest        → bi/referentiel/familles
      LotSerieRequest       → bi/referentiel/lots-series
      DocEnteteRequest      → bi/referentiel/documents-entete
      DocLigneRequest       → bi/referentiel/documents-ligne
      StockDepotRequest     → /stock-depot
"""
from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# ===========================================================================
# MODÈLE DE REPONSE COMMUNE
# ===========================================================================

class ReferentielResponse(BaseModel):
    endpoint: str
    client_schema: str
    source: str
    message: Optional[str] = None
    total_rows: Optional[int] = None
    data: List[dict]


# ===========================================================================
# BASE COMMUNE — Nouveaux schémas spécifiques
# ===========================================================================

class BaseReferentielRequest(BaseModel):
    """Socle commun à tous les nouveaux schémas spécifiques par ressource."""
    client_schema: str = Field(..., description="Schéma PostgreSQL du client (ex: 'client_01')")
    source_type: str = Field(
        "db_latest",
        description="Source de données : 'db_latest' (PostgreSQL courant) | 'archive' (snapshot horodaté)"
    )
    snapshot_datetime: Optional[str] = Field(
        None,
        description="Pour source_type='archive' : datetime ISO du snapshot cible (ex: '2026-01-15T08:00:00')"
    )
    limit: int = Field(100000000, ge=1, description="Nombre max de lignes retournées (sans plafond)")

    @field_validator("client_schema")
    @classmethod
    def validate_client_schema(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", str(v)):
            raise ValueError("Nom de schéma invalide (risque d'injection SQL).")
        return str(v)


# ===========================================================================
# A.1 — ComptesTiersRequest → POST /bi/referentiel/comptes-tiers
# ===========================================================================

class ComptesTiersRequest(BaseReferentielRequest):
    """Recherche dans F_COMPTET (clients, fournisseurs, salariés, autres).

    Tous les champs sont optionnels. Par défaut : clients actifs uniquement.

    Exemples :
    - "Liste de tous mes clients actifs à Casablanca"
    - "Fournisseur avec ICE 012345678901234"
    - "Clients représentés par le commercial CO_No=3"
    - "Comptes créés entre janvier et mars 2026"
    """
    # Filtres d'identification
    ct_num: List[str] = Field(
        default_factory=list,
        description="Numéros de compte(s) spécifiques (CT_Num) — ex: ['CLT001', 'CLT002']"
    )
    ct_intitule: Optional[str] = Field(
        None,
        description="Intitulé du compte (ILIKE '%...%') — ex: 'dupont' retourne tous les comptes Dupont"
    )
    ct_type: List[int] = Field(
        default=[0],
        description="Type(s) de tiers : 0=Client, 1=Fournisseur, 2=Salarié, 3=Autre"
    )
    ct_sommeil: Optional[int] = Field(
        0,
        description="Statut actif : 0=Actif uniquement, 1=En sommeil uniquement, None=Tous"
    )
    ct_identifiant: Optional[str] = Field(
        None,
        description="Numéro ICE exact (CT_Identifiant) — recherche exacte"
    )

    # Filtres géographiques / qualification
    ct_ville: Optional[str] = Field(
        None,
        description="Ville (recherche partielle, insensible à la casse) — ex: 'casa'"
    )
    ct_qualite: Optional[str] = Field(
        None,
        description="Qualité du tiers (recherche partielle) — ex: 'sarl'"
    )
    ct_code_region: Optional[str] = Field(
        None,
        description="Code région (recherche partielle) — ex: 'SUD'"
    )

    # Filtres relationnels
    co_no_representant: Optional[int] = Field(
        None,
        description="Filtrer les comptes par représentant attitré (CO_No)"
    )

    # Filtres temporels
    cbcreation_from: Optional[str] = Field(
        None,
        description="Date de création >= YYYY-MM-DD"
    )
    cbcreation_to: Optional[str] = Field(
        None,
        description="Date de création <= YYYY-MM-DD"
    )


# ===========================================================================
# A.2 — CollaborateurRequest → POST /bi/referentiel/collaborateurs
# ===========================================================================

class CollaborateurRequest(BaseReferentielRequest):
    """Recherche dans F_COLLABORATEUR avec filtres métier.

    Exemples :
    - "Liste de tous les vendeurs actifs"
    - "Acheteurs de l'entreprise"
    - "Collaborateur avec matricule MAT"
    - "Commerciaux dont la fonction contient 'responsable'"
    """
    co_no: List[int] = Field(
        default_factory=list,
        description="Numéros internes spécifiques (CO_No)"
    )
    co_vendeur: Optional[int] = Field(
        None,
        description="Rôle vendeur : 1=Vendeurs uniquement, 0=Non-vendeurs, None=Tous"
    )
    co_acheteur: Optional[int] = Field(
        None,
        description="Rôle acheteur : 1=Acheteurs uniquement, 0=Non-acheteurs, None=Tous"
    )
    co_nom: Optional[str] = Field(
        None,
        description="Nom du collaborateur (ILIKE '%...%') — ex: 'ben' retourne 'Benali', 'Benmoussa'"
    )
    co_prenom: Optional[str] = Field(
        None,
        description="Prénom du collaborateur (ILIKE '%...%') — ex: 'ali'"
    )
    co_fonction: Optional[str] = Field(
        None,
        description="Fonction (recherche partielle, insensible à la casse) — ex: 'directeur'"
    )
    co_matricule: Optional[str] = Field(
        None,
        description="Matricule (recherche partielle ILIKE '%...%') — ex: 'MAT' retourne 'MAT001', 'AAMAT02'"
    )


# ===========================================================================
# A.3 — ArticleDetailRequest → POST /bi/referentiel/articles/detail
# ===========================================================================

class ArticleDetailRequest(BaseReferentielRequest):
    """Recherche dans F_ARTICLE avec enrichissements stock et lots en option.

    Exemples :
    - "Article REF001 avec ses quantités en stock par dépôt"
    - "Articles de la famille ELECT avec stock total"
    - "Produits finis avec des lots actifs non encore expirés"
    - "Articles dont la désignation contient 'cable'"
    """
    # Filtres articles
    ar_ref: Optional[str] = Field(
        None,
        description="Référence article (ILIKE '%...%') — ex: 'REF' retourne 'REF001', 'AREF02'. Pour une liste exacte, utiliser ar_ref_exact."
    )
    ar_ref_exact: List[str] = Field(
        default_factory=list,
        description="Référence(s) article(s) exactes (IN) — ex: ['REF001', 'REF002']"
    )
    ar_design: List[str] = Field(
        default_factory=list,
        description="Désignation(s) (chaque élément est un ILIKE '%...%' en OR) — ex: ['cable', 'fil'] retourne tous les articles contenant 'cable' OU 'fil'"
    )
    ar_code_barre: Optional[str] = Field(None, description="Code barre (exact)")
    fa_codefamille: List[str] = Field(default_factory=list, description="Code(s) famille")
    ar_nature: List[int] = Field(
        default_factory=list,
        description="Nature : 0=Composant, 1=Pièce détachée, 2=Produit fini, 3=Semi-fini"
    )
    ar_type: List[int] = Field(
        default_factory=list,
        description="Type : 0=Standard, 1=Gamme, 2=Prestation, 3=Location"
    )
    ar_suivistock: List[int] = Field(
        default_factory=list,
        description="Suivi stock : 0=Aucun, 1=Sérialisé, 2=CMUP, 3=FIFO, 4=LIFO, 5=Par lot"
    )
    ar_sommeil: Optional[int] = Field(0, description="0=Actif, 1=En sommeil, None=Tous")

    # Options de vue (enrichissements)
    with_stock: bool = Field(
        False,
        description="Si True : ajoute 'qte_stock_totale' depuis F_ARTSTOCK (somme de tous les dépôts)"
    )
    with_lots: bool = Field(
        False,
        description="Si True : ajoute 'lots_actifs', 'lots_perimes', 'prochaine_peremption' depuis F_LOTSERIE"
    )
    depot_ids: List[int] = Field(
        default_factory=list,
        description="Si with_stock=True : filtrer le stock uniquement sur ces dépôts. Vide = tous les dépôts."
    )


# ===========================================================================
# A.4 — FamilleRequest → POST /bi/referentiel/familles
# ===========================================================================

class FamilleRequest(BaseReferentielRequest):
    """Recherche dans F_FAMILLE avec arborescence et comptage articles.

    Exemples :
    - "Liste de toutes les familles avec leur nombre d'articles"
    - "Familles centralisatrices du catalogue"
    - "Familles avec suivi stock CMUP"
    - "Sous-familles de la famille centralisatrice ELEC"
    """
    fa_codefamille: List[str] = Field(default_factory=list, description="Code(s) famille spécifiques")
    fa_intitule: Optional[str] = Field(
        None,
        description="Intitulé de la famille (ILIKE '%...%') — ex: 'elec' retourne 'Electronique', 'Electricité'"
    )
    fa_type: List[int] = Field(
        default_factory=list,
        description="Type : 0=Détail, 1=Total, 2=Centralisateur"
    )
    fa_central: Optional[str] = Field(
        None,
        description="Code famille centralisatrice parente (exact) — pour filtrer les sous-familles"
    )
    fa_suivistock: List[int] = Field(
        default_factory=list,
        description="Méthode de suivi stock : 0=Aucun, 1=Sérialisé, 2=CMUP, 3=FIFO, 4=LIFO, 5=Par lot"
    )
    with_articles_count: bool = Field(
        False,
        description="Si True : ajoute 'nb_articles' (articles actifs par famille)"
    )
    with_articles_names: bool = Field(
        False,
        description="Si True : ajoute 'articles_names' (liste des désignations des articles actifs)"
    )


# ===========================================================================
# A.5 — LotSerieRequest → POST /bi/referentiel/lots-series
# ===========================================================================

class LotSerieRequest(BaseReferentielRequest):
    """Recherche dans F_LOTSERIE (traçabilité, péremption, contrôle qualité).

    Exemples :
    - "Lots actifs de l'article REF001"
    - "Lots qui expirent avant le 31/12/2026"
    - "Lots non épuisés avec quantité restante > 10"
    - "Numéro de lot contenant 'LOT2026'"
    - "Tous les lots en alerte péremption des 30 prochains jours"
    """
    ar_ref: List[str] = Field(default_factory=list, description="Référence(s) article(s)")
    fa_codefamille: List[str] = Field(default_factory=list, description="Code(s) famille (via F_ARTICLE)")
    ls_noserie: Optional[str] = Field(
        None,
        description="Numéro de lot/série (ILIKE '%...%') — ex: 'LOT2026' retourne 'LOT2026-001'"
    )
    de_no: List[int] = Field(default_factory=list, description="Dépôt(s) spécifiques (DE_NO)")
    only_active: bool = Field(
        True,
        description="Si True (défaut) : retourne uniquement les lots non épuisés (LS_LotEpuise=0)"
    )
    ls_lotepuise: Optional[int] = Field(
        None,
        description="Statut : 0=Actif, 1=Épuisé. Ignoré si only_active=True."
    )
    peremption_before: Optional[str] = Field(
        None,
        description="Lots périmant AVANT cette date YYYY-MM-DD (alerte préemption)"
    )
    peremption_after: Optional[str] = Field(
        None,
        description="Lots périmant APRÈS cette date YYYY-MM-DD"
    )
    qte_restant_min: Optional[float] = Field(
        None,
        description="Seuil minimum de quantité restante (LS_QteRestant >= valeur)"
    )


# ===========================================================================
# A.6 — DocEnteteRequest → POST /bi/referentiel/documents-entete
# ===========================================================================

class DocEnteteRequest(BaseReferentielRequest):
    """Recherche dans F_DOCENTETE (entêtes de tous les documents commerciaux).

    Exemples :
    - "Toutes les factures du client CLT001 en janvier 2026"
    - "BL non soldés (DO_MontantRegle < DO_TotalTTC)"
    - "Bons de commande fournisseur du mois courant"
    - "Document FA2026-001 : détail de la facture"
    - "Devis du commercial CO_No=3 sur le T1 2026"
    """
    # Filtres document
    do_domaine: List[int] = Field(
        default=[0],
        description="Domaine : 0=Vente, 1=Achat, 2=Stock, 3=Ticket, 4=Document interne"
    )
    do_type: List[int] = Field(
        default_factory=list,
        description=(
            "Type document Vente : 0=Devis, 1=BC, 2=PL, 3=BL, 4=Retour, 5=Avoir, 6=Facture, 7=Facture comptab. | "
            "Achat : 10=DA, 11=PC, 12=BC, 13=BL, 14=Retour, 15=Avoir, 16=Facture, 17=Facture comptab."
        )
    )
    do_piece: List[str] = Field(default_factory=list, description="N° de pièce(s) interne(s) spécifiques")
    do_tiers: List[str] = Field(default_factory=list, description="Code(s) client/fournisseur (CT_Num)")
    co_no: List[int] = Field(default_factory=list, description="Représentant(s) (CO_No)")
    do_ref: Optional[str] = Field(None, description="N° pièce externe (ILIKE '%...%')")

    # Filtres temporels
    do_date: Optional[str] = Field(None, description="Date exacte du document = YYYY-MM-DD")
    date_from: Optional[str] = Field(None, description="Date document >= YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="Date document <= YYYY-MM-DD")

    # Filtres montant
    do_totalttc_min: Optional[float] = Field(None, description="Montant TTC minimum")
    do_totalttc_max: Optional[float] = Field(None, description="Montant TTC maximum")
    montant_regle_unpaid: bool = Field(
        False,
        description="Si True : uniquement les documents non entièrement réglés (reste_a_payer > 0)"
    )


# ===========================================================================
# A.7 — DocLigneRequest → POST /bi/referentiel/documents-ligne
# ===========================================================================

class DocLigneRequest(BaseReferentielRequest):
    """Recherche dans F_DOCLIGNE (lignes de documents) avec option d'affichage de l'entête.

    Exemples :
    - "Toutes les lignes de la facture FA2026-001"
    - "Dans quels documents a été vendu l'article REF001 en mars 2026 ?"
    - "Lignes non livrées du client CLT001"
    - "Lignes valorisées avec montant HT > 5000 DH"
    """
    # Filtres document
    do_domaine: List[int] = Field(default=[0], description="Domaine : 0=Vente, 1=Achat, 2=Stock, 3=Ticket")
    do_type: List[int] = Field(default_factory=list, description="Type(s) de document")
    do_piece: List[str] = Field(
        default_factory=list,
        description="N° de pièce(s) — filtre fort recommandé pour limiter le volume"
    )

    # Filtres tiers / article
    ar_ref: List[str] = Field(default_factory=list, description="Référence(s) article(s)")
    ct_num: List[str] = Field(default_factory=list, description="Code(s) client/fournisseur")
    co_no: List[int] = Field(default_factory=list, description="Représentant(s)")
    dl_design: Optional[str] = Field(None, description="Désignation de ligne (ILIKE '%...%')")
    pf_num: Optional[str] = Field(
        None,
        description="Numéro de projet/affaire (PF_Num) — filtre exact (ex: 'PROJ2026-01')"
    )

    # Filtres temporels
    do_date: Optional[str] = Field(None, description="Date exacte du document = YYYY-MM-DD")
    date_from: Optional[str] = Field(None, description="Date document >= YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="Date document <= YYYY-MM-DD")

    # Filtres quantité / montant
    dl_qte_min: Optional[float] = Field(None, description="Quantité minimum (DL_Qte >= valeur)")
    dl_montantht_min: Optional[float] = Field(None, description="Montant HT minimum par ligne")
    dl_nonlivre: Optional[int] = Field(None, description="0=Livré, 1=Non livré (DL_NonLivre)")
    dl_valorise: Optional[int] = Field(None, description="0=Non valorisé, 1=Valorisé (DL_Valorise)")

    # Option entête
    with_entete: bool = Field(
        False,
        description=(
            "Si True : inclure les colonnes de F_DOCENTETE (DO_TotalTTC, DO_MontantRegle, reste_a_payer). "
            "Nécessite au moins un filtre fort : do_piece, ar_ref, ct_num ou période."
        )
    )

    @model_validator(mode="after")
    def check_with_entete_requires_filter(self):
        """Protection RAM : with_entete=True nécessite au moins un filtre fort."""
        if self.with_entete:
            has_filter = (
                bool(self.do_piece)
                or bool(self.ar_ref)
                or bool(self.ct_num)
                or bool(self.do_date)
                or bool(self.date_from)
                or bool(self.date_to)
            )
            if not has_filter:
                raise ValueError(
                    "with_entete=True nécessite au moins un filtre fort "
                    "(do_piece, ar_ref, ct_num, do_date, date_from ou date_to) "
                    "pour éviter le chargement de tout l'historique."
                )
        return self


class StockDepotRequest(BaseReferentielRequest):
    """Filtres pour consulter les stocks par dépôt (F_ARTSTOCK)"""
    ar_ref: Optional[List[str]] = None
    de_no: Optional[List[int]] = None
    fa_codefamille: Optional[List[str]] = None
    ar_suivistock: Optional[List[int]] = None
    ar_sommeil: Optional[int] = None
    qte_min: Optional[float] = None
    qte_max: Optional[float] = None
    only_rupture: bool = False


class ReglementRequest(BaseReferentielRequest):
    """Filtres pour consulter les règlements (F_REGLECH)"""
    do_domaine: List[int] = Field(default=[0], description="Domaine : 0=Vente, 1=Achat")
    do_type: List[int] = Field(default_factory=list, description="Type de document")
    do_piece: List[str] = Field(default_factory=list, description="Numéro de pièce")
    rg_typereg: List[int] = Field(default_factory=list, description="Type règlement : 0 à 8")
    date_from: Optional[str] = Field(None, description="Date document >= YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="Date document <= YYYY-MM-DD")


