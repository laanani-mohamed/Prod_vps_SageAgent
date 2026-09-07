"""
api/bi/repositories/pg_repo/bi_balance_repo.py

Repository PostgreSQL pour le rapport Balance Client.
Retourne F_DOCENTETE (factures) avec jointures tiers pour calculer l'encours et les arriérés.
"""
from typing import Tuple, List, Dict, Any

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema


class PgBIBalanceClientRepository(BaseBIRepository):
    """
    Repository pour la balance client (POST /api/bi/rapport/balance).
    """

    def fetch(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_query, req, schema)
        return data

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        col_aliases = [
            "do_piece", "do_date", "do_tiers", "ct_intitule",
            "do_totalttc", "do_montantregle", "reste_a_payer"
        ]

        # On filtre les factures (DO_Type = 6) qui ont un reste à payer
        # DO_Domaine = 0 (Ventes)
        sql = f"""
SELECT
    e.do_piece,
    CAST(e.do_date AS TEXT) AS do_date,
    e.do_tiers,
    COALESCE(ct.ct_intitule, 'Non identifier') AS ct_intitule,
    COALESCE(e.do_totalttc, 0) AS do_totalttc,
    COALESCE(e.do_montantregle, 0) AS do_montantregle,
    COALESCE(e.do_totalttc, 0) - COALESCE(e.do_montantregle, 0) AS reste_a_payer
FROM {schema}.f_docentete e
LEFT JOIN {schema}.f_comptet ct ON ct.ct_num = e.do_tiers
WHERE e.do_domaine = 0 
  AND e.do_type IN (6, 7)
  AND ROUND(CAST(COALESCE(e.do_totalttc, 0) - COALESCE(e.do_montantregle, 0) AS NUMERIC), 2) > 0
""".strip()

        return sql, params, col_aliases
