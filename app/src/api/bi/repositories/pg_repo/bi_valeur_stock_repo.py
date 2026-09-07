"""
api/bi/repositories/pg_repo/bi_valeur_stock_repo.py

Repository PostgreSQL pour le rapport Valeur du Stock.
Retourne le stock valorisé par dépôt/famille/article
en utilisant le dernier DL_CMUP (do_domaine=0) × qté f_artstock.
"""
from typing import Tuple, List, Dict, Any

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema


class PgBIValeurStockRepository(BaseBIRepository):

    def fetch(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_query, req, schema)
        return data

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        col_aliases = [
            "de_no", "de_intitule",
            "fa_codefamille", "fa_intitule",
            "ar_ref", "ar_design",
            "qte_stock", "prix_revient", "valeur_stock",
        ]

        sql = f"""
SELECT
    s.de_no, d.de_intitule,
    a.fa_codefamille, f.fa_intitule,
    a.ar_ref, a.ar_design,
    SUM(s.as_qtesto) AS qte_stock,
    COALESCE(dl_cmup.dernier_cmup, a.ar_prixach, 0) AS prix_revient,
    SUM(s.as_qtesto) * COALESCE(dl_cmup.dernier_cmup, a.ar_prixach, 0) AS valeur_stock
FROM {schema}.f_artstock s
JOIN {schema}.f_article a ON a.ar_ref = s.ar_ref
LEFT JOIN {schema}.f_depot d ON d.de_no = s.de_no
LEFT JOIN {schema}.f_famille f ON a.fa_codefamille = f.fa_codefamille
LEFT JOIN LATERAL (
    SELECT dl.dl_cmup AS dernier_cmup
    FROM {schema}.f_docligne dl
    WHERE dl.ar_ref = a.ar_ref AND dl.do_domaine = 0 AND dl.dl_cmup > 0
    ORDER BY dl.do_date DESC LIMIT 1
) dl_cmup ON true
WHERE s.as_qtesto > 0
GROUP BY s.de_no, d.de_intitule, a.fa_codefamille, f.fa_intitule,
         a.ar_ref, a.ar_design, dl_cmup.dernier_cmup, a.ar_prixach
ORDER BY d.de_intitule, f.fa_intitule, a.ar_design""".strip()

        return sql, params, col_aliases
