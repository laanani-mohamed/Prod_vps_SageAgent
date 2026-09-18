import logging
import os
import uuid
from etl.validation.val_files_names import validate_files
from etl.validation.val_files_sizes import validate_sizes
from etl.validation.val_schema_quality import validate_schema_quality
from etl.ingestion.ingestor import ingest
from etl.archive.archiver import archive_folder
from etl.orchestration.event_store import append_event
from etl.orchestration.pipeline_state import init_state, fail_state, complete_state
from etl.reporting.error_report import write_error_report, purge_old_error_reports
from config.etl_config import UPLOAD_BASE_PATH

logger = logging.getLogger("etl.worker")

"""
Worker dédié au traitement d'un dossier client (Validation -> Ingestion -> Archivage).
Isolé de l'orchestrateur central pour permettre une meilleure évolutivité et lisibilité.
"""
    
def process(folder_path: str, client_schema: str) -> bool:
    """
    Traite un dossier depuis la file d'attente.
    Retourne False UNIQUEMENT si une erreur d'infrastructure bloque le système.
    """
    run_id = str(uuid.uuid4())
    init_state(run_id, client_schema)

    # NB: folder_path pointe vers le dossier de file d'attente temporaire
    # (storage_srv/queue/<client>__<timestamp>/), pas vers le dossier d'upload
    # SFTP du client (déjà vidé par queue_manager.enqueue avant l'appel à process()).
    # Le rapport d'erreur doit être visible par le client : on cible donc toujours
    # son vrai dossier d'upload, pas folder_path.
    upload_folder = os.path.join(UPLOAD_BASE_PATH, client_schema)
    purge_old_error_reports(upload_folder)

    try:
        # --- Validation Noms ---
        ok, detail = validate_files(folder_path, client_schema, run_id)
        if not ok:
            append_event(run_id, client_schema, "FilenameValidationFailed", {"error_code": "INVALID_INPUT_FILES"})
            fail_state(run_id, client_schema, "validation", "INVALID_INPUT_FILES", "Noms de fichiers non conformes.")
            archive_folder(folder_path, client_schema, success=False, run_id=run_id)
            append_event(run_id, client_schema, "ArchiveCompleted", {"destination": "error"})
            write_error_report(upload_folder, client_schema, run_id, detail)
            return True # Data error, not infra

        append_event(run_id, client_schema, "FilenameValidationPassed", {"folder": folder_path})

        # --- Validation Tailles ---
        ok, detail = validate_sizes(folder_path, client_schema, run_id)
        if not ok:
            append_event(run_id, client_schema, "SizeValidationFailed", {"error_code": "EMPTY_FILES"})
            fail_state(run_id, client_schema, "validation", "EMPTY_FILES", "Fichier(s) vide(s).")
            archive_folder(folder_path, client_schema, success=False, run_id=run_id)
            append_event(run_id, client_schema, "ArchiveCompleted", {"destination": "error"})
            write_error_report(upload_folder, client_schema, run_id, detail)
            return True

        append_event(run_id, client_schema, "SizeValidationPassed", {})

        # --- Validation Schéma ---
        ok, detail = validate_schema_quality(folder_path, client_schema, run_id)
        if not ok:
            append_event(run_id, client_schema, "SchemaValidationFailed", {"error_code": "SCHEMA_QUALITY_FAILED"})
            fail_state(run_id, client_schema, "validation", "SCHEMA_QUALITY_FAILED", "Schéma non conforme.")
            archive_folder(folder_path, client_schema, success=False, run_id=run_id)
            append_event(run_id, client_schema, "ArchiveCompleted", {"destination": "error"})
            write_error_report(upload_folder, client_schema, run_id, detail)
            return True

        append_event(run_id, client_schema, "SchemaValidationPassed", {})

        # --- Ingestion ---
        append_event(run_id, client_schema, "IngestionStarted", {"folder": folder_path})
        success, err_type, err_code = ingest(folder_path, client_schema, run_id)

        if not success:
            if err_type == "INFRA_ERROR":
                logger.warning(f"[{client_schema}] Erreur Infrastructure ({err_code}). Broker Queue activé.")
                append_event(run_id, client_schema, "IngestionFailed", {"error_code": err_code, "error_type": "INFRA_ERROR"})
                append_event(run_id, client_schema, "BrokerQueueTripped", {"folder": folder_path})
                fail_state(run_id, client_schema, "ingestion", err_code, "Erreur Infrastructure DB.")
                return False # STOP QUEUE PROCESSING
            else:
                logger.error(f"[{client_schema}] Erreur de données lors de l'ingestion ({err_code}).")
                append_event(run_id, client_schema, "IngestionFailed", {"error_code": err_code, "error_type": "DATA_ERROR"})
                fail_state(run_id, client_schema, "ingestion", err_code, "Erreur d'intégrité des données.")
                archive_folder(folder_path, client_schema, success=False, run_id=run_id)
                append_event(run_id, client_schema, "ArchiveCompleted", {"destination": "error"})
                write_error_report(upload_folder, client_schema, run_id, {"error_code": err_code, "phase": "ingestion"})
                return True
            
        # --- Succès ---
        append_event(run_id, client_schema, "IngestionCompleted", {})
        archive_folder(folder_path, client_schema, success=True, run_id=run_id)
        append_event(run_id, client_schema, "ArchiveCompleted", {"destination": "success"})
        complete_state(run_id, client_schema)
        return True

    except Exception as e:
        logger.error(f"Erreur inattendue dans process: {e}")
        append_event(run_id, client_schema, "PipelineFailed", {"error_code": "UNEXPECTED_ERROR", "error_message": str(e)})
        return False # Dans le doute d'un crash global, on stop la queue
