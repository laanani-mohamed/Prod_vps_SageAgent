"""
bi/referentiel/repositories/pg_repo/doc_ligne_repo.py
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_ilike, add_eq, add_gte, add_lte

class PgDocLigneRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        cols = [
            "do_domaine", "do_type", "ct_num", "ct_intitule",
            "do_piece", "dl_piecebc", "dl_piecebl", "do_date", "do_ref",
            "dl_ligne", "ar_ref", "ar_design_catalogue", "dl_design",
            "dl_qte", "dl_prixunitaire", "dl_montantht", "dl_montantttc",
            "dl_cmup", "dl_nonlivre", "dl_valorise", "co_no", "co_nom",
        ]

        entete_join = ""
        entete_cols = ""
        if req.with_entete:
            entete_join = f"""
LEFT JOIN {schema}.f_docentete e ON l.do_piece = e.do_piece
  AND l.do_domaine = e.do_domaine"""
            entete_cols = """,
       e.do_totalht, e.do_totalttc,
       COALESCE(e.do_montantregle, 0)                                   AS do_montantregle,
       e.do_totalttc - COALESCE(e.do_montantregle, 0)                  AS reste_a_payer"""
            cols += ["do_totalht", "do_totalttc", "do_montantregle", "reste_a_payer"]

        sql = f"""
SELECT l.do_domaine, l.do_type, l.ct_num, c.ct_intitule,
       l.do_piece, l.dl_piecebc, l.dl_piecebl, l.do_date, l.do_ref,
       l.dl_ligne, l.ar_ref, a.ar_design AS ar_design_catalogue, l.dl_design,
       l.dl_qte, l.dl_prixunitaire, l.dl_montantht, l.dl_montantttc,
       l.dl_cmup, l.dl_nonlivre, l.dl_valorise, l.co_no, col.co_nom
       {entete_cols}
FROM {schema}.f_docligne l
LEFT JOIN {schema}.f_comptet c ON l.ct_num = c.ct_num
LEFT JOIN {schema}.f_article a ON l.ar_ref = a.ar_ref
LEFT JOIN {schema}.f_collaborateur col ON l.co_no = col.co_no
{entete_join}
WHERE 1=1""".strip()

        sql = add_in(sql, "l.do_domaine", req.do_domaine, params)
        sql = add_in(sql, "l.do_type", req.do_type, params)
        sql = add_in(sql, "l.do_piece", req.do_piece, params)
        sql = add_in(sql, "l.ar_ref", req.ar_ref, params)
        sql = add_in(sql, "l.ct_num", req.ct_num, params)
        sql = add_in(sql, "l.co_no", req.co_no, params)
        sql = add_ilike(sql, "l.dl_design", req.dl_design, params)
        sql = add_eq(sql, "l.pf_num", req.pf_num, params)
        sql = add_eq(sql, "l.do_date", req.do_date, params)
        sql = add_gte(sql, "l.do_date", req.date_from, params)
        sql = add_lte(sql, "l.do_date", req.date_to, params)
        sql = add_gte(sql, "l.dl_qte", req.dl_qte_min, params)
        sql = add_gte(sql, "l.dl_montantht", req.dl_montantht_min, params)
        sql = add_eq(sql, "l.dl_nonlivre", req.dl_nonlivre, params)
        sql = add_eq(sql, "l.dl_valorise", req.dl_valorise, params)
        sql += f" ORDER BY l.do_piece ASC, l.dl_ligne ASC"
        return sql, params, cols
