"""
api/bi/repositories/pg_repo/bi_consommation_repo.py

Repository PostgreSQL pour la consommation d'articles par famille/produit
(POST /api/bi/rapport/consommation). Lignes de factures de vente jointes
à F_ARTICLE/F_FAMILLE — même modèle que bi_top_articles_repo.py (lecture
de do_domaine/do_type/do_date dénormalisés sur F_DOCLIGNE, pas de JOIN
F_DOCENTETE).
"""
from typing import Tuple, List, Dict, Any

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema, add_date_range


class PgBIConsommationRepository(BaseBIRepository):
    """
    Repository pour la consommation d'articles (POST /api/bi/rapport/consommation).
    Retourne F_DOCLIGNE avec jointure F_ARTICLE/F_FAMILLE, filtré sur les factures vente.
    """

    def fetch(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_query, req, schema)
        return data

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        col_aliases = [
            "ar_ref", "ar_design", "fa_codefamille", "fa_intitule",
            "do_date", "do_type", "dl_qte",
        ]

        sql = f"""
SELECT
    l.ar_ref,
    a.ar_design,
    COALESCE(a.fa_codefamille, '__SANS__') AS fa_codefamille,
    COALESCE(f.fa_intitule,    'Sans famille') AS fa_intitule,
    CAST(l.do_date AS TEXT) AS do_date,
    l.do_type,
    l.dl_qte
FROM {schema}.f_docligne l
LEFT JOIN {schema}.f_article a ON a.ar_ref = l.ar_ref
LEFT JOIN {schema}.f_famille f ON f.fa_codefamille = a.fa_codefamille
WHERE l.do_domaine = 0 AND l.do_type IN (6, 7)
  AND l.ar_ref IS NOT NULL""".strip()

        sql = add_date_range(sql, "l.do_date", req.date_from, req.date_to, params)

        return sql, params, col_aliases
