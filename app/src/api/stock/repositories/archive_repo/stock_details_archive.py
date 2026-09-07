"""
bi/stock/repositories/archive_repo/stock_details_archive.py
"""
import os
import polars as pl
from typing import Dict, List, Any
from api.stock.repositories.archive_repo.base_archive import BaseArchiveStockRepository
from config.etl_config import ARCHIVE_BASE_PATH

class ArchiveStockDetailsRepository(BaseArchiveStockRepository):
    def fetch(self, req) -> Dict[str, List[Dict[str, Any]]]:
        df, ts = self._get_base_df(req)
        
        # Charger les lots depuis les archives s'ils existent
        archive_dir = os.path.join(ARCHIVE_BASE_PATH, req.client_schema)
        df_lots = self._load_archive_file(archive_dir, "F_LOTSERIE", ts)
        
        lots_data = []
        if df_lots is not None:
            # Filtrer les lots
            if req.ar_ref:
                df_lots = df_lots.filter(pl.col("ar_ref").is_in(req.ar_ref))
            if req.ar_design and "ar_design" in df.columns:
                matching_refs = df.select("ar_ref").unique().to_series().to_list()
                df_lots = df_lots.filter(pl.col("ar_ref").is_in(matching_refs))
            lots_data = df_lots.to_dicts()

        raw_stock = df.to_dicts()
        if raw_stock:
            raw_stock[0]["__source_timestamp__"] = ts
            
        return {
            "raw_stock": raw_stock,
            "lots_data": lots_data
        }
