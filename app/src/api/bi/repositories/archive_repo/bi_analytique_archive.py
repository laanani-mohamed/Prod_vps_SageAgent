"""
api/bi/repositories/archive_repo/bi_analytique_archive.py

Repository archive pour les KPIs analytiques.
Fournit l'accès aux tables F_DOCENTETE, F_DOCLIGNE, F_COMPTET, F_FAMILLE.
"""
from typing import List, Dict, Any, Optional, Tuple
import polars as pl

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.archive_repo.base_bi_archive import (
    get_bi_archive_dir, find_bi_snapshot, load_bi_table,
)


class ArchiveBIAnalytiqueRepository(BaseBIRepository):

    def fetch(self, req) -> List[Dict[str, Any]]:
        """Retourne F_DOCENTETE (données brutes)."""
        archive_dir = get_bi_archive_dir(req.client_schema)
        ts = find_bi_snapshot(archive_dir, "F_DOCENTETE", None)
        if not ts:
            return []
        df = load_bi_table(archive_dir, "F_DOCENTETE", ts)
        return df.to_dicts() if df is not None else []

    def fetch_all_tables(self, client_schema: str) -> Tuple[
        Optional[pl.DataFrame],  # df_entete
        Optional[str],           # ts_e
        Optional[pl.DataFrame],  # df_docligne
        Optional[str],           # ts_dl
        Optional[pl.DataFrame],  # df_article
        Optional[pl.DataFrame],  # df_comptet
        Optional[pl.DataFrame],  # df_famille
    ]:
        """
        Charge toutes les tables nécessaires aux KPIs analytiques.
        Utilisé directement par analytique_uc quand source_type='archive'.
        """
        archive_dir = get_bi_archive_dir(client_schema)

        ts_e  = find_bi_snapshot(archive_dir, "F_DOCENTETE", None)
        ts_dl = find_bi_snapshot(archive_dir, "F_DOCLIGNE",  None)

        df_entete  = load_bi_table(archive_dir, "F_DOCENTETE", ts_e)  if ts_e  else None
        df_docligne= load_bi_table(archive_dir, "F_DOCLIGNE",  ts_dl) if ts_dl else None

        ts_art = find_bi_snapshot(archive_dir, "F_ARTICLE",  None)
        df_article = load_bi_table(archive_dir, "F_ARTICLE", ts_art) if ts_art else None

        ts_ct  = find_bi_snapshot(archive_dir, "F_COMPTET", None)
        df_ct  = load_bi_table(archive_dir, "F_COMPTET",  ts_ct)  if ts_ct  else None

        ts_fam = find_bi_snapshot(archive_dir, "F_FAMILLE", None)
        df_fam = load_bi_table(archive_dir, "F_FAMILLE",  ts_fam) if ts_fam else None

        return df_entete, ts_e, df_docligne, ts_dl, df_article, df_ct, df_fam
