"""
api/bi/use_cases/objectifs_uc.py

Use Case : GET /api/bi/dashboard/objectifs
Orchestre : repository PG (db_latest) → calculs objectifs → réponse Pydantic.
"""
from __future__ import annotations
import logging
from datetime import date

import polars as pl

from api.bi.schemas import ObjectifsResponse, ObjectifItem
from api.bi.repositories.pg_repo.bi_dashboard_repo import PgBIDashboardRepository
from api.bi.business_logic.kpi_calculations import prepare_docentete
from api.bi.repositories.archive_repo.base_bi_archive import safe_float_col

logger = logging.getLogger("api.bi.use_cases.objectifs")

# Constantes métier
OBJECTIF_CA    = 25_000_000.0   # MAD
LIMITE_ENCOURS = 30_000_000.0  # MAD
SEUIL_CA_WARN  = 60.0          # % → alerte si CA < 60 % de l'objectif
SEUIL_ENC_WARN = 50.0          # % → alerte si encours > 50 % de la limite


def execute(client_schema: str) -> ObjectifsResponse:
    ca_mois    = 0.0
    encours    = 0.0
    marge_mois = 0.0
    pct_marge  = 0.0

    try:
        # Créer une requête fictive pour le repo
        class _Req:
            def __init__(self):
                self.client_schema = client_schema
                self.date_from = None
                self.date_to   = None
                self.source_type = "db_latest"

        req = _Req()
        repo = PgBIDashboardRepository()

        rows = repo.fetch(req)
        if rows:
            df_raw = pl.from_dicts(rows, infer_schema_length=500)
            df_e = prepare_docentete(df_raw)

            today = date.today()
            ytd_from = today.replace(month=1, day=1).isoformat()
            ytd_to   = today.isoformat()

            # ── CA YTD ──────────────────────────────────────────────────────
            df_ytd = df_e.filter(
                (pl.col("do_date").cast(pl.Utf8) >= ytd_from) &
                (pl.col("do_date").cast(pl.Utf8) <= ytd_to)
            )
            df_ca = df_ytd.filter(
                (pl.col("do_domaine") == 0) & (pl.col("do_type").is_in([6, 7]))
            )
            ca_mois = float(df_ca["do_totalht_f"].sum() or 0.0)

            # ── Encours all-time ─────────────────────────────────────────────
            df_enc_base = df_e.filter(
                (pl.col("do_domaine") == 0) & (pl.col("do_type").is_in([6, 7]))
            )
            df_enc = df_enc_base.with_columns(
                (pl.col("do_totalttc_f") - pl.col("do_montantregle_f")).alias("reste")
            ).filter(pl.col("reste") > 0)
            encours = float(df_enc["reste"].sum() or 0.0)

            # ── Achats YTD + Marge ────────────────────────────────────────────
            df_ach = df_ytd.filter(
                (pl.col("do_domaine") == 1) & pl.col("do_type").is_in([16, 17])
            )
            achats_mois = float(df_ach["do_totalht_f"].sum() or 0.0)
            marge_mois  = ca_mois - achats_mois
            pct_marge   = round(marge_mois / ca_mois * 100, 1) if ca_mois > 0.0 else 0.0

    except Exception as exc:
        logger.warning("[BI/objectifs] Erreur chargement données : %s", exc)

    # ── Évaluation des statuts ──────────────────────────────────────────────
    pct_ca  = round(ca_mois / OBJECTIF_CA * 100, 1)    if OBJECTIF_CA   > 0 else 0.0
    pct_enc = round(encours / LIMITE_ENCOURS * 100, 1)  if LIMITE_ENCOURS > 0 else 0.0

    statut_ca  = "ok" if pct_ca  >= SEUIL_CA_WARN  else ("warning" if pct_ca  > 40.0 else "danger")
    statut_enc = "ok" if pct_enc <= SEUIL_ENC_WARN  else ("warning" if pct_enc < 60.0 else "danger")

    def to_m_str(val: float) -> str:
        return f"{val / 1_000_000:.3f}".replace(".", ",") + " MMAD"

    objectifs = [
        ObjectifItem(
            axe="Performance Commerciale",
            objectif=f"CA annuel ≥ {to_m_str(OBJECTIF_CA)}",
            realise=to_m_str(ca_mois),
            pct_atteinte=pct_ca,
            seuil_alerte="Critique si ≤ 40 %, Alerte si < 60 %",
            statut=statut_ca,
        ),
        ObjectifItem(
            axe="Encours Clients",
            objectif=f"Encours ≤ {to_m_str(LIMITE_ENCOURS)}",
            realise=to_m_str(encours),
            pct_atteinte=pct_enc,
            seuil_alerte="Alerte si > 50 %, Critique si ≥ 60 %",
            statut=statut_enc,
        ),
        ObjectifItem(
            axe="Marge Brute Globale & Taux de Marge",
            objectif="Suivi de la rentabilité YTD",
            realise=to_m_str(marge_mois),
            pct_atteinte=pct_marge,
            seuil_alerte="",
            statut="neutral",
        ),
    ]
    return ObjectifsResponse(client_schema=client_schema, objectifs=objectifs)
