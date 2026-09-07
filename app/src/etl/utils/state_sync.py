import os
import json
import logging
from datetime import datetime
import psycopg2
import sys

logger = logging.getLogger("state_sync")

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.db_config import DB_CONFIG
from config.etl_config import STORAGE_ROOT

STATE_DIR = os.path.join(STORAGE_ROOT, "storage_srv", "state")
STATE_SYNC_ERROR_DIR = os.path.join(STATE_DIR, "state_sync_errors")
os.makedirs(STATE_SYNC_ERROR_DIR, exist_ok=True)


def parse_iso_datetime(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


def sync_states():
    if not os.path.exists(STATE_DIR):
        logger.warning("Dossier state introuvable, arrêt.")
        return

    #Scanner tous les JSON
    json_files = []
    for root, _, files in os.walk(STATE_DIR):
        for file in files:
            if file.endswith(".json"):
                json_files.append(os.path.join(root, file))

    if not json_files:
        logger.info("Aucun state détecté.")
        return

    conn = None
    failed_run_ids = []
    synced = 0
    skipped = 0

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()

        # Préparer la requête d’upsert
        upsert_query = """
        INSERT INTO public.etl_state (
            run_id, client, status, current_step, error_code, error_message,
            started_at, finished_at, duration_ms, last_updated_at
        ) VALUES (
            %(run_id)s, %(client)s, %(status)s, %(current_step)s, %(error_code)s, %(error_message)s,
            %(started_at)s, %(finished_at)s, %(duration_ms)s, %(last_updated_at)s
        )
        ON CONFLICT (run_id) DO UPDATE SET
            client = EXCLUDED.client,
            status = EXCLUDED.status,
            current_step = EXCLUDED.current_step,
            error_code = EXCLUDED.error_code,
            error_message = EXCLUDED.error_message,
            finished_at = EXCLUDED.finished_at,
            duration_ms = EXCLUDED.duration_ms,
            last_updated_at = EXCLUDED.last_updated_at;
        """

        # Récupérer les run_id déjà connus + last_updated_at
        cur.execute("SELECT run_id, last_updated_at FROM public.etl_state;")
        existing_states = {
            row[0]: row[1]
            for row in cur.fetchall()
        }

        for filepath in json_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    state = json.load(f)

                run_id = state.get("run_id")
                if not run_id:
                    continue

                json_updated_at_str = state.get("last_updated_at")
                if json_updated_at_str:
                    json_updated_at = parse_iso_datetime(json_updated_at_str)
                else:
                    # Fallback sur la date système du fichier si la clé n'existe pas dans le JSON
                    import datetime as dt
                    json_updated_at = datetime.fromtimestamp(os.path.getmtime(filepath), tz=dt.timezone.utc)

                db_updated_at = existing_states.get(run_id)

                # LOGIQUE INCRÉMENTALE
                if db_updated_at and json_updated_at <= db_updated_at:
                    skipped += 1
                    continue

                cur.execute(upsert_query, {
                    "run_id": run_id,
                    "client": state.get("client"),
                    "status": state.get("status"),
                    "current_step": state.get("current_step"),
                    "error_code": state.get("error_code"),
                    "error_message": state.get("error_message"),
                    "started_at": parse_iso_datetime(state.get("started_at")),
                    "finished_at": parse_iso_datetime(state.get("finished_at")),
                    "duration_ms": state.get("duration_ms"),
                    "last_updated_at": json_updated_at
                })

                synced += 1

            except Exception as e:
                logger.error(f"Erreur sync {filepath}: {e}")
                failed_run_ids.append(run_id or os.path.basename(filepath))

        logger.info(
            f"Synchronisation terminée | Injectés : {synced} | Ignorés (déjà à jour) : {skipped} | Échecs : {len(failed_run_ids)}"
        )

        #Sauvegarde des run_id non synchronisés
        if failed_run_ids:
            report_path = os.path.join(
                STATE_SYNC_ERROR_DIR,
                f"failed_runs_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
            )
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump({
                    "generated_at": datetime.utcnow().isoformat(),
                    "failed_run_ids": failed_run_ids
                }, f, indent=4)
            logger.warning(f"Run_id non synchronisés écrits dans {report_path}")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    sync_states()
