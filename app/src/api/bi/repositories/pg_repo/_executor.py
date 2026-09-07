"""
api/bi/repositories/pg_repo/_executor.py

Wrapper psycopg2 générique — partagé par toutes les requêtes PostgreSQL du module BI.
Miroir exact de api/stock/repositories/pg_repo/_executor.py adapté pour le module BI.

Responsabilités :
  - Ouvrir/fermer la connexion
  - Exécuter le SQL construit par le repo appelant
  - Logger SQL + params en DEBUG
  - Retourner List[dict]
"""
from __future__ import annotations
import logging
from typing import Tuple, List, Dict, Any, Callable

import psycopg2

from api.db import get_db_connection

logger = logging.getLogger("api.bi.repositories.pg")


def execute_query(
    builder_fn: Callable,
    req: Any,
    schema: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Exécute une requête SQL construite par builder_fn(req, schema).

    Args:
        builder_fn : Fonction (req, schema) → (sql, params, col_aliases)
        req        : L'objet de requête Pydantic
        schema     : Le schéma PostgreSQL du client (ex: "client_01")

    Returns:
        Tuple[List[dict], List[str]] : Résultats mappés par nom de colonne et alias
    """
    sql, params, col_aliases = builder_fn(req, schema)

    logger.info(
        "[PG BI] schema=%s | endpoint=%s",
        schema,
        getattr(req, "endpoint", getattr(req, "client_schema", "?")),
    )
    logger.debug("[PG BI] SQL:\n%s\nParams: %s", sql, params)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            data = [dict(zip(col_aliases, row)) for row in rows]
            return data, col_aliases

    except psycopg2.Error as e:
        logger.error("[PG BI] Erreur PostgreSQL : %s", e)
        raise
