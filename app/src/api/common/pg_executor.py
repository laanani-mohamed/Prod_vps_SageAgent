"""
api/common/pg_executor.py

Wrapper psycopg2 générique — partagé par les repositories PostgreSQL de
tous les modules API (stock, bi, référentiel).

Responsabilités :
  - Ouvrir/fermer la connexion
  - Exécuter le SQL construit par le repo appelant
  - Logger SQL + params en DEBUG
  - Retourner List[dict] et la liste des alias de colonnes
"""
from __future__ import annotations
import logging
from typing import Tuple, List, Dict, Any, Callable

import psycopg2

from api.db import get_db_connection


def execute_query(
    builder_fn: Callable,
    req: Any,
    schema: str,
    logger: logging.Logger,
    log_prefix: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Exécute une requête SQL construite par builder_fn(req, schema).

    Args:
        builder_fn : Fonction (req, schema) → (sql, params, col_aliases)
        req        : L'objet de requête Pydantic
        schema     : Le schéma PostgreSQL du client (ex: "client_01")
        logger     : Logger du module appelant
        log_prefix : Préfixe des lignes de log (ex: "[PG Stock]")

    Returns:
        Tuple[List[dict], List[str]] : Résultats mappés par nom de colonne et alias
    """
    sql, params, col_aliases = builder_fn(req, schema)

    logger.info("%s schema=%s | req=%s", log_prefix, schema, type(req).__name__)
    logger.debug("%s SQL:\n%s\nParams: %s", log_prefix, sql, params)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            data = [dict(zip(col_aliases, row)) for row in rows]
            return data, col_aliases

    except psycopg2.Error as e:
        logger.error("%s Erreur PostgreSQL : %s", log_prefix, e)
        raise
