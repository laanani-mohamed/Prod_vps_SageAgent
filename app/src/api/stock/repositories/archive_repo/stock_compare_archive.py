"""
bi/stock/repositories/archive_repo/stock_compare_archive.py
"""
from typing import List, Dict, Any
from api.stock.repositories.archive_repo.base_archive import BaseArchiveStockRepository

class ArchiveStockCompareRepository(BaseArchiveStockRepository):
    def fetch(self, req) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "La comparaison temporelle de stock est orchestrée directement "
            "dans le use-case en combinant deux requêtes de snapshot."
        )
