"""
bi/referentiel/repositories/pg_repo/comptes_tiers_repo.py
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_ilike, add_eq, add_gte, add_lte

class PgComptesTiersRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        cols = [
            "ct_num", "ct_intitule", "ct_type", "ct_qualite", "ct_contact",
            "ct_adresse", "ct_complement", "ct_ville", "ct_code_region", "ct_identifiant",
            "ct_telephone", "ct_telecopie", "ct_email", "ct_site",
            "cbcreation", "ct_sommeil", "co_no", "co_nom", "co_prenom", "co_fonction",
        ]
        sql = f"""
SELECT
  c.ct_num, c.ct_intitule, c.ct_type, c.ct_qualite, c.ct_contact,
  c.ct_adresse, c.ct_complement, c.ct_ville, c.ct_coderegion, c.ct_identifiant,
  c.ct_telephone, c.ct_telecopie, c.ct_email, c.ct_site,
  c.cbcreation, c.ct_sommeil, c.co_no,
  col.co_nom, col.co_prenom, col.co_fonction
FROM {schema}.f_comptet c
LEFT JOIN {schema}.f_collaborateur col ON c.co_no = col.co_no
WHERE 1=1""".strip()

        sql = add_in(sql, "c.ct_num", req.ct_num, params)
        sql = add_ilike(sql, "c.ct_intitule", req.ct_intitule, params)
        sql = add_in(sql, "c.ct_type", req.ct_type, params)
        sql = add_eq(sql, "c.ct_sommeil", req.ct_sommeil, params)
        sql = add_eq(sql, "c.ct_identifiant", req.ct_identifiant, params)
        sql = add_ilike(sql, "c.ct_ville", req.ct_ville, params)
        sql = add_ilike(sql, "c.ct_qualite", req.ct_qualite, params)
        sql = add_ilike(sql, "c.ct_coderegion", req.ct_code_region, params)
        sql = add_eq(sql, "c.co_no", req.co_no_representant, params)
        sql = add_gte(sql, "c.cbcreation", req.cbcreation_from, params)
        sql = add_lte(sql, "c.cbcreation", req.cbcreation_to, params)
        sql += f" ORDER BY c.ct_intitule ASC"
        return sql, params, cols
