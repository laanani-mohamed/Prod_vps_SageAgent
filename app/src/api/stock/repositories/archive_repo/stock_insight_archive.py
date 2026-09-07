"""
bi/stock/repositories/archive_repo/stock_insight_archive.py
"""
import os
import polars as pl
from typing import List, Dict, Any
from api.stock.repositories.archive_repo.base_archive import BaseArchiveStockRepository
from config.etl_config import ARCHIVE_BASE_PATH

class ArchiveStockInsightRepository(BaseArchiveStockRepository):
    def fetch(self, req) -> List[Dict[str, Any]]:
        df, ts = self._get_base_df(req)
        
        if req.insight_type == "expiration":
            archive_dir = os.path.join(ARCHIVE_BASE_PATH, req.client_schema)
            df_lots = self._load_archive_file(archive_dir, "F_LOTSERIE", ts)
            if df_lots is not None:
                df_art = df.select(["ar_ref", "ar_design", "fa_codefamille"]).unique("ar_ref")
                df_lots = df_lots.join(df_art, on="ar_ref", how="inner")
                data = df_lots.to_dicts()
            else:
                data = []
        else:
            data = df.to_dicts()
            
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
