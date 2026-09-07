"""
bi/stock/repositories/pg_repo/stock_insight_repo.py
"""
from typing import Tuple, List, Dict, Any
from api.stock.repositories.base_repo import BaseStockRepository
from api.stock.repositories.pg_repo._executor import execute_query
from api.stock.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_eq

class PgStockInsightRepository(BaseStockRepository):
    def fetch(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        if req.insight_type == "expiration":
            data, _ = execute_query(self._build_lots_query, req, schema)
        else:
            data, _ = execute_query(self._build_stock_query, req, schema)
        return data

    def _build_stock_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        
        # 1. Joins
        join_artstock = f"LEFT JOIN {schema}.f_artstock s ON a.ar_ref = s.ar_ref"
        if req.depot_ids:
            placeholders = ", ".join(["%s"] * len(req.depot_ids))
            join_artstock += f" AND s.de_no IN ({placeholders})"
            params.extend(req.depot_ids)

        join_lateral = f"LEFT JOIN LATERAL (SELECT MAX(dl.do_date)::date AS max_do_date FROM {schema}.f_docligne dl WHERE dl.ar_ref = a.ar_ref AND dl.do_domaine = 0) dl_max ON true"
        join_famille = f"LEFT JOIN {schema}.f_famille f ON a.fa_codefamille = f.fa_codefamille"

        # 2. Select columns
        select_cols = [
            "a.ar_ref", "a.ar_design", "s.as_qtesto",
            "a.ar_prixven", "a.ar_prixach", "a.fa_codefamille", "f.fa_intitule",
            "a.ar_suivistock", "a.ar_nature", "a.ar_type", "a.ar_sommeil",
            "s.de_no", "d.de_intitule",
            "dl_max.max_do_date AS derniere_date_vente",
            "(CURRENT_DATE - dl_max.max_do_date) AS nbr_jours_inactif"
        ]
        col_aliases = [
            "ar_ref", "ar_design", "as_qtesto",
            "ar_prixven", "ar_prixach", "fa_codefamille", "fa_intitule",
            "ar_suivistock", "ar_nature", "ar_type", "ar_sommeil",
            "de_no", "de_intitule", "derniere_date_vente", "nbr_jours_inactif"
        ]

        sql = f"""
SELECT {', '.join(select_cols)}
FROM {schema}.f_article a
{join_artstock}
LEFT JOIN {schema}.f_depot d ON d.de_no = s.de_no
{join_lateral}
{join_famille}
WHERE 1=1""".strip()

        # 3. Where filters
        if req.insight_type == "sommeil":
            # Override ar_sommeil if they requested "sommeil" type explicitly
            sql = add_eq(sql, "a.ar_sommeil", 1, params)
        else:
            sql = add_eq(sql, "a.ar_sommeil", req.ar_sommeil, params)
            
        sql = add_in(sql, "a.fa_codefamille", req.fa_codefamille, params)

        if req.insight_type == "dormant":
            # Dormant: no movements in F_DOCLIGNE (excluding achats, do_domaine = 0) in the last X days, BUT has been sold at least once
            dormant_days = req.dormant_days or 90
            sql += f" AND dl_max.max_do_date IS NOT NULL"
            sql += f" AND (CURRENT_DATE - dl_max.max_do_date) >= {dormant_days}"
            
        elif req.insight_type == "jamais_vendu":
            # Jamais vendu: no movements in F_DOCLIGNE at all (excluding achats)
            sql += f" AND dl_max.max_do_date IS NULL"

        sql += f" LIMIT {int(req.limit)}"
        
        return sql, params, col_aliases

    def _build_lots_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        join_artstock = f"LEFT JOIN {schema}.f_artstock s ON a.ar_ref = s.ar_ref"
        if req.depot_ids:
            placeholders = ", ".join(["%s"] * len(req.depot_ids))
            join_artstock += f" AND s.de_no IN ({placeholders})"
            params.extend(req.depot_ids)

        join_lotserie = (
            f"LEFT JOIN {schema}.f_lotserie ls "
            f"ON ls.ar_ref = a.ar_ref AND ls.de_no = s.de_no "
            f"AND (a.ar_suivistock = 1 OR a.ar_suivistock = 5)"
        )
        join_famille = f"LEFT JOIN {schema}.f_famille f ON a.fa_codefamille = f.fa_codefamille"

        select_cols = [
            "a.ar_ref", "a.ar_design", "a.fa_codefamille", "f.fa_intitule", "s.de_no",
            "ls.ls_noserie", "ls.ls_qte",
            "ls.ls_qterestant", "ls.ls_peremption", "ls.ls_lotepuise"
        ]
        col_aliases = [
            "ar_ref", "ar_design", "fa_codefamille", "fa_intitule", "de_no",
            "ls_noserie", "ls_qte",
            "ls_qterestant", "ls_peremption", "ls_lotepuise"
        ]

        sql = f"""
SELECT {', '.join(select_cols)}
FROM {schema}.f_article a
{join_artstock}
LEFT JOIN {schema}.f_depot d ON d.de_no = s.de_no
{join_lotserie}
{join_famille}
WHERE 1=1""".strip()

        # 3. Where filters
        sql = add_eq(sql, "a.ar_sommeil", req.ar_sommeil, params)
        sql = add_in(sql, "a.fa_codefamille", req.fa_codefamille, params)

        # Pas de LIMIT pour les lots en péremption afin de ne rater aucune alerte
        return sql, params, col_aliases
