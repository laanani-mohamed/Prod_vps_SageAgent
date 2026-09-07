"""
api/bi/repositories/archive_repo/bi_rapport_ca_archive.py
"""
from typing import List, Dict, Any, Optional, Tuple
import polars as pl

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.archive_repo.base_bi_archive import (
    get_bi_archive_dir, find_bi_snapshot, resolve_bi_target_dt, load_bi_table,
)


class ArchiveBIRapportCARepository(BaseBIRepository):

    def fetch(self, req) -> List[Dict[str, Any]]:
        archive_dir = get_bi_archive_dir(req.client_schema)
        target_dt = resolve_bi_target_dt(req)
        ts = find_bi_snapshot(archive_dir, "F_DOCENTETE", target_dt)
        if not ts:
            raise FileNotFoundError("Aucun snapshot F_DOCENTETE")
        df = load_bi_table(archive_dir, "F_DOCENTETE", ts)
        return df.to_dicts() if df is not None else []

    def fetch_all_tables(self, req) -> Tuple[
        Optional[str],           # ts
        Optional[pl.DataFrame],  # df_entete
        Optional[pl.DataFrame],  # df_col
        Optional[pl.DataFrame],  # df_tiers
    ]:
        """Charge F_DOCENTETE + F_COLLABORATEUR + F_COMPTET pour le rapport CA."""
        archive_dir = get_bi_archive_dir(req.client_schema)
        target_dt = resolve_bi_target_dt(req)
        ts = find_bi_snapshot(archive_dir, "F_DOCENTETE", target_dt)
        if not ts:
            raise FileNotFoundError("Aucun snapshot F_DOCENTETE")
        df_e     = load_bi_table(archive_dir, "F_DOCENTETE",     ts)
        df_col   = load_bi_table(archive_dir, "F_COLLABORATEUR", ts)
        df_tiers = load_bi_table(archive_dir, "F_COMPTET",       ts)
        return ts, df_e, df_col, df_tiers
