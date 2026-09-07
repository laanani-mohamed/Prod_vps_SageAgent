"""
api/bi/repositories/pg_repo/bi_dashboard_repo.py

Repository PostgreSQL pour le Dashboard BI.
Retourne les données brutes de F_DOCENTETE, F_ARTSTOCK, F_ARTICLE
nécessaires au calcul des KPIs du tableau de bord.
"""
from typing import Tuple, List, Dict, Any

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema, add_date_range


class PgBIDashboardRepository(BaseBIRepository):
    """
    Récupère F_DOCENTETE en temps réel depuis PostgreSQL pour le dashboard.
    Les colonnes retournées correspondent exactement à ce qu'attend
    business_logic/kpi_calculations.py.
    """

    def fetch(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_docentete_query, req, schema)
        return data

    def fetch_stock(self, req) -> List[Dict[str, Any]]:
        """Récupère F_ARTSTOCK × F_ARTICLE pour la valorisation du stock."""
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_stock_query, req, schema)
        return data

    def _build_docentete_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        col_aliases = [
            "do_domaine", "do_type", "do_date",
            "do_totalht", "do_totalttc", "do_montantregle",
            "do_tiers", "do_piece",
        ]

        sql = f"""
SELECT
    e.do_domaine,
    e.do_type,
    CAST(e.do_date AS TEXT) AS do_date,
    e.do_totalht,
    e.do_totalttc,
    e.do_montantregle,
    e.do_tiers,
    e.do_piece
FROM {schema}.f_docentete e
WHERE 1=1""".strip()

        return sql, params, col_aliases

    def _build_stock_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        col_aliases = ["ar_ref", "as_qtesto", "ar_prixach"]

        sql = f"""
SELECT
    a.ar_ref,
    s.as_qtesto,
    a.ar_prixach
FROM {schema}.f_article a
LEFT JOIN {schema}.f_artstock s ON s.ar_ref = a.ar_ref
WHERE 1=1""".strip()

        return sql, params, col_aliases
