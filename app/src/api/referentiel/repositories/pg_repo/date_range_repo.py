"""
api/referentiel/repositories/pg_repo/date_range_repo.py

MIN/MAX de do_date pour borner les filtres de date du dashboard (une seule ligne renvoyée).
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in


class PgDateRangeRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        table = req.table or "docentete"

        if table == "docligne":
            alias, date_col = "l", "l.do_date"
            source = f"{schema}.f_docligne l"
        elif table == "reglement":
            # La date filtrée sur les règlements est celle de l'entête du document réglé
            alias, date_col = "r", "e.do_date"
            source = (f"{schema}.f_reglech r JOIN {schema}.f_docentete e ON e.do_domaine = r.do_domaine "
                      f"AND e.do_type = r.do_type AND e.do_piece = r.do_piece")
        else:
            alias, date_col = "e", "e.do_date"
            source = f"{schema}.f_docentete e"

        sql = f"""
SELECT CAST(MIN({date_col}) AS DATE) AS date_min, CAST(MAX({date_col}) AS DATE) AS date_max
FROM {source}
WHERE 1=1""".strip()

        sql = add_in(sql, f"{alias}.do_domaine", req.do_domaine, params)
        sql = add_in(sql, f"{alias}.do_type", req.do_type, params)
        if table == "docligne":
            sql = add_in(sql, "l.ar_ref", req.ar_ref, params)
        return sql, params, ["date_min", "date_max"]
