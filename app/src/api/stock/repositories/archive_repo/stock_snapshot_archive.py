"""
bi/stock/repositories/archive_repo/stock_snapshot_archive.py
"""
from typing import List, Dict, Any
from api.stock.repositories.archive_repo.base_archive import BaseArchiveStockRepository

class ArchiveStockSnapshotRepository(BaseArchiveStockRepository):
    def fetch(self, req) -> List[Dict[str, Any]]:
        df, ts = self._get_base_df(req)
        data, _ = self._sort_and_limit(df, req)
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
