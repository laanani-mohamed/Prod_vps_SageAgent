"""
bi/stock/repositories/pg_repo/stock_snapshot_repo.py
"""
from typing import List, Dict, Any
from api.stock.repositories.base_repo import BaseStockRepository

class PgStockSnapshotRepository(BaseStockRepository):
    def fetch(self, req) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "Le snapshot de stock n'est pas supporté en direct sur PostgreSQL (live). "
            "Veuillez utiliser source_type='archive' pour requêter les états passés."
        )
