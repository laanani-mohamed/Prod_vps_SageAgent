"""
bi/stock/repositories/pg_repo/stock_availability_repo.py
"""
from typing import Tuple, List, Dict, Any
from api.stock.repositories.base_repo import BaseStockRepository
from api.stock.repositories.pg_repo._executor import execute_query
from api.stock.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_eq

class PgStockAvailabilityRepository(BaseStockRepository):
    def fetch(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_query, req, schema)
        return data

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        
        # 1. Joins
        join_artstock = f"LEFT JOIN {schema}.f_artstock s ON a.ar_ref = s.ar_ref"
        if req.depot_ids:
            placeholders = ", ".join(["%s"] * len(req.depot_ids))
            join_artstock += f" AND s.de_no IN ({placeholders})"
            params.extend(req.depot_ids)

        # 2. Select columns
        select_cols = [
            "a.ar_ref", "a.ar_design", "s.as_qtesto",
            "a.ar_prixven", "a.ar_prixach", "a.fa_codefamille",
            "a.ar_suivistock", "a.ar_nature", "a.ar_type", "a.ar_sommeil",
            "s.de_no", "d.de_intitule"
        ]
        col_aliases = [
            "ar_ref", "ar_design", "as_qtesto",
            "ar_prixven", "ar_prixach", "fa_codefamille",
            "ar_suivistock", "ar_nature", "ar_type", "ar_sommeil",
            "de_no", "de_intitule"
        ]

        sql = f"""
SELECT {', '.join(select_cols)}
FROM {schema}.f_article a
{join_artstock}
LEFT JOIN {schema}.f_depot d ON d.de_no = s.de_no
WHERE 1=1""".strip()

        # 3. Where filters
        sql = add_eq(sql, "a.ar_sommeil", req.ar_sommeil, params)
        sql = add_in(sql, "a.fa_codefamille", req.fa_codefamille, params)

        # Search conditions
        search_conds: list[str] = []
        if req.ar_ref:
            exact_refs = [r for r in req.ar_ref if len(r) > 7]
            prefix_refs = [r for r in req.ar_ref if len(r) <= 7]
            if exact_refs:
                placeholders = ", ".join(["%s"] * len(exact_refs))
                search_conds.append(f"a.ar_ref IN ({placeholders})")
                params.extend(exact_refs)
            for prefix in prefix_refs:
                search_conds.append("a.ar_ref LIKE %s")
                params.append(f"{prefix}%")

        search_terms = req.search_terms or []
        for t in search_terms:
            search_conds.append("a.ar_design ILIKE %s")
            params.append(f"%{t}%")

        if search_conds:
            sql += " AND (" + " OR ".join(search_conds) + ")"

        sql += f" LIMIT {int(req.limit)}"
        
        return sql, params, col_aliases
