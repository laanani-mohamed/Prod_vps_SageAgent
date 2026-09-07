"""
bi/referentiel/repositories/pg_repo/stock_depot_repo.py
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_eq, add_gte, add_lte

class PgStockDepotRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        cols = [
            "ar_ref", "ar_design", "fa_codefamille", "fa_intitule",
            "de_no", "de_intitule", "as_qtesto",
            "ar_prixach", "ar_prixven",
            "valeur_stock_achat", "valeur_stock_vente",
            "ar_suivistock", "ar_sommeil", "u_intitule",
        ]
        sql = f"""
SELECT stk.ar_ref, a.ar_design, a.fa_codefamille, f.fa_intitule,
       stk.de_no, d.de_intitule, stk.as_qtesto,
       a.ar_prixach, a.ar_prixven,
       stk.as_qtesto * COALESCE(a.ar_prixach, 0)  AS valeur_stock_achat,
       stk.as_qtesto * COALESCE(a.ar_prixven, 0)  AS valeur_stock_vente,
       a.ar_suivistock, a.ar_sommeil, u.u_intitule
FROM {schema}.f_artstock stk
JOIN {schema}.f_article a ON stk.ar_ref = a.ar_ref
LEFT JOIN {schema}.f_depot d ON stk.de_no = d.de_no
LEFT JOIN {schema}.f_famille f ON a.fa_codefamille = f.fa_codefamille
LEFT JOIN {schema}.p_unite u ON a.ar_uniteven = u.cbindice
WHERE 1=1""".strip()

        sql = add_in(sql, "stk.ar_ref", req.ar_ref, params)
        sql = add_in(sql, "stk.de_no", req.de_no, params)
        sql = add_in(sql, "a.fa_codefamille", req.fa_codefamille, params)
        sql = add_in(sql, "a.ar_suivistock", req.ar_suivistock, params)
        sql = add_eq(sql, "a.ar_sommeil", req.ar_sommeil, params)
        sql = add_gte(sql, "stk.as_qtesto", req.qte_min, params)
        sql = add_lte(sql, "stk.as_qtesto", req.qte_max, params)
        if req.only_rupture:
            sql += " AND stk.as_qtesto <= 0"
        sql += f" ORDER BY a.fa_codefamille ASC, a.ar_ref ASC, stk.de_no ASC"
        return sql, params, cols
