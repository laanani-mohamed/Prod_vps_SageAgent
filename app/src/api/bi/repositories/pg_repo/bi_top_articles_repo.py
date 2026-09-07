"""
api/bi/repositories/pg_repo/bi_top_articles_repo.py

Repository PostgreSQL pour le top N articles vendus.
"""
from typing import Tuple, List, Dict, Any

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema, add_date_range, add_in


class PgBITopArticlesRepository(BaseBIRepository):
    """
    Repository pour le top articles (POST /api/bi/top-articles).
    Retourne F_DOCLIGNE avec jointure F_ARTICLE, filtré sur les factures vente.
    """

    def fetch(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_query, req, schema)
        return data

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        col_aliases = [
            "do_domaine", "do_type", "do_date",
            "ar_ref", "ar_design",
            "dl_qte", "dl_montantht",
            "fa_codefamille",
        ]

        sql = f"""
SELECT
    l.do_domaine,
    l.do_type,
    CAST(l.do_date AS TEXT) AS do_date,
    l.ar_ref,
    a.ar_design,
    l.dl_qte,
    l.dl_montantht,
    a.fa_codefamille
FROM {schema}.f_docligne l
LEFT JOIN {schema}.f_article a ON a.ar_ref = l.ar_ref
WHERE l.do_domaine = 0 AND l.do_type IN (6, 7)
  AND l.ar_ref IS NOT NULL""".strip()

        sql = add_date_range(sql, "l.do_date", req.date_from, req.date_to, params)

        # Filtre optionnel par famille
        fa_filter = getattr(req, "fa_codefamille", None)
        if fa_filter:
            sql = add_in(sql, "a.fa_codefamille", fa_filter, params)

        return sql, params, col_aliases
