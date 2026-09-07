"""
bi/referentiel/repositories/pg_repo/reglement_repo.py
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_ilike, add_eq, add_gte, add_lte

class PgReglementRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        cols = [
            "rg_no", "dr_no", "do_domaine", "do_type", "do_piece", "rc_montant", "rg_typereg",
            "do_date", "do_tiers", "ct_intitule", "ct_identifiant"
        ]
        sql = f"""
SELECT r.rg_no, r.dr_no, r.do_domaine, r.do_type, r.do_piece, r.rc_montant, r.rg_typereg,
       e.do_date, e.do_tiers, c.ct_intitule, c.ct_identifiant
FROM {schema}.f_reglech r
LEFT JOIN {schema}.f_docentete e ON r.do_piece = e.do_piece
LEFT JOIN {schema}.f_comptet c ON e.do_tiers = c.ct_num
WHERE 1=1""".strip()

        sql = add_in(sql, "r.do_domaine", req.do_domaine, params)
        sql = add_in(sql, "r.do_type", req.do_type, params)
        sql = add_in(sql, "r.do_piece", req.do_piece, params)
        sql = add_in(sql, "r.rg_typereg", req.rg_typereg, params)
        sql = add_gte(sql, "e.do_date", req.date_from, params)
        sql = add_lte(sql, "e.do_date", req.date_to, params)

        sql += f" ORDER BY e.do_date DESC, r.rg_no DESC"
        return sql, params, cols
