"""
audit_reader.py — Lecture seule du journal d'accès à l'API (auth.audit_logs).
Zéro dépendance Streamlit. Toutes les valeurs de filtre passent en paramètres SQL.
Dates : bornes incluses, en UTC (le journal est horodaté en UTC).
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import psycopg2

from config.db_config import DB_CONFIG


def _where(date_from: date, date_to: date, client: Optional[str], action: Optional[str],
           status: Optional[str]) -> Tuple[str, list]:
    sql = "WHERE timestamp >= %s AND timestamp < %s"
    params: list = [date_from, date_to + timedelta(days=1)]
    if client:
        # LOGIN / LOGOUT / REFRESH n'ont jamais de client_schema : on les rattache au client
        # via les schémas autorisés de l'utilisateur (auth.users). Casse ignorée (MULIPARTS / muliparts).
        sql += (" AND (LOWER(client_schema) = LOWER(%s) OR (client_schema IS NULL AND username IN ("
                "SELECT username FROM auth.users WHERE LOWER(%s) = ANY(allowed_schemas))))")
        params += [client, client]
    for col, val in (("action", action), ("status", status)):
        if val:
            sql += f" AND {col} = %s"
            params.append(val)
    return sql, params


def _query(sql: str, params: list) -> List[Dict]:
    with psycopg2.connect(**DB_CONFIG) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def filter_options() -> Dict[str, List[str]]:
    """Valeurs présentes dans le journal, pour les listes de filtres."""
    rows = _query("SELECT DISTINCT client_schema, action, status FROM auth.audit_logs", [])
    return {
        "clients": sorted({r["client_schema"].lower() for r in rows if r["client_schema"]}),
        "actions": sorted({r["action"] for r in rows if r["action"]}),
        "statuts": sorted({r["status"] for r in rows if r["status"]}),
    }


def counts_by_action(date_from: date, date_to: date, client: Optional[str] = None) -> List[Dict]:
    """Nombre d'événements par (action, statut) sur la période."""
    where, params = _where(date_from, date_to, client, None, None)
    return _query(f"SELECT action, status, COUNT(*) AS nb FROM auth.audit_logs {where} "
                  "GROUP BY action, status ORDER BY nb DESC", params)


def daily_counts(date_from: date, date_to: date, client: Optional[str] = None) -> List[Dict]:
    """Par jour (UTC) : appels API réussis, erreurs API, connexions échouées, accès refusés."""
    where, params = _where(date_from, date_to, client, None, None)
    return _query(f"""
SELECT (timestamp AT TIME ZONE 'UTC')::date AS jour,
       COUNT(*) FILTER (WHERE action = 'API_CALL' AND status = 'SUCCESS') AS appels_ok,
       COUNT(*) FILTER (WHERE action = 'API_ERROR')                       AS erreurs_api,
       COUNT(*) FILTER (WHERE action = 'LOGIN' AND status = 'FAILED')     AS connexions_echouees,
       COUNT(*) FILTER (WHERE action = 'ACCESS_DENIED')                   AS acces_refuses
FROM auth.audit_logs {where}
GROUP BY jour ORDER BY jour""", params)


def events(date_from: date, date_to: date, client: Optional[str] = None, action: Optional[str] = None,
           status: Optional[str] = None, limit: int = 1000) -> List[Dict]:
    """Événements détaillés, les plus récents d'abord (au plus `limit`)."""
    where, params = _where(date_from, date_to, client, action, status)
    return _query(f"""
SELECT timestamp, username, action, endpoint, ip_address, client_schema, status, details
FROM auth.audit_logs {where}
ORDER BY timestamp DESC LIMIT %s""", params + [int(limit)])
