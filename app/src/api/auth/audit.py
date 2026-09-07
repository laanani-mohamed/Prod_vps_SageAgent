"""
api/auth/audit.py

Système d'audit asynchrone / fire-and-forget pour tracker les actions sensibles
sans impacter les performances de l'API.

Toutes les actions sont insérées dans une queue thread-safe et traitées en
arrière-plan pour une insertion dans PostgreSQL.
"""
import logging
import threading
import queue
import time
from typing import Optional

from pydantic import BaseModel
from datetime import datetime, timezone
import psycopg2

from .config import auth_settings
from api.db import get_db_connection

logger = logging.getLogger("api.auth.audit")

class AuditEvent(BaseModel):
    timestamp: datetime
    username: Optional[str]
    action: str
    endpoint: str
    ip_address: str
    client_schema: Optional[str]
    status: str
    details: Optional[str]

# Queue thread-safe
_audit_queue = queue.Queue(maxsize=10000)
_stop_event = threading.Event()

def log_audit_event(
    action: str,
    endpoint: str,
    ip_address: str,
    status: str,
    username: Optional[str] = None,
    client_schema: Optional[str] = None,
    details: Optional[str] = None,
):
    """Fire-and-forget: ajoute l'événement à la queue."""
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc),
        username=username,
        action=action,
        endpoint=endpoint,
        ip_address=ip_address,
        client_schema=client_schema,
        status=status,
        details=details
    )
    try:
        _audit_queue.put_nowait(event)
    except queue.Full:
        logger.warning("[AUDIT] Queue pleine, perte d'un événement d'audit !")

def _audit_worker():
    """Worker qui dépile la queue et insère dans la base de données."""
    logger.info("[AUDIT] Démarrage du worker d'audit en arrière-plan")
            
    while not _stop_event.is_set():
        try:
            # Attend un événement pendant 1 seconde
            event: AuditEvent = _audit_queue.get(timeout=1.0)
            
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        sql = """
                        INSERT INTO auth.audit_logs 
                        (timestamp, username, action, endpoint, ip_address, client_schema, status, details)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cur.execute(sql, (
                            event.timestamp,
                            event.username,
                            event.action,
                            event.endpoint,
                            event.ip_address,
                            event.client_schema,
                            event.status,
                            event.details
                        ))
                    conn.commit()
            except Exception as e:
                logger.error(f"[AUDIT] Erreur insertion: {e}")
                # Le rollback est géré par get_db_connection en cas d'erreur
            finally:
                _audit_queue.task_done()
                
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"[AUDIT] Erreur inattendue du worker: {e}")
            time.sleep(1)

    logger.info("[AUDIT] Arrêt du worker d'audit")

# Démarrer le worker dans un thread séparé
_worker_thread = threading.Thread(target=_audit_worker, daemon=True)

def start_audit_worker():
    if not _worker_thread.is_alive():
        _worker_thread.start()

def stop_audit_worker():
    _stop_event.set()
    _worker_thread.join(timeout=5.0)
