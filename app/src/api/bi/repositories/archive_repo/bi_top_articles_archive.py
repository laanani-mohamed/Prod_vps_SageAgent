"""
api/bi/repositories/archive_repo/bi_top_articles_archive.py
"""
from typing import List, Dict, Any, Optional, Tuple
import polars as pl

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.archive_repo.base_bi_archive import (
    get_bi_archive_dir, find_bi_snapshot, resolve_bi_target_dt, load_bi_table,
)


class ArchiveBITopArticlesRepository(BaseBIRepository):

    def fetch(self, req) -> List[Dict[str, Any]]:
        archive_dir = get_bi_archive_dir(req.client_schema)
        target_dt = resolve_bi_target_dt(req)
        ts = find_bi_snapshot(archive_dir, "F_DOCLIGNE", target_dt)
        if not ts:
            raise FileNotFoundError("Aucun snapshot F_DOCLIGNE")
        df = load_bi_table(archive_dir, "F_DOCLIGNE", ts)
        return df.to_dicts() if df is not None else []

    def fetch_with_article(self, req) -> Tuple[
        Optional[str],
        Optional[pl.DataFrame],
        Optional[pl.DataFrame],
    ]:
        """Retourne (ts, df_docligne, df_article)."""
        archive_dir = get_bi_archive_dir(req.client_schema)
        target_dt = resolve_bi_target_dt(req)
        ts = find_bi_snapshot(archive_dir, "F_DOCLIGNE", target_dt)
        if not ts:
            raise FileNotFoundError("Aucun snapshot F_DOCLIGNE")
        df_l = load_bi_table(archive_dir, "F_DOCLIGNE", ts)
        df_a = load_bi_table(archive_dir, "F_ARTICLE",  ts)
        return ts, df_l, df_a
