"""
api/bi/use_cases/last_update_uc.py

Use Case : GET /api/bi/dashboard/last-update
Retourne l'horodatage de la dernière ingestion ETL réussie (PipelineCompleted)
pour un client donné, tous comptes de casse confondus (ex: 'MULIPARTS' côté ETL
vs 'muliparts' côté schéma Postgres).
"""
from __future__ import annotations
import logging

from api.bi.schemas import LastUpdateResponse
from api.db import get_db_connection

logger = logging.getLogger("api.bi.use_cases.last_update")

_SQL = """
    SELECT MAX(created_at)
    FROM etl_events.pipeline_events
    WHERE lower(client) = lower(%s) AND event_type = 'PipelineCompleted'
"""


def execute(client_schema: str) -> LastUpdateResponse:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_SQL, (client_schema,))
                row = cur.fetchone()
                last_update = row[0].isoformat() if row and row[0] else None
    except Exception as exc:
        logger.error("[BI/last-update] Erreur requête pour %s : %s", client_schema, exc)
        raise

    return LastUpdateResponse(client_schema=client_schema, last_update=last_update)
