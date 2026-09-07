"""
api/bi/use_cases/dashboard_uc.py

Use Case : POST /api/bi/dashboard
Orchestre : factory_repo (db_latest ou archive) → business_logic → réponse Pydantic.
"""
from __future__ import annotations
import logging

import polars as pl

from api.bi.schemas import DashboardRequest, DashboardResponse, KPIData
from api.bi.repositories.factory_repo import get_bi_repo
from api.bi.repositories.archive_repo.base_bi_archive import safe_float_col
from api.bi.business_logic.kpi_calculations import (
    prepare_docentete,
    calc_chiffre_affaires,
    calc_ca_n_minus_1,
    calc_evolution_mensuelle,
    calc_encours_clients,
    calc_dettes_fournisseurs,
    calc_total_achats,
    calc_nb_clients_actifs,
    calc_valeur_stock,
)

logger = logging.getLogger("api.bi.use_cases.dashboard")


def execute(req: DashboardRequest) -> DashboardResponse:
    repo = get_bi_repo("dashboard", req.source_type)

    try:
        rows = repo.fetch(req)
    except FileNotFoundError as exc:
        raise exc
    except Exception as exc:
        logger.error("[BI/dashboard] Erreur repository (%s): %s", req.source_type, exc)
        raise

    kpis = KPIData()

    if rows:
        df_raw = pl.from_dicts(rows, infer_schema_length=500)
        df_e = prepare_docentete(df_raw)

        kpis.chiffre_affaires    = calc_chiffre_affaires(df_e, req.date_from, req.date_to)
        kpis.total_achats        = calc_total_achats(df_e, req.date_from, req.date_to)
        kpis.encours_clients     = calc_encours_clients(df_e)
        kpis.dettes_fournisseurs = calc_dettes_fournisseurs(df_e)
        kpis.nb_clients_actifs   = calc_nb_clients_actifs(df_e, req.date_from, req.date_to)
        kpis.ca_evolution_monthly = calc_evolution_mensuelle(df_e, req.date_from, req.date_to)

        if req.date_from and req.date_to:
            kpis.ca_n_minus_1 = calc_ca_n_minus_1(df_e, req.date_from, req.date_to)
            if kpis.ca_n_minus_1 > 0:
                kpis.ca_evolution_pct = round(
                    (kpis.chiffre_affaires - kpis.ca_n_minus_1) / kpis.ca_n_minus_1 * 100, 1
                )

    # Valorisation du stock (méthode spécifique du repo PG)
    try:
        stock_rows = repo.fetch_stock(req)
        if stock_rows:
            df_stock_raw = pl.from_dicts(stock_rows, infer_schema_length=500)
            df_stock = df_stock_raw.with_columns([
                safe_float_col(df_stock_raw, "as_qtesto").alias("as_qtesto_f"),
                safe_float_col(df_stock_raw, "ar_prixach").alias("ar_prixach_f"),
            ])
            kpis.valeur_stock = float(
                (df_stock["as_qtesto_f"] * df_stock["ar_prixach_f"]).sum() or 0
            )
    except Exception as exc:
        logger.warning("[BI/dashboard] Valorisation stock non disponible : %s", exc)

    return DashboardResponse(
        client_schema=req.client_schema,
        source=req.source_type,
        date_from=req.date_from,
        date_to=req.date_to,
        kpis=kpis,
    )
