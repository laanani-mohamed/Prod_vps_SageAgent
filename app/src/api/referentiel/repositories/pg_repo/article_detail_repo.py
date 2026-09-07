"""
bi/referentiel/repositories/pg_repo/article_detail_repo.py
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_ilike, add_eq

class PgArticleDetailRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        cols = [
            "ar_ref", "ar_design", "fa_codefamille", "fa_intitule", "u_intitule",
            "ar_prixach", "ar_prixven", "ar_prixttc", "ar_codebarre",
            "ar_punet", "ar_coutstd", "ar_type", "ar_nature", "ar_sommeil", "ar_suivistock",
        ]

        stock_join = ""
        if req.with_stock:
            depot_filter = ""
            if req.depot_ids:
                placeholders = ", ".join(["%s"] * len(req.depot_ids))
                params.extend(req.depot_ids)
                depot_filter = f"WHERE de_no IN ({placeholders})"
            stock_join = f"""
LEFT JOIN (
    SELECT ar_ref, SUM(as_qtesto) AS qte_stock_totale
    FROM {schema}.f_artstock
    {depot_filter}
    GROUP BY ar_ref
) stk ON stk.ar_ref = a.ar_ref"""
            cols.append("qte_stock_totale")

        lots_join = ""
        if req.with_lots:
            lots_join = f"""
LEFT JOIN (
    SELECT ar_ref,
      COUNT(*) FILTER (WHERE ls_lotepuise = 0)              AS lots_actifs,
      COUNT(*) FILTER (WHERE ls_lotepuise = 1)              AS lots_perimes,
      MIN(ls_peremption) FILTER (WHERE ls_lotepuise = 0)    AS prochaine_peremption
    FROM {schema}.f_lotserie
    GROUP BY ar_ref
) lots ON lots.ar_ref = a.ar_ref"""
            cols += ["lots_actifs", "lots_perimes", "prochaine_peremption"]

        sql = f"""
SELECT a.ar_ref, a.ar_design, a.fa_codefamille, f.fa_intitule, u.u_intitule,
       a.ar_prixach, a.ar_prixven, a.ar_prixttc, a.ar_codebarre,
       a.ar_punet, a.ar_coutstd, a.ar_type, a.ar_nature, a.ar_sommeil, a.ar_suivistock
       {', stk.qte_stock_totale' if req.with_stock else ''}
       {', lots.lots_actifs, lots.lots_perimes, lots.prochaine_peremption' if req.with_lots else ''}
FROM {schema}.f_article a
LEFT JOIN {schema}.f_famille f ON a.fa_codefamille = f.fa_codefamille
LEFT JOIN {schema}.p_unite u ON a.ar_uniteven = u.cbindice
{stock_join}
{lots_join}
WHERE 1=1""".strip()

        sql = add_ilike(sql, "a.ar_ref", req.ar_ref, params)
        sql = add_in(sql, "a.ar_ref", req.ar_ref_exact, params)
        if req.ar_design:
            or_clauses = " OR ".join(["LOWER(a.ar_design::text) LIKE LOWER(%s)"] * len(req.ar_design))
            params.extend([f"%{v}%" for v in req.ar_design])
            sql += f" AND ({or_clauses})"
        sql = add_eq(sql, "a.ar_codebarre", req.ar_code_barre, params)
        sql = add_in(sql, "a.fa_codefamille", req.fa_codefamille, params)
        sql = add_in(sql, "a.ar_nature", req.ar_nature, params)
        sql = add_in(sql, "a.ar_type", req.ar_type, params)
        sql = add_in(sql, "a.ar_suivistock", req.ar_suivistock, params)
        sql = add_eq(sql, "a.ar_sommeil", req.ar_sommeil, params)
        sql += f" ORDER BY a.fa_codefamille ASC, a.ar_ref ASC"
        return sql, params, cols
