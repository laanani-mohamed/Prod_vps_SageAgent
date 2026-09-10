"""
api/stock/repositories/pg_repo/_executor.py

Wrapper fin autour de api.common.pg_executor pour le module Stock.
"""
from __future__ import annotations
import logging
from typing import Tuple, List, Dict, Any, Callable

from api.common.pg_executor import execute_query as _execute_query

logger = logging.getLogger("api.stock.repositories.pg")


def execute_query(
    builder_fn: Callable,
    req: Any,
    schema: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    return _execute_query(builder_fn, req, schema, logger, "[PG Stock]")
