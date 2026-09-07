"""
bi/stock/repositories/pg_repo/stock_compare_repo.py
"""
from typing import List, Dict, Any
from api.stock.repositories.base_repo import BaseStockRepository

class PgStockCompareRepository(BaseStockRepository):
    def fetch(self, req) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "La comparaison temporelle de stock nécessite des données historiques. "
            "Veuillez utiliser source_type='archive'."
        )
