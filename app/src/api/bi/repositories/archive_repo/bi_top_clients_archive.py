"""
api/bi/repositories/archive_repo/bi_top_clients_archive.py
"""
from typing import List, Dict, Any, Optional, Tuple
import polars as pl

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.archive_repo.base_bi_archive import (
    get_bi_archive_dir, find_bi_snapshot, resolve_bi_target_dt, load_bi_table,
)


class ArchiveBITopClientsRepository(BaseBIRepository):

    def fetch(self, req) -> List[Dict[str, Any]]:
        archive_dir = get_bi_archive_dir(req.client_schema)
        target_dt = resolve_bi_target_dt(req)
        ts = find_bi_snapshot(archive_dir, "F_DOCENTETE", target_dt)
        if not ts:
            raise FileNotFoundError("Aucun snapshot F_DOCENTETE")
        df = load_bi_table(archive_dir, "F_DOCENTETE", ts)
        return df.to_dicts() if df is not None else []

    def fetch_with_tiers(self, req) -> Tuple[
        Optional[str],
        Optional[pl.DataFrame],
        Optional[pl.DataFrame],
    ]:
        """Retourne (ts, df_docentete, df_comptet)."""
        archive_dir = get_bi_archive_dir(req.client_schema)
        target_dt = resolve_bi_target_dt(req)
        ts = find_bi_snapshot(archive_dir, "F_DOCENTETE", target_dt)
        if not ts:
            raise FileNotFoundError("Aucun snapshot F_DOCENTETE")
        df_e     = load_bi_table(archive_dir, "F_DOCENTETE", ts)
        df_tiers = load_bi_table(archive_dir, "F_COMPTET",   ts)
        return ts, df_e, df_tiers
