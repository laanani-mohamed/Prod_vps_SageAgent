"""
api/bi/router.py — Routeur FastAPI pour le module BI (Dashboard, Rapports).

Routes :
  GET  /api/bi/dashboard             → KPIs agrégés (CA, Achats, Stock, Encours)
  GET  /api/bi/dashboard/objectifs   → Axes stratégiques
  POST /api/bi/rapport/ca            → Rapport Chiffre d'Affaires
  POST /api/bi/top-clients           → Top N clients par CA
  POST /api/bi/top-articles          → Top N articles vendus
  POST /api/bi/rapports/{nom}        → Rapport mis en forme (JSON) ou export ?format=pdf|xlsx
  POST /api/bi/vues/{nom}            → Données prêtes à afficher d'une page du front Next.js
  POST /api/bi/bon-commande          → PDF d'un bon de commande client (page « Passer bon de commande »)
"""
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Depends, Request

from api.auth.audit import log_audit_event
from api.auth.dependencies import DIRECTEUR_OU_COLLABORATEUR, DIRECTEUR_SEUL
from api.auth.schemas import TokenData
from api._base_router import secured_handle

from api.bi.schemas import (
    DashboardRequest, DashboardResponse, ObjectifsResponse, LastUpdateResponse,
    RapportCARequest, TopClientsRequest, TopArticlesRequest,
    RapportResponse, KpiAnalytiqueResponse, BalanceClientRequest,
    RapportVisiteClientRequest, ValeurStockRequest,
    RapportConsommationRequest, StatsTiersRequest, RapportRequest, VueRequest, BonCommandeRequest,
)
from api.bi.service import (
    get_dashboard, get_objectifs, get_analytique,
    get_rapport_ca, get_top_clients, get_top_articles,
    get_balance_client, get_rapport_visite, get_valeur_stock,
    get_rapport_consommation, get_balance_agee, get_last_update,
    get_stats_tiers, get_rapport, get_vue, get_bon_commande,
)
from api.bi.vues import reservee_directeur

