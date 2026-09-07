"""
main.py — Orchestrateur central du pipeline ETL (Queue-Based).

Responsabilités :
  1. Lance le Watcher pour surveiller les dépôts clients.
  2. Déplace immédiatement les dossiers prêts dans la file d'attente (broker_queue).
  3. Dépile la file d'attente par lots à chaque Heartbeat.
"""
import logging
import uuid
import sys
import os

# Ajout dynamique de la racine du projet et du dossier src au PYTHONPATH
# Ajout dynamique de la racine du projet et du dossier src au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
# Remonte : orchestration -> etl -> src (2 niveaux) -> RACINE (3 niveaux)
src_path = os.path.dirname(os.path.dirname(current_dir))
project_root = os.path.dirname(src_path)

for path in [project_root, src_path]:
    if path not in sys.path:
        sys.path.insert(0, path)

from etl.watcher.watcher import watch
from etl.archive.archiver import archive_folder
from config.logging_config import setup_logging
from config.etl_config import MAX_QUEUE_LIMIT
from etl.orchestration.event_store import append_event
from etl.broker import queue_manager
from etl.worker.pipeline_worker import process

logger = logging.getLogger("etl.main")


if __name__ == "__main__":
    setup_logging()
    logger.info("Démarrage du pipeline ETL (Queue-Based). En attente de détections...", extra={"step": "pipeline_start"})

    try:
        for folder_path, current_client, status in watch():
            
            # --- 1. Rejet par le Watcher (Instable) ---
            if status in ["TIMEOUT", "TOO_MANY_FILES"]:
                import uuid
                run_id = str(uuid.uuid4())
                error_code = "WATCHER_TIMEOUT" if status == "TIMEOUT" else "WATCHER_TOO_MANY_FILES"
                append_event(run_id, current_client, "WatcherValidationFailed", {"error_code": error_code})
                archive_folder(folder_path, current_client, success=False, run_id=run_id)
                continue

            # --- 2. Mise en file d'attente immédiate ---
            if status == "READY":
                queue_manager.enqueue(folder_path, current_client)
                continue
                
            # --- 3. Dépilage au Heartbeat ---
            if status == "HEARTBEAT":
                queue = queue_manager.get_queue(limit=MAX_QUEUE_LIMIT)
                if queue:
                    logger.info(f"Heartbeat: {len(queue)} dossier(s) en file d'attente. Dépilage en cours...")
                    
                for q_folder, q_client in queue:
                    can_continue = process(q_folder, q_client)
                    if not can_continue:
                        logger.warning("Arrêt du dépilage suite à une erreur bloquante (Broker Queue).")
                        break # DB down or critical error, wait for next heartbeat

    except Exception as e:
        logger.critical(f"Crash critique du Main Loop: {e}")