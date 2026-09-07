"""
bi/referentiel/repositories/pg_repo/famille_repo.py
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_ilike, add_eq

class PgFamilleRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        cols = ["fa_codefamille", "fa_intitule", "fa_type", "fa_suivistock", "fa_central", "u_intitule"]

        articles_join = ""
        if req.with_articles_count or req.with_articles_names:
            selects = []
            if req.with_articles_count:
                selects.append("COUNT(*) AS nb_articles")
                cols.append("nb_articles")
            if req.with_articles_names:
                selects.append("array_agg(DISTINCT ar_design) AS articles_names")
                cols.append("articles_names")
            select_str = ", ".join(selects)
            
            articles_join = f"""
LEFT JOIN (
    SELECT fa_codefamille, {select_str}
    FROM {schema}.f_article
    WHERE ar_sommeil = 0
    GROUP BY fa_codefamille
) art ON art.fa_codefamille = f.fa_codefamille"""

        sql = f"""
SELECT f.fa_codefamille, f.fa_intitule, f.fa_type, f.fa_suivistock, f.fa_central, u.u_intitule
       {', art.nb_articles' if req.with_articles_count else ''}
       {', art.articles_names' if req.with_articles_names else ''}
FROM {schema}.f_famille f
LEFT JOIN {schema}.p_unite u ON f.fa_uniteven = u.cbindice
{articles_join}
WHERE 1=1""".strip()

        sql = add_in(sql, "f.fa_codefamille", req.fa_codefamille, params)
        sql = add_ilike(sql, "f.fa_intitule", req.fa_intitule, params)
        sql = add_in(sql, "f.fa_type", req.fa_type, params)
        sql = add_eq(sql, "f.fa_central", req.fa_central, params)
        sql = add_in(sql, "f.fa_suivistock", req.fa_suivistock, params)
        sql += f" ORDER BY f.fa_codefamille ASC"
        return sql, params, cols
