"""
bi/referentiel/repositories/pg_repo/doc_entete_repo.py
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_ilike, add_eq, add_gte, add_lte

class PgDocEnteteRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        cols = [
            "do_domaine", "do_type", "do_piece", "do_date", "do_ref",
            "do_tiers", "ct_intitule", "co_no", "co_nom", "co_prenom",
            "do_totalht", "do_totalhtnet", "do_totalttc", "do_montantregle", "reste_a_payer",
        ]
        sql = f"""
SELECT e.do_domaine, e.do_type, e.do_piece, e.do_date, e.do_ref,
       e.do_tiers, c.ct_intitule, e.co_no, col.co_nom, col.co_prenom,
       e.do_totalht, e.do_totalhtnet, e.do_totalttc,
       COALESCE(e.do_montantregle, 0)                                   AS do_montantregle,
       e.do_totalttc - COALESCE(e.do_montantregle, 0)                  AS reste_a_payer
FROM {schema}.f_docentete e
LEFT JOIN {schema}.f_comptet c ON e.do_tiers = c.ct_num
LEFT JOIN {schema}.f_collaborateur col ON e.co_no = col.co_no
WHERE 1=1""".strip()

        sql = add_in(sql, "e.do_domaine", req.do_domaine, params)
        sql = add_in(sql, "e.do_type", req.do_type, params)
        sql = add_in(sql, "e.do_piece", req.do_piece, params)
        sql = add_in(sql, "e.do_tiers", req.do_tiers, params)
        sql = add_in(sql, "e.co_no", req.co_no, params)
        sql = add_ilike(sql, "e.do_ref", req.do_ref, params)
        sql = add_eq(sql, "e.do_date", req.do_date, params)
        sql = add_gte(sql, "e.do_date", req.date_from, params)
        sql = add_lte(sql, "e.do_date", req.date_to, params)
        sql = add_gte(sql, "e.do_totalttc", req.do_totalttc_min, params)
        sql = add_lte(sql, "e.do_totalttc", req.do_totalttc_max, params)
        if req.montant_regle_unpaid:
            sql += " AND COALESCE(e.do_montantregle, 0) < e.do_totalttc"
        sql += f" ORDER BY e.do_date DESC, e.do_piece DESC"
        return sql, params, cols
