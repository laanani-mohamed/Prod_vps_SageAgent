"""
api/bi/repositories/pg_repo/bi_top_clients_repo.py

Repository PostgreSQL pour le top N clients.
"""
from typing import Tuple, List, Dict, Any

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema, add_date_range


class PgBITopClientsRepository(BaseBIRepository):
    """
    Repository pour le top clients (POST /api/bi/top-clients).
    Retourne F_DOCENTETE avec jointure F_COMPTET, filtré sur les factures vente.
    """

    def fetch(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_query, req, schema)
        return data

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        col_aliases = [
            "do_domaine", "do_type", "do_date",
            "do_totalht", "do_piece",
            "do_tiers", "ct_intitule",
        ]

        sql = f"""
SELECT
    e.do_domaine,
    e.do_type,
    CAST(e.do_date AS TEXT) AS do_date,
    e.do_totalht,
    e.do_piece,
    e.do_tiers,
    ct.ct_intitule
FROM {schema}.f_docentete e
LEFT JOIN {schema}.f_comptet ct ON ct.ct_num = e.do_tiers
WHERE e.do_domaine = 0 AND e.do_type IN (6, 7)""".strip()

        sql = add_date_range(sql, "e.do_date", req.date_from, req.date_to, params)

        return sql, params, col_aliases