logger = logging.getLogger("api.bi.router")
router = APIRouter(prefix="/api/bi", tags=["BI — Dashboard & Rapports"])

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.post(
    "/dashboard",
    response_model=DashboardResponse,
    summary="KPIs du tableau de bord (CA, Achats, Stock, Encours)",
    description="""
Agrège les données depuis les archives pour produire les 4 KPIs du tableau de bord.

**Paramètres clés** :
- `client_schema` : Schéma client (ex: `"client_01"`)
- `date_from` / `date_to` : Filtrer la période (YYYY-MM-DD)
- `source_type` : Toujours `"archive"` en V1
    """,
)
def dashboard(
    req: DashboardRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> DashboardResponse:
    return secured_handle(
        get_dashboard,
        endpoint="/api/bi/dashboard",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


@router.get(
    "/dashboard/last-update",
    response_model=LastUpdateResponse,
    summary="Horodatage de la dernière ingestion ETL réussie pour ce client",
)
def dashboard_last_update(
    request: Request,
    client_schema: str = Query(..., description="Schéma client"),
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> LastUpdateResponse:
    return secured_handle(
        get_last_update,
        partage=True,
        endpoint="/api/bi/dashboard/last-update",
        request=request,
        current_user=current_user,
        client_schema=client_schema
    )


@router.get(
    "/dashboard/objectifs",
    response_model=ObjectifsResponse,
    summary="Axes stratégiques et objectifs",
)
def dashboard_objectifs(
    request: Request,
    client_schema: str = Query(..., description="Schéma client"),
    current_user: TokenData = Depends(DIRECTEUR_SEUL)
) -> ObjectifsResponse:
    return secured_handle(
        get_objectifs,
        endpoint="/api/bi/dashboard/objectifs",
        request=request,
        current_user=current_user,
        client_schema=client_schema
    )


@router.get(
    "/dashboard/analytique",
    response_model=KpiAnalytiqueResponse,
    summary="KPIs Analytiques (Marge, DSO, Litige, Retour, Conversion, Top Clients)",
)
def dashboard_analytique(
    request: Request,
    client_schema: str = Query(..., description="Schéma client"),
    date_from: str = Query(..., description="Date début YYYY-MM-DD"),
    date_to: str = Query(..., description="Date fin YYYY-MM-DD"),
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> KpiAnalytiqueResponse:
    return secured_handle(
        get_analytique,
        endpoint="/api/bi/dashboard/analytique",
        request=request,
        current_user=current_user,
        client_schema=client_schema,
        date_from=date_from,
        date_to=date_to
    )

# ---------------------------------------------------------------------------
# Rapports
# ---------------------------------------------------------------------------

@router.post(
    "/rapport/ca",
    response_model=RapportResponse,
    summary="Rapport Chiffre d'Affaires (groupé par mois, client ou commercial)",
)
def rapport_ca(
    req: RapportCARequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> RapportResponse:
    return secured_handle(
        get_rapport_ca,
        endpoint="/api/bi/rapport/ca",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


@router.post(
    "/top-clients",
    response_model=RapportResponse,
    summary="Top N clients par CA sur la période",
)
def top_clients(
    req: TopClientsRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> RapportResponse:
    return secured_handle(
        get_top_clients,
        endpoint="/api/bi/top-clients",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


@router.post(
    "/top-articles",
    response_model=RapportResponse,
    summary="Top N articles vendus sur la période",
)
def top_articles(
    req: TopArticlesRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> RapportResponse:
    return secured_handle(
        get_top_articles,
        endpoint="/api/bi/top-articles",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


@router.post(
    "/rapport/balance",
    response_model=RapportResponse,
    summary="Balance par clients",
)
def rapport_balance(
    req: BalanceClientRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> RapportResponse:
    return secured_handle(
        get_balance_client,
        endpoint="/api/bi/rapport/balance",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


@router.post(
    "/rapport/visite-client",
    response_model=RapportResponse,
    summary="Rapport Client Avant Visite (BCs, Factures, Articles, Familles, CA N vs N-1)",
)
def rapport_visite_client(
    req: RapportVisiteClientRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> RapportResponse:
    return secured_handle(
        get_rapport_visite,
        endpoint="/api/bi/rapport/visite-client",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


@router.post(
    "/rapport/valeur-stock",
    response_model=RapportResponse,
    summary="Rapport Valeur du Stock (Σ AS_MontSto par dépôt/famille/article)",
)
def rapport_valeur_stock(
    req: ValeurStockRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_SEUL)
) -> RapportResponse:
    return secured_handle(
        get_valeur_stock,
        endpoint="/api/bi/rapport/valeur-stock",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


@router.post(
    "/rapport/balance-agee",
    response_model=RapportResponse,
    summary="Balance âgée par clients (tranches en jours)",
)
def rapport_balance_agee(
    req: BalanceClientRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> RapportResponse:
    return secured_handle(
        get_balance_agee,
        endpoint="/api/bi/rapport/balance-agee",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


@router.post(
    "/rapport/consommation",
    response_model=RapportResponse,
    summary="Consommation des articles par famille/produit (6 mois glissants)",
)
def rapport_consommation(
    req: RapportConsommationRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_SEUL)
) -> RapportResponse:
    return secured_handle(
        get_rapport_consommation,
        endpoint="/api/bi/rapport/consommation",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


@router.post(
    "/stats-tiers",
    response_model=RapportResponse,
    summary="Statistiques d'un client ou d'un fournisseur sur une période (vs N-1)",
)
def stats_tiers(
    req: StatsTiersRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
) -> RapportResponse:
    return secured_handle(
        get_stats_tiers,
        endpoint="/api/bi/stats-tiers",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )


def _refuser(request: Request, user: TokenData, schema: str, endpoint: str, motif: str):
    """403 journalisé dans l'audit, comme les refus de secured_handle."""
    log_audit_event("ACCESS_DENIED", endpoint, request.client.host if request.client else "unknown", "FAILED",
                    username=user.username, client_schema=schema, details=motif)
    raise HTTPException(status_code=403, detail=motif)


# Rapports de stock : sans commercial, donc non filtrables pour un collaborateur
RAPPORTS_DIRECTEUR = {"valeur_stock", "produits_dormants", "lots_peremption", "consommation"}


@router.post(
    "/rapports/{nom}",
    summary="Rapport mis en forme (JSON), ou son export PDF / Excel",
    description="""
Les 9 rapports de l'onglet Rapports, calculés par `reporting/` comme pour la tâche planifiée :
`chiffre_affaire`, `comparaison_ca`, `balance`, `balance_agee`, `valeur_stock`, `visite_client`,
`produits_dormants`, `lots_peremption`, `consommation`.

- `format=json` (défaut) : `titre`, `sous_titre`, `filtres` appliqués, `sections` (`titre`, `colonnes`, `lignes`),
  `totaux` (ligne Total) et `repartition` (graphique : valeur par dépôt, ancienneté des dormants).
- `format=pdf` / `format=xlsx` : le fichier, identique aux boutons de téléchargement du dashboard.
- `filtres` : mêmes clés que `config/rapports_config.py` ; filtre inconnu ou invalide → 400.
- Collaborateur : ses propres chiffres (co_no du jeton) ; rapports de stock → 403.
    """,
)
def rapport(
    nom: str,
    req: RapportRequest,
    request: Request,
    format: Literal["json", "pdf", "xlsx"] = "json",
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
):
    endpoint = f"/api/bi/rapports/{nom}"
    if nom in RAPPORTS_DIRECTEUR and "collaborateur" in current_user.roles:
        _refuser(request, current_user, req.client_schema, endpoint, "Rapport réservé au directeur")
    return secured_handle(
        get_rapport,
        endpoint=endpoint,
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
        nom=nom,
        format=format,
    )


@router.post(
    "/vues/{nom}",
    summary="Données prêtes à afficher d'une page du front (filtrées, totalisées, paginées)",
    description="""
Vues de `api/bi/vues.py` : `reglements`, `documents`, `document`, `compteurs`, `articles`, `article`, `tiers`, `clients`,
`depots`, `familles`, `stock_etat`, `stock_alertes`, `plan_depots`, et (api/bi/vues_analyse.py) `tdb_plus`
(panier moyen, rythme, alertes, top commerciaux), `ruptures_a`, `analyse_ventes`, `analyse_achats`. `filtres` : propres à chaque vue
(voir les docstrings), `page` pour la pagination (50 lignes). Filtre manquant ou invalide → 400.
Collaborateur : ses propres documents ; stock, achats et fournisseurs → 403.
    """,
)
def vue(
    nom: str,
    req: VueRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
):
    endpoint = f"/api/bi/vues/{nom}"
    if "collaborateur" in current_user.roles and reservee_directeur(nom, req.filtres):
        _refuser(request, current_user, req.client_schema, endpoint, "Section réservée au directeur")
    return secured_handle(
        get_vue,
        endpoint=endpoint,
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
        nom=nom,
    )


@router.post(
    "/bon-commande",
    summary="PDF d'un bon de commande client",
    description="""
Bon de commande de la page « Passer bon de commande » (page 9 de Streamlit), au format PDF :
lignes (référence, quantité, remise %) et remise globale saisies ; prix de vente, désignation et famille
relus dans Sage ; totaux HT, TVA 20 % et TTC. Rien n'est écrit en base. Client ou article inconnu → 400.
Directeur et collaborateur (référentiel partagé, aucune donnée d'un autre commercial).
    """,
)
def bon_commande(
    req: BonCommandeRequest,
    request: Request,
    current_user: TokenData = Depends(DIRECTEUR_OU_COLLABORATEUR)
):
    return secured_handle(
        get_bon_commande,
        partage=True,
        endpoint="/api/bi/bon-commande",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )
