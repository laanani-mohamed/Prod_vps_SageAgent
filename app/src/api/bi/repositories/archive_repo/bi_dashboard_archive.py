"""
api/bi/repositories/archive_repo/bi_dashboard_archive.py

Repository archive pour le Dashboard BI.
Charge F_DOCENTETE, F_ARTSTOCK, F_ARTICLE depuis les snapshots.
"""
from typing import List, Dict, Any
import polars as pl

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.archive_repo.base_bi_archive import (
    get_bi_archive_dir, find_bi_snapshot, resolve_bi_target_dt, load_bi_table,
)


class ArchiveBIDashboardRepository(BaseBIRepository):
    """
    Charge les tables nécessaires au dashboard depuis les archives.
    Retourne un dict spécial avec les 3 DataFrames nécessaires.
    """

    def fetch(self, req) -> List[Dict[str, Any]]:
        """
        Retourne les lignes de F_DOCENTETE (données brutes).
        Le use case dashboard_uc charge séparément stock et article.
        """
        archive_dir = get_bi_archive_dir(req.client_schema)
        target_dt = resolve_bi_target_dt(req)
        ts = find_bi_snapshot(archive_dir, "F_DOCENTETE", target_dt)
        if not ts:
            raise FileNotFoundError(
                f"Aucun snapshot F_DOCENTETE dans les archives du schéma '{req.client_schema}'"
            )
        df = load_bi_table(archive_dir, "F_DOCENTETE", ts)
        return df.to_dicts() if df is not None else []

    def fetch_with_ts(self, req):
        """
        Retourne (ts, df_entete, df_stock, df_article) pour le use case dashboard.
        Utilisé directement par le use case quand source_type='archive'.
        """
        archive_dir = get_bi_archive_dir(req.client_schema)
        target_dt = resolve_bi_target_dt(req)
        ts = find_bi_snapshot(archive_dir, "F_DOCENTETE", target_dt)
        if not ts:
            raise FileNotFoundError(
                f"Aucun snapshot F_DOCENTETE dans les archives du schéma '{req.client_schema}'"
            )
        df_entete  = load_bi_table(archive_dir, "F_DOCENTETE", ts)
        df_stock   = load_bi_table(archive_dir, "F_ARTSTOCK",  ts)
        df_article = load_bi_table(archive_dir, "F_ARTICLE",   ts)
        return ts, df_entete, df_stock, df_article
