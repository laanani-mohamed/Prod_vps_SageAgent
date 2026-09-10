"""
api/referentiel/repositories/pg_repo/_executor.py

Wrapper fin autour de api.common.pg_executor pour le module Référentiel.
"""
from __future__ import annotations
import logging
from typing import List, Dict, Any, Callable

from api.common.pg_executor import execute_query as _execute_query

logger = logging.getLogger("api.referentiel.repositories.pg")


def execute_query(
    builder_fn: Callable,
    req: Any,
    schema: str,
) -> List[Dict[str, Any]]:
    data, _ = _execute_query(builder_fn, req, schema, logger, "[PG Referentiel]")
    return data
