"""
api/bi/use_cases/top_clients_uc.py

Use Case : POST /api/bi/top-clients
Orchestre : factory_repo (db_latest ou archive) → business_logic rapport → réponse Pydantic.
"""
from __future__ import annotations
import logging

import polars as pl

from api.bi.schemas import TopClientsRequest, RapportResponse
from api.bi.repositories.factory_repo import get_bi_repo
from api.bi.repositories.archive_repo.base_bi_archive import safe_float_col
from api.bi.business_logic.rapport_calculations import calc_top_clients_rapport

logger = logging.getLogger("api.bi.use_cases.top_clients")


def execute(req: TopClientsRequest) -> RapportResponse:
    repo = get_bi_repo("top_clients", req.source_type)

    try:
        rows = repo.fetch(req)
    except FileNotFoundError as exc:
        raise exc
    except Exception as exc:
        logger.error("[BI/top_clients] Erreur repository (%s): %s", req.source_type, exc)
        raise

    if not rows:
        return RapportResponse(
            endpoint="/api/bi/top-clients",
            client_schema=req.client_schema,
            source=req.source_type,
            total_rows=0,
            data=[],
        )

    df = pl.from_dicts(rows, infer_schema_length=500)
    df = df.with_columns(
        safe_float_col(df, "do_totalht").alias("do_totalht_f")
    )

    data = calc_top_clients_rapport(df, None, req.limit)

    return RapportResponse(
        endpoint="/api/bi/top-clients",
        client_schema=req.client_schema,
        source=req.source_type,
        total_rows=len(data),
        data=data,
    )
