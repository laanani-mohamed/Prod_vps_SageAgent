"""
bi/stock/service.py — Couche service pour le module Stock.
"""
from __future__ import annotations
import logging
from typing import Any, Callable

from api.stock.schemas import StockResponse
from api.stock.use_cases import (
    availability_uc,
    article_details_uc,
    catalog_search_uc,
    stock_insight_uc,
    stock_snapshot_uc,
    stock_compare_time_uc,
)

logger = logging.getLogger("api.stock.service")

# Mappe les endpoints vers leurs use cases spécifiques
RESOURCE_HANDLERS: dict[str, Callable[[Any], StockResponse]] = {
    "/api/stock/availability": availability_uc.execute,
    "/api/stock/details": article_details_uc.execute,
    "/api/stock/catalog": catalog_search_uc.execute,
    "/api/stock/insights": stock_insight_uc.execute,
    "/api/stock/snapshot": stock_snapshot_uc.execute,
    "/api/stock/compare": stock_compare_time_uc.execute,
}

def get_specific(req: Any, endpoint: str) -> StockResponse:
    """Route vers le bon Use Case pour les requêtes de stock spécifiques."""
    handler = RESOURCE_HANDLERS.get(endpoint)
    if not handler:
        raise ValueError(f"Endpoint stock spécifique non géré : {endpoint}")
    
    # Remplir automatiquement les listes vides et valeurs None non fournies (RAM & Validation safety)
    if hasattr(req, "model_fields_set") and hasattr(req, "model_fields"):
        system_fields = {
            "client_schema", "source_type", "snapshot_datetime", "limit",
            "with_financials", "by_depot", "only_available", "threshold", "expiry_days"
        }
        for field, field_info in req.model_fields.items():
            if field not in system_fields and field not in req.model_fields_set:
                anno_str = str(field_info.annotation).lower()
                if "list" in anno_str:
                    setattr(req, field, [])
                else:
                    setattr(req, field, None)

    logger.info(f"[Stock] endpoint={endpoint} | schema={req.client_schema} | source={req.source_type}")
    return handler(req)
