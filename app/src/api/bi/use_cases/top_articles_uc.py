"""
api/bi/use_cases/top_articles_uc.py

Use Case : POST /api/bi/top-articles
Orchestre : factory_repo (db_latest ou archive) → business_logic rapport → réponse Pydantic.
"""
from __future__ import annotations
import logging

import polars as pl

from api.bi.schemas import TopArticlesRequest, RapportResponse
from api.bi.repositories.factory_repo import get_bi_repo
from api.bi.repositories.archive_repo.base_bi_archive import safe_float_col
from api.bi.business_logic.rapport_calculations import calc_top_articles_rapport

logger = logging.getLogger("api.bi.use_cases.top_articles")


def execute(req: TopArticlesRequest) -> RapportResponse:
    repo = get_bi_repo("top_articles", req.source_type)

    try:
        rows = repo.fetch(req)
    except FileNotFoundError as exc:
        raise exc
    except Exception as exc:
        logger.error("[BI/top_articles] Erreur repository (%s): %s", req.source_type, exc)
        raise

    if not rows:
        return RapportResponse(
            endpoint="/api/bi/top-articles",
            client_schema=req.client_schema,
            source=req.source_type,
            total_rows=0,
            data=[],
        )

    df = pl.from_dicts(rows, infer_schema_length=500)
    df = df.with_columns([
        safe_float_col(df, "dl_qte").alias("dl_qte_f"),
        safe_float_col(df, "dl_montantht").alias("dl_montantht_f"),
    ])

    # Filtre optionnel par famille
    if req.fa_codefamille:
        df = df.filter(pl.col("fa_codefamille").is_in(req.fa_codefamille))

    data = calc_top_articles_rapport(df, None)

    return RapportResponse(
        endpoint="/api/bi/top-articles",
        client_schema=req.client_schema,
        source=req.source_type,
        total_rows=len(data),
        data=data,
    )
