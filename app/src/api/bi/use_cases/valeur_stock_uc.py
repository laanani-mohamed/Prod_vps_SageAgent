"""
api/bi/use_cases/valeur_stock_uc.py

Use Case : POST /api/bi/rapport/valeur-stock
Retourne le stock valorisé (DL_CMUP × qté) par dépôt/famille/article.
"""
from __future__ import annotations
import logging

from api.bi.schemas import ValeurStockRequest, RapportResponse
from api.bi.repositories.factory_repo import get_bi_repo

logger = logging.getLogger("api.bi.use_cases.valeur_stock")


def execute(req: ValeurStockRequest) -> RapportResponse:
    repo = get_bi_repo("valeur_stock", req.source_type)

    try:
        rows = repo.fetch(req)
    except Exception as exc:
        logger.error("[BI/valeur_stock] Erreur repository (%s): %s", req.source_type, exc)
        raise

    return RapportResponse(
        endpoint="/api/bi/rapport/valeur-stock",
        client_schema=req.client_schema,
        source=req.source_type,
        total_rows=len(rows),
        data=rows,
    )
