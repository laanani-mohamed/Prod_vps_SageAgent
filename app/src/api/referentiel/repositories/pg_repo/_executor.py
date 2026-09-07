"""
bi/referentiel/repositories/pg_repo/_executor.py

Wrapper psycopg2 générique — partagé par tous les repositories PostgreSQL du module Référentiel.

Responsabilités :
  - Ouvrir/fermer la connexion
  - Exécuter le SQL
  - Logger SQL + params en DEBUG
  - Retourner List[dict]
"""
from __future__ import annotations
import logging
from typing import Tuple, List, Dict, Any, Callable

import psycopg2

from api.db import get_db_connection

logger = logging.getLogger("api.referentiel.repositories.pg")


def execute_query(
    builder_fn: Callable,
    req: Any,
    schema: str,
) -> List[Dict[str, Any]]:
    """
    Exécute une requête SQL construite par builder_fn(req, schema).

    Args:
        builder_fn : Fonction (req, schema) → (sql, params, col_aliases)
        req        : Le schéma Pydantic de la requête
        schema     : Le schéma PostgreSQL du client (ex: "client_01")

    Returns:
        List[dict] : Résultats mappés par nom de colonne
    """
    sql, params, col_aliases = builder_fn(req, schema)

    logger.info(
        f"[PG Referentiel] schema={schema} | resource={type(req).__name__} | limit={getattr(req, 'limit', '?')}"
    )
    logger.debug(f"[PG Referentiel] SQL:\n{sql}\nParams: {params}")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            return [dict(zip(col_aliases, row)) for row in rows]

    except psycopg2.Error as e:
        logger.error(f"[PG Referentiel] Erreur PostgreSQL : {e}")
        raise
