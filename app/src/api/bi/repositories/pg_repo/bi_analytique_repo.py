"""
api/bi/repositories/pg_repo/bi_analytique_repo.py

Repository PostgreSQL pour les KPIs analytiques avancés.
Fournit des méthodes séparées pour F_DOCENTETE et F_DOCLIGNE
(chaque table est chargée indépendamment par le use case analytique).
"""
from typing import Tuple, List, Dict, Any

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema, add_date_range


class PgBIAnalytiqueRepository(BaseBIRepository):
    """
    Repository pour les KPIs analytiques avancés (DSO, Marge, Top Clients...).
    fetch() retourne F_DOCENTETE. fetch_docligne() retourne F_DOCLIGNE.
    """

    def fetch(self, req) -> List[Dict[str, Any]]:
        """Retourne F_DOCENTETE pour la période donnée (YTD)."""
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_docentete_query, req, schema)
        return data

    def fetch_docligne(self, req) -> List[Dict[str, Any]]:
        """Retourne F_DOCLIGNE avec jointure F_ARTICLE pour le calcul de marge."""
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_docligne_query, req, schema)
        return data

    def fetch_comptet(self, req) -> List[Dict[str, Any]]:
        """Retourne F_COMPTET (intitulés clients/fournisseurs)."""
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_comptet_query, req, schema)
        return data

    def fetch_famille(self, req) -> List[Dict[str, Any]]:
        """Retourne F_FAMILLE (intitulés des familles d'articles)."""
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_famille_query, req, schema)
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

    def _build_docligne_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        col_aliases = [
            "do_domaine", "do_type", "do_date",
            "ar_ref", "dl_montantht", "dl_qtebl", "dl_prixru", "dl_cmup",
            "ct_num", "fa_codefamille", "ar_prixach", "ar_design",
            "dl_design",
        ]

        sql = f"""
SELECT
    l.do_domaine,
    l.do_type,
    CAST(l.do_date AS TEXT) AS do_date,
    l.ar_ref,
    l.dl_montantht,
    l.dl_qtebl,
    l.dl_prixru,
    l.dl_cmup,
    e.do_tiers AS ct_num,
    a.fa_codefamille,
    a.ar_prixach,
    a.ar_design,
    l.dl_design
FROM {schema}.f_docligne l
LEFT JOIN {schema}.f_docentete e ON e.do_piece = l.do_piece
    AND e.do_domaine = l.do_domaine AND e.do_type = l.do_type
LEFT JOIN {schema}.f_article a ON a.ar_ref = l.ar_ref
WHERE 1=1""".strip()

        return sql, params, col_aliases

    def _build_comptet_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        col_aliases = ["ct_num", "ct_intitule"]
        sql = f"""
SELECT ct_num, ct_intitule
FROM {schema}.f_comptet
WHERE 1=1""".strip()
        return sql, params, col_aliases

    def _build_famille_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        col_aliases = ["fa_codefamille", "fa_intitule"]
        sql = f"""
SELECT fa_codefamille, fa_intitule
FROM {schema}.f_famille
WHERE 1=1""".strip()
        return sql, params, col_aliases
