"""
api/bi/repositories/pg_repo/bi_rapport_ca_repo.py

Repository PostgreSQL pour le rapport CA.
Retourne F_DOCENTETE avec jointures tiers et collaborateur,
prêt pour le groupement par mois/client/commercial.
"""
from typing import Tuple, List, Dict, Any

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema, add_date_range


class PgBIRapportCARepository(BaseBIRepository):
    """
    Repository pour le rapport CA (POST /api/bi/rapport/ca).
    Retourne les données enrichies avec intitulé tiers et nom commercial.
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
            "ct_ville",
            "co_no", "co_fullname",
        ]

        sql = f"""
SELECT
    e.do_domaine,
    e.do_type,
    CAST(e.do_date AS TEXT) AS do_date,
    e.do_totalht,
    e.do_piece,
    e.do_tiers,
    ct.ct_intitule,
    ct.ct_ville,
    e.co_no,
    CASE 
        WHEN e.co_no = 0 THEN 'Non identifier' 
        ELSE COALESCE(col.co_nom || ' ' || col.co_prenom, 'Non identifier') 
    END AS co_fullname
FROM {schema}.f_docentete e
LEFT JOIN {schema}.f_comptet ct ON ct.ct_num = e.do_tiers
LEFT JOIN {schema}.f_collaborateur col ON col.co_no = e.co_no
WHERE e.do_domaine = 0 AND e.do_type IN (6, 7)""".strip()

        sql = add_date_range(sql, "e.do_date", req.date_from, req.date_to, params)

        return sql, params, col_aliases
