"""
bi/referentiel/repositories/pg_repo/collaborateur_repo.py
"""
from typing import Tuple, List, Any
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.pg_repo._executor import execute_query
from api.referentiel.repositories.pg_repo.sql_helpers import validate_schema, add_in, add_ilike, add_eq

class PgCollaborateurRepository(BaseReferentielRepository):
    def fetch(self, req):
        schema = validate_schema(req.client_schema)
        return execute_query(self._build_query, req, schema)

    def _build_query(self, req, schema: str) -> Tuple[str, List[Any], List[str]]:
        params: list = []
        cols = [
            "co_no", "co_nom", "co_prenom", "co_fonction",
            "co_vendeur", "co_acheteur",
            "co_telephone", "co_telecopie", "co_email", "co_matricule",
        ]
        sql = f"""
SELECT co_no, co_nom, co_prenom, co_fonction,
       co_vendeur, co_acheteur,
       co_telephone, co_telecopie, co_email, co_matricule
FROM {schema}.f_collaborateur
WHERE 1=1""".strip()

        sql = add_in(sql, "co_no", req.co_no, params)
        sql = add_eq(sql, "co_vendeur", req.co_vendeur, params)
        sql = add_eq(sql, "co_acheteur", req.co_acheteur, params)
        sql = add_ilike(sql, "co_nom", req.co_nom, params)
        sql = add_ilike(sql, "co_prenom", req.co_prenom, params)
        sql = add_ilike(sql, "co_fonction", req.co_fonction, params)
        sql = add_ilike(sql, "co_matricule", req.co_matricule, params)
        sql += f" ORDER BY co_nom ASC, co_prenom ASC"
        return sql, params, cols
