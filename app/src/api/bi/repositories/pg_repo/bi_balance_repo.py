"""
api/bi/repositories/pg_repo/bi_balance_repo.py

Repository PostgreSQL pour le rapport Balance Client.
Retourne F_DOCENTETE (factures) avec jointures tiers pour calculer l'encours et les arriérés.
Le commercial est celui porté par la facture (F_DOCENTETE.co_no), pas celui du tiers.
"""
from typing import Tuple, List, Dict, Any

from api.bi.repositories.base_bi_repo import BaseBIRepository
from api.bi.repositories.pg_repo._executor import execute_query
from api.bi.repositories.pg_repo.sql_helpers import validate_schema, add_in


class PgBIBalanceClientRepository(BaseBIRepository):
    """
    Repository pour la balance client (POST /api/bi/rapport/balance).
    """

    def fetch(self, req) -> List[Dict[str, Any]]:
        schema = validate_schema(req.client_schema)
        data, _ = execute_query(self._build_query, req, schema)
        return data

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []

        col_aliases = [
            "do_piece", "do_date", "do_tiers", "ct_intitule",
            "co_no", "co_fullname",
            "do_totalttc", "do_montantregle", "reste_a_payer"
        ]

        # On filtre les factures (DO_Type = 6) qui ont un reste à payer
        # DO_Domaine = 0 (Ventes)
        sql = f"""
SELECT
    e.do_piece,
    CAST(e.do_date AS TEXT) AS do_date,
    e.do_tiers,
    COALESCE(ct.ct_intitule, 'Non identifier') AS ct_intitule,
    COALESCE(e.co_no, 0) AS co_no,
    CASE
        WHEN COALESCE(e.co_no, 0) = 0 THEN 'Non identifié'
        ELSE COALESCE(
            NULLIF(CONCAT_WS(' ', NULLIF(TRIM(col.co_nom), ''), NULLIF(TRIM(col.co_prenom), '')), ''),
            'Commercial ' || e.co_no
        )
    END AS co_fullname,
    COALESCE(e.do_totalttc, 0) AS do_totalttc,
    COALESCE(e.do_montantregle, 0) AS do_montantregle,
    COALESCE(e.do_totalttc, 0) - COALESCE(e.do_montantregle, 0) AS reste_a_payer
FROM {schema}.f_docentete e
LEFT JOIN {schema}.f_comptet ct ON ct.ct_num = e.do_tiers
LEFT JOIN {schema}.f_collaborateur col ON col.co_no = e.co_no
WHERE e.do_domaine = 0
  AND e.do_type IN (6, 7)
  AND ROUND(CAST(COALESCE(e.do_totalttc, 0) - COALESCE(e.do_montantregle, 0) AS NUMERIC), 2) > 0
""".strip()

        sql = add_in(sql, "COALESCE(e.co_no, 0)", req.co_no, params)

        return sql, params, col_aliases
