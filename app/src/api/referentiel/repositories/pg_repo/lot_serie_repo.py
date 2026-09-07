"""
bi/referentiel/repositories/pg_repo/lot_serie_repo.py
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_ilike, add_eq, add_gte, add_lte

class PgLotSerieRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        cols = [
            "ar_ref", "ar_design", "fa_codefamille",
            "ls_noserie", "ls_peremption", "ls_qte", "ls_qterestant", "ls_lotepuise",
            "de_no", "de_intitule", "jours_avant_peremption",
        ]
        sql = f"""
SELECT ls.ar_ref, a.ar_design, a.fa_codefamille,
       ls.ls_noserie, ls.ls_peremption, ls.ls_qte, ls.ls_qterestant, ls.ls_lotepuise,
       ls.de_no, d.de_intitule,
       (ls.ls_peremption::date - CURRENT_DATE) AS jours_avant_peremption
FROM {schema}.f_lotserie ls
JOIN {schema}.f_article a ON ls.ar_ref = a.ar_ref
LEFT JOIN {schema}.f_depot d ON ls.de_no = d.de_no
LEFT JOIN {schema}.f_famille f ON a.fa_codefamille = f.fa_codefamille
WHERE 1=1""".strip()

        if req.only_active:
            sql += " AND ls.ls_lotepuise = 0"
        else:
            sql = add_eq(sql, "ls.ls_lotepuise", req.ls_lotepuise, params)

        sql = add_in(sql, "ls.ar_ref", req.ar_ref, params)
        sql = add_in(sql, "a.fa_codefamille", req.fa_codefamille, params)
        sql = add_ilike(sql, "ls.ls_noserie", req.ls_noserie, params)
        sql = add_in(sql, "ls.de_no", req.de_no, params)
        sql = add_lte(sql, "ls.ls_peremption", req.peremption_before, params)
        sql = add_gte(sql, "ls.ls_peremption", req.peremption_after, params)
        sql = add_gte(sql, "ls.ls_qterestant", req.qte_restant_min, params)
        sql += f" ORDER BY ls.ls_peremption ASC NULLS LAST, ls.ar_ref ASC"
        return sql, params, cols
