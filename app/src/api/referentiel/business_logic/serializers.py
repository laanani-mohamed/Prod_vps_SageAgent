"""
bi/referentiel/business_logic/serializers.py

Sérialisation JSON-safe des données retournées par les repositories.
Centralise la conversion des types Python non-sérialisables.
"""
from __future__ import annotations
import decimal
import datetime
from typing import Any, Dict, List


def serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convertit les valeurs d'une ligne en types JSON-sérialisables."""
    result = {}
    for k, v in row.items():
        if isinstance(v, decimal.Decimal):
            result[k] = float(v)
        elif isinstance(v, datetime.datetime):
            result[k] = v.isoformat()
        elif isinstance(v, datetime.date):
            result[k] = v.isoformat()
        elif isinstance(v, datetime.timedelta):
            result[k] = v.days
        else:
            result[k] = v
    return result


def serialize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convertit une liste de lignes en types JSON-sérialisables."""
    return [serialize_row(row) for row in rows]
