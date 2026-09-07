import logging
import uuid
from etl.validation.val_files_names import validate_files
from etl.validation.val_files_sizes import validate_sizes
from etl.validation.val_schema_quality import validate_schema_quality
from etl.ingestion.ingestor import ingest
from etl.archive.archiver import archive_folder
from etl.orchestration.event_store import append_event
from etl.orchestration.pipeline_state import init_state, fail_state, complete_state, update_step

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
        
    try:
        # --- Validation Noms ---
        if not validate_files(folder_path, client_schema, run_id):
            append_event(run_id, client_schema, "FilenameValidationFailed", {"error_code": "INVALID_INPUT_FILES"})
            fail_state(run_id, client_schema, "validation", "INVALID_INPUT_FILES", "Noms de fichiers non conformes.")
            archive_folder(folder_path, client_schema, success=False, run_id=run_id)
            append_event(run_id, client_schema, "ArchiveCompleted", {"destination": "error"})
            return True # Data error, not infra

        append_event(run_id, client_schema, "FilenameValidationPassed", {"folder": folder_path})

        # --- Validation Tailles ---
        if not validate_sizes(folder_path, client_schema, run_id):
            append_event(run_id, client_schema, "SizeValidationFailed", {"error_code": "EMPTY_FILES"})
            fail_state(run_id, client_schema, "validation", "EMPTY_FILES", "Fichier(s) vide(s).")
            archive_folder(folder_path, client_schema, success=False, run_id=run_id)
            append_event(run_id, client_schema, "ArchiveCompleted", {"destination": "error"})
            return True
                
        append_event(run_id, client_schema, "SizeValidationPassed", {})

        # --- Validation Schéma ---
        if not validate_schema_quality(folder_path, client_schema, run_id):
            append_event(run_id, client_schema, "SchemaValidationFailed", {"error_code": "SCHEMA_QUALITY_FAILED"})
            fail_state(run_id, client_schema, "validation", "SCHEMA_QUALITY_FAILED", "Schéma non conforme.")
            archive_folder(folder_path, client_schema, success=False, run_id=run_id)
            append_event(run_id, client_schema, "ArchiveCompleted", {"destination": "error"})
            return True
                
        append_event(run_id, client_schema, "SchemaValidationPassed", {})
        update_step(run_id, client_schema, "validation", "SUCCESS", "ingestion")

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
                return True
            
        # --- Succès ---
        append_event(run_id, client_schema, "IngestionCompleted", {})
        update_step(run_id, client_schema, "ingestion", "SUCCESS", "archivage")
        archive_folder(folder_path, client_schema, success=True, run_id=run_id)
        append_event(run_id, client_schema, "ArchiveCompleted", {"destination": "success"})
        complete_state(run_id, client_schema)
        return True

    except Exception as e:
        logger.error(f"Erreur inattendue dans process: {e}")
        append_event(run_id, client_schema, "PipelineFailed", {"error_code": "UNEXPECTED_ERROR", "error_message": str(e)})
        return False # Dans le doute d'un crash global, on stop la queue
