"""
api/stock/router.py — Routeur FastAPI pour le module Stock.

Expose les endpoints spécifiques par intention (intent) :
  POST /api/stock/availability    → CheckAvailabilityRequest
  POST /api/stock/details         → ArticleDetailsRequest
  POST /api/stock/catalog         → CatalogSearchRequest
  POST /api/stock/insights        → StockInsightRequest
  POST /api/stock/snapshot         → StockSnapshotRequest
  POST /api/stock/compare         → StockCompareTimeRequest

Route utilitaire :
  GET  /api/stock/health          → Healthcheck
"""
import logging
from fastapi import APIRouter, HTTPException, Request, Depends

from api.auth.dependencies import require_role
from api.auth.schemas import TokenData
from api._base_router import secured_handle

from api.stock.schemas import (
    CheckAvailabilityRequest,
    ArticleDetailsRequest,
    CatalogSearchRequest,
    StockInsightRequest,
    StockSnapshotRequest,
    StockCompareTimeRequest,
    StockResponse,
)
from api.stock.service import get_specific

logger = logging.getLogger("api.stock.router")
router = APIRouter(prefix="/api/stock", tags=["Stock"])


# ===========================================================================
# ROUTES UNITAIRES
# ===========================================================================

@router.get("/health", summary="Healthcheck du module Stock")
def health():
    """Vérifie que le module stock est opérationnel."""
    return {"status": "ok", "module": "api.stock"}


@router.post(
    "/availability",
    response_model=StockResponse,
    summary="Disponibilité et stock d'un article",
    description="Retourne le stock total disponible par article et facultativement ventilé par dépôt.",
)
def get_stock_availability(
    req: CheckAvailabilityRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> StockResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/stock/availability",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/details",
    response_model=StockResponse,
    summary="Fiche technique détaillée d'un article",
    description="Retourne la fiche complète d'un article avec ses stocks par dépôt et ses lots si applicable.",
)
def get_article_details(
    req: ArticleDetailsRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> StockResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/stock/details",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/catalog",
    response_model=StockResponse,
    summary="Recherche catalogue technique",
    description="Recherche multicritère d'articles basée sur leurs caractéristiques techniques (nature, type, suivi).",
)
def get_catalog_search(
    req: CatalogSearchRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> StockResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/stock/catalog",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/insights",
    response_model=StockResponse,
    summary="Détection d'anomalies de stock (insights)",
    description="Détecte les alertes de stocks : ruptures, stock bas, produits dormants, ou lots arrivant à expiration.",
)
def get_stock_insights(
    req: StockInsightRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> StockResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/stock/insights",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/snapshot",
    response_model=StockResponse,
    summary="Snapshot d'état de stock passé",
    description="Retourne l'état des stocks à une date précise du passé en lisant depuis les snapshots archivés.",
)
def get_stock_snapshot(
    req: StockSnapshotRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> StockResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/stock/snapshot",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )


@router.post(
    "/compare",
    response_model=StockResponse,
    summary="Comparaison temporelle des stocks",
    description="Compare la quantité totale disponible par article entre deux dates (archives et/ou base courante).",
)
def compare_stock_time(
    req: StockCompareTimeRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
) -> StockResponse:
    return secured_handle(
        get_specific,
        endpoint="/api/stock/compare",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )
