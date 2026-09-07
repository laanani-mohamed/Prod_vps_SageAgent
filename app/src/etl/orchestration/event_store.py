"""
event_store.py — Cœur de l'Event Sourcing pour le pipeline ETL.

Responsabilités :
  1. append_event()    → Enregistrer un événement immuable (PostgreSQL + fallback JSONL).
  2. get_events()      → Rejouer l'historique complet d'un run.
  3. rebuild_state()   → Reconstruire l'état courant d'un run depuis ses événements (Reducer).

Architecture :
  - Source de vérité primaire  : Table PostgreSQL `etl_events.pipeline_events`.
  - Fallback (si DB indispo)   : Fichier JSONL append-only dans `storage_srv/events/`.
  - Aucun UPDATE / DELETE n'est jamais exécuté sur les événements.

Types d'événements (event_type) :
  WatcherValidationFailed    → Le watcher a rejeté un dossier (ex: timeout).
  WatcherCriticalError       → Erreur système globale du watcher.
  RunInitialized             → Début du pipeline pour un client/run_id.
  FilenameValidationPassed   → Validation des noms de fichiers réussie.
  FilenameValidationFailed   → Validation des noms de fichiers échouée.
  SizeValidationPassed       → Validation des tailles de fichiers réussie.
  SizeValidationFailed       → Validation des tailles de fichiers échouée.
  SchemaValidationPassed     → Validation du schéma/qualité réussie.
  SchemaValidationFailed     → Validation du schéma/qualité échouée.
  IngestionStarted           → Début de l'ingestion SQL.
  IngestionCompleted         → Ingestion réussie.
  IngestionFailed            → Ingestion échouée (rollback déclenché).
  ArchiveCompleted           → Archivage terminé.
  PipelineFailed             → Clôture du pipeline en échec.
  PipelineCompleted          → Clôture du pipeline en succès.
"""

import json
import logging
import os
from datetime import datetime, timezone

import psycopg2

from config.db_config import DB_CONFIG

logger = logging.getLogger("etl.event_store")

# =============================================================================
# Configuration des chemins
# =============================================================================

from config.etl_config import STORAGE_ROOT

EVENTS_DIR = os.path.join(STORAGE_ROOT, "storage_srv", "events")
os.makedirs(EVENTS_DIR, exist_ok=True)

FALLBACK_JSONL_PATH = os.path.join(EVENTS_DIR, "events.jsonl")

# Requête d'insertion principale (PostgreSQL)
_SQL_INSERT = """
    INSERT INTO etl_events.pipeline_events (run_id, client, event_type, payload, created_at)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id;
"""

# Requête de lecture par run_id (PostgreSQL) — ordonnée pour le replay
_SQL_SELECT_RUN = """
    SELECT id, run_id, client, event_type, payload, created_at
    FROM etl_events.pipeline_events
    WHERE run_id = %s
    ORDER BY id ASC;
"""


# =============================================================================
# ÉCRITURE — append_event (PostgreSQL + fallback JSONL)
# =============================================================================

def append_event(run_id: str, client: str, event_type: str, payload: dict = None) -> bool:
    """
    Ajoute un événement immuable dans l'Event Store.

    Tente d'abord un INSERT dans PostgreSQL. En cas d'échec de connexion,
    bascule automatiquement sur le fichier JSONL local (fallback).

    Args:
        run_id      : UUID du run de pipeline (string).
        client      : Nom du schéma client (ex: "client_abc").
        event_type  : Type sémantique de l'événement (voir liste en en-tête).
        payload     : Dictionnaire de données contextuelles (optionnel).

    Returns:
        True si l'événement a été enregistré (dans PostgreSQL ou JSONL), False sinon.
    """
    if payload is None:
        payload = {}

    now = datetime.now(timezone.utc)

    # --- Tentative PostgreSQL ---
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn:
            with conn.cursor() as cur:
                cur.execute(_SQL_INSERT, (run_id, client, event_type, json.dumps(payload), now))
                inserted_id = cur.fetchone()[0]
        conn.close()

        logger.debug(
            f"[EventStore] Événement enregistré en DB (id={inserted_id}).",
            extra={"run_id": run_id, "client": client, "event_type": event_type, "step": "event_store_pg"}
        )
        return True

    except psycopg2.OperationalError as e:
        # DB indisponible : on bascule sur le fallback JSONL sans bloquer le pipeline
        logger.warning(
            f"[EventStore] PostgreSQL indisponible, bascule sur JSONL. Détail : {e}",
            extra={"run_id": run_id, "client": client, "event_type": event_type, "step": "event_store_fallback"}
        )

    except Exception as e:
        logger.error(
            f"[EventStore] Erreur inattendue lors de l'INSERT : {e}",
            extra={"run_id": run_id, "client": client, "event_type": event_type, "step": "event_store_error"}
        )

    # --- Fallback JSONL (append-only, atomique via write + flush) ---
    return _append_to_jsonl(run_id, client, event_type, payload, now)


def _append_to_jsonl(run_id: str, client: str, event_type: str, payload: dict, now: datetime) -> bool:
    """Écrit un événement dans le fichier JSONL local (fallback)."""
    record = {
        "created_at": now.isoformat(),
        "run_id":     run_id,
        "client":     client,
        "event_type": event_type,
        "payload":    payload,
    }
    try:
        with open(FALLBACK_JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())  # Garantit l'écriture physique sur disque
        logger.debug(
            "[EventStore] Événement enregistré en fallback JSONL.",
            extra={"run_id": run_id, "client": client, "event_type": event_type, "step": "event_store_jsonl"}
        )
        return True
    except Exception as e:
        logger.critical(
            f"[EventStore] CRITIQUE — Impossible d'écrire l'événement même en fallback JSONL : {e}",
            extra={"run_id": run_id, "client": client, "event_type": event_type, "error_code": "EVENT_STORE_WRITE_FAILURE", "step": "event_store_critical"}
        )
        return False


# =============================================================================
# LECTURE — get_events / rebuild_state
# =============================================================================

def get_events(run_id: str) -> list:
    """
    Retourne la liste ordonnée (chronologique) de tous les événements d'un run.
    Tente d'abord PostgreSQL, puis bascule sur le JSONL local.

    Returns:
        Liste de dictionnaires {id, run_id, client, event_type, payload, created_at}.
    """
    # --- Tentative PostgreSQL ---
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        events = []
        with conn:
            with conn.cursor() as cur:
                cur.execute(_SQL_SELECT_RUN, (run_id,))
                rows = cur.fetchall()
                for row in rows:
                    events.append({
                        "id":         row[0],
                        "run_id":     str(row[1]),
                        "client":     row[2],
                        "event_type": row[3],
                        "payload":    row[4] if row[4] else {},
                        "created_at": row[5].isoformat() if row[5] else None,
                    })
        conn.close()
        return events

    except psycopg2.OperationalError:
        logger.warning(
            "[EventStore] PostgreSQL indisponible pour get_events, lecture JSONL.",
            extra={"run_id": run_id, "step": "event_store_read_fallback"}
        )
    except Exception as e:
        logger.error(
            f"[EventStore] Erreur lors de la lecture des événements : {e}",
            extra={"run_id": run_id, "step": "event_store_read_error"}
        )

    # --- Fallback JSONL ---
    return _read_from_jsonl(run_id)


def _read_from_jsonl(run_id: str) -> list:
    """Lit les événements d'un run depuis le fichier JSONL local."""
    events = []
    if not os.path.exists(FALLBACK_JSONL_PATH):
        return events
    with open(FALLBACK_JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("run_id") == run_id:
                    events.append(record)
            except json.JSONDecodeError:
                continue
    return events


def rebuild_state(run_id: str) -> dict:
    """
    Reconstruit l'état courant d'un run en rejouant tous ses événements (Reducer).

    C'est l'équivalent de "rejouer l'historique bancaire pour connaître le solde".
    Aucune donnée n'est lue depuis un fichier de state CRUD : tout est calculé
    depuis les événements immuables.

    Returns:
        Dictionnaire représentant l'état courant du run :
        {
            "run_id", "client", "status", "current_step",
            "started_at", "finished_at", "duration_ms",
            "error_code", "error_message",
            "steps": { "watcher", "validation", "ingestion", "archivage" }
        }
    """
    events = get_events(run_id)

    # État initial vide (avant tout événement)
    state = {
        "run_id":        run_id,
        "client":        None,
        "status":        "UNKNOWN",
        "current_step":  None,
        "started_at":    None,
        "finished_at":   None,
        "duration_ms":   None,
        "error_code":    None,
        "error_message": None,
        "steps": {
            "watcher":    "PENDING",
            "validation": "PENDING",
            "ingestion":  "PENDING",
            "archivage":  "PENDING",
        },
        "events_count": len(events),
    }

    # --- Reducer : appliquer chaque événement sur l'état ---
    for event in events:
        etype   = event.get("event_type")
        payload = event.get("payload", {})
        ts      = event.get("created_at")

        if etype == "RunInitialized":
            state["client"]       = event.get("client")
            state["status"]       = "RUNNING"
            state["started_at"]   = ts
            state["current_step"] = "validation"
            state["steps"]["watcher"] = "SUCCESS"

        elif etype == "FilenameValidationPassed":
            state["current_step"] = "size_validation"

        elif etype == "FilenameValidationFailed":
            state["steps"]["validation"] = "FAILED"
            state["error_code"]    = payload.get("error_code", "INVALID_INPUT_FILES")
            state["error_message"] = payload.get("error_message", "Noms de fichiers non conformes.")

        elif etype == "SizeValidationPassed":
            state["current_step"] = "schema_validation"

        elif etype == "SizeValidationFailed":
            state["steps"]["validation"] = "FAILED"
            state["error_code"]    = payload.get("error_code", "EMPTY_FILES")
            state["error_message"] = payload.get("error_message", "Fichier(s) vide(s) détecté(s).")

        elif etype == "SchemaValidationPassed":
            state["steps"]["validation"] = "SUCCESS"
            state["current_step"]        = "ingestion"

        elif etype == "SchemaValidationFailed":
            state["steps"]["validation"] = "FAILED"
            state["error_code"]    = payload.get("error_code", "SCHEMA_QUALITY_FAILED")
            state["error_message"] = payload.get("error_message", "Qualité des données non conforme.")

        elif etype == "IngestionStarted":
            state["current_step"] = "ingestion"

        elif etype == "IngestionCompleted":
            state["steps"]["ingestion"] = "SUCCESS"
            state["current_step"]       = "archivage"

        elif etype == "IngestionFailed":
            state["steps"]["ingestion"] = "FAILED"
            state["error_code"]    = payload.get("error_code", "INGESTION_FAILED")
            state["error_message"] = payload.get("error_message", "Erreur lors de l'insertion en DB.")

        elif etype == "ArchiveCompleted":
            state["steps"]["archivage"] = "SUCCESS"
            state["current_step"]       = "completed"

        elif etype == "PipelineFailed":
            state["status"]        = "FAILED"
            state["finished_at"]   = ts
            state["error_code"]    = payload.get("error_code", state["error_code"])
            state["error_message"] = payload.get("error_message", state["error_message"])
            if state["started_at"] and state["finished_at"]:
                try:
                    started  = datetime.fromisoformat(state["started_at"])
                    finished = datetime.fromisoformat(state["finished_at"])
                    state["duration_ms"] = int((finished - started).total_seconds() * 1000)
                except ValueError:
                    pass

        elif etype == "PipelineCompleted":
            state["status"]      = "SUCCESS"
            state["finished_at"] = ts
            state["current_step"] = "completed"
            for step in state["steps"]:
                if state["steps"][step] == "PENDING":
                    state["steps"][step] = "SUCCESS"
            if state["started_at"] and state["finished_at"]:
                try:
                    started  = datetime.fromisoformat(state["started_at"])
                    finished = datetime.fromisoformat(state["finished_at"])
                    state["duration_ms"] = int((finished - started).total_seconds() * 1000)
                except ValueError:
                    pass

    return state
