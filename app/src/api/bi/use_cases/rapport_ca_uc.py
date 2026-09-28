"""
api/bi/use_cases/rapport_ca_uc.py

Use Case : POST /api/bi/rapport/ca
Orchestre : factory_repo (db_latest ou archive) → business_logic rapport → réponse Pydantic.
"""
from __future__ import annotations
import logging

import polars as pl

from api.bi.schemas import RapportCARequest, RapportResponse
from api.bi.repositories.factory_repo import get_bi_repo
from api.bi.repositories.archive_repo.base_bi_archive import safe_float_col
from api.bi.business_logic.rapport_calculations import (
    group_ca_par_mois,
    group_ca_par_client,
    group_ca_par_commercial,
    group_ca_par_region,
)

logger = logging.getLogger("api.bi.use_cases.rapport_ca")


def execute(req: RapportCARequest) -> RapportResponse:
    repo = get_bi_repo("rapport_ca", req.source_type)

    try:
        rows = repo.fetch(req)
    except FileNotFoundError as exc:
        raise exc
    except Exception as exc:
        logger.error("[BI/rapport_ca] Erreur repository (%s): %s", req.source_type, exc)
        raise

    if not rows:
        return RapportResponse(
            endpoint="/api/bi/rapport/ca",
            client_schema=req.client_schema,
            source=req.source_type,
            total_rows=0,
            data=[],
        )

    # ── Convertir en DataFrame Polars (attendu par business_logic) ───────────
    df = pl.from_dicts(rows, infer_schema_length=500)

    # Ajouter la colonne do_totalht_f (float) attendue par les fonctions de groupement
    df = df.with_columns(
        safe_float_col(df, "do_totalht").alias("do_totalht_f")
    )

    # ── Groupement ───────────────────────────────────────────────────────────
    if req.group_by == "client":
        data = group_ca_par_client(df)
    elif req.group_by == "commercial":
        data = group_ca_par_commercial(df)
    elif req.group_by == "region":
        data = group_ca_par_region(df)
    else:
        data = group_ca_par_mois(df)

    return RapportResponse(
        endpoint="/api/bi/rapport/ca",
        client_schema=req.client_schema,
        source=req.source_type,
        total_rows=len(data),
        data=data,
    )
