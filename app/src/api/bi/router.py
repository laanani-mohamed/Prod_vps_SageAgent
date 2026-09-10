"""
api/bi/router.py — Routeur FastAPI pour le module BI (Dashboard, Rapports).

Routes :
  GET  /api/bi/dashboard             → KPIs agrégés (CA, Achats, Stock, Encours)
  GET  /api/bi/dashboard/objectifs   → Axes stratégiques
  POST /api/bi/rapport/ca            → Rapport Chiffre d'Affaires
  POST /api/bi/top-clients           → Top N clients par CA
  POST /api/bi/top-articles          → Top N articles vendus
"""
import logging
from fastapi import APIRouter, HTTPException, Query, Depends, Request

from api.auth.dependencies import require_role
from api.auth.schemas import TokenData
from api._base_router import secured_handle

from api.bi.schemas import (
    DashboardRequest, DashboardResponse, ObjectifsResponse,
    RapportCARequest, TopClientsRequest, TopArticlesRequest,
    RapportResponse, KpiAnalytiqueResponse, BalanceClientRequest,
    RapportVisiteClientRequest, ValeurStockRequest,
    RapportConsommationRequest,
)
from api.bi.service import (
    get_dashboard, get_objectifs, get_analytique,
    get_rapport_ca, get_top_clients, get_top_articles,
    get_balance_client, get_rapport_visite, get_valeur_stock,
    get_rapport_consommation, get_balance_agee,
)

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
    current_user: TokenData = Depends(require_role("analyst"))
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
    "/dashboard/objectifs",
    response_model=ObjectifsResponse,
    summary="Axes stratégiques et objectifs",
)
def dashboard_objectifs(
    request: Request,
    client_schema: str = Query(..., description="Schéma client"),
    current_user: TokenData = Depends(require_role("analyst"))
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
    current_user: TokenData = Depends(require_role("analyst"))
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
    current_user: TokenData = Depends(require_role("analyst"))
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
    current_user: TokenData = Depends(require_role("analyst"))
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
    current_user: TokenData = Depends(require_role("analyst"))
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
    current_user: TokenData = Depends(require_role("analyst"))
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
    current_user: TokenData = Depends(require_role("analyst"))
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
    summary="Rapport Valeur du Stock (DL_CMUP × qté par dépôt/famille/article)",
)
def rapport_valeur_stock(
    req: ValeurStockRequest,
    request: Request,
    current_user: TokenData = Depends(require_role("analyst"))
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
    current_user: TokenData = Depends(require_role("analyst"))
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
    current_user: TokenData = Depends(require_role("analyst"))
) -> RapportResponse:
    return secured_handle(
        get_rapport_consommation,
        endpoint="/api/bi/rapport/consommation",
        request=request,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req
    )
