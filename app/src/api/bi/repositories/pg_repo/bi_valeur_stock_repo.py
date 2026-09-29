"""
api/bi/repositories/pg_repo/bi_valeur_stock_repo.py

Repository PostgreSQL pour le rapport Valeur du Stock.
Retourne le stock valorisé par dépôt/famille/article à partir du montant du stock
Sage (F_ARTSTOCK.AS_MontSto) :
  valeur_stock = Σ AS_MontSto (vide → 0)
  prix_revient = Σ AS_MontSto ÷ Σ qté (coût moyen)
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
    COALESCE(SUM(s.as_montsto) / NULLIF(SUM(s.as_qtesto), 0), 0) AS prix_revient,
    COALESCE(SUM(s.as_montsto), 0) AS valeur_stock
FROM {schema}.f_artstock s
JOIN {schema}.f_article a ON a.ar_ref = s.ar_ref
LEFT JOIN {schema}.f_depot d ON d.de_no = s.de_no
LEFT JOIN {schema}.f_famille f ON a.fa_codefamille = f.fa_codefamille
WHERE s.as_qtesto > 0
GROUP BY s.de_no, d.de_intitule, a.fa_codefamille, f.fa_intitule,
         a.ar_ref, a.ar_design
ORDER BY d.de_intitule, f.fa_intitule, a.ar_design""".strip()

        return sql, params, col_aliases
