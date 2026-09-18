import logging
import os
import shutil
from datetime import datetime
from config.etl_config import ARCHIVE_BASE_PATH, ERROR_BASE_PATH, ERROR_REPORT_PREFIX

logger = logging.getLogger("etl.archiver")

def archive_folder(folder_path: str, client_schema: str, success: bool = True, run_id: str = None):
    """
    Ne supprime PAS le dossier racine du client (ex: /upload/Client_01).
    Déplace UNIQUEMENT les fichiers à l'intérieur en les horodatant.
    Succès  -> /archives/Client_XX/YYYY-MM-DD/
    Échec   -> /error/Client_XX/YYYY-MM-DD/
    (même logique de répartition client → date que pour les logs)
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    date_str = now.strftime("%Y-%m-%d")
    dest_root = ARCHIVE_BASE_PATH if success else ERROR_BASE_PATH

    dest_path = os.path.join(dest_root, client_schema, date_str)
    os.makedirs(dest_path, exist_ok=True)

    files_moved = 0
    archived_filenames = []
    try:
        for filename in os.listdir(folder_path):
            if filename.startswith('.'):
                continue # On ne déplace pas les fichiers cachés (comme .retries) dans les archives
            if filename.startswith(ERROR_REPORT_PREFIX):
                continue # Le rapport d'erreur reste visible dans le dossier d'upload du client

            src_file = os.path.join(folder_path, filename)
            if os.path.isfile(src_file):
                name, ext = os.path.splitext(filename)
                new_filename = f"{name}_{timestamp}{ext}"
                shutil.move(src_file, os.path.join(dest_path, new_filename))
                files_moved += 1
                archived_filenames.append(new_filename)

        if files_moved > 0:
            status = "archivés" if success else "mis en quarantaine (error)"
            logger.info(f"{files_moved} fichier(s) {status} vers : {dest_path}",
                        extra={"run_id": run_id, "client": client_schema, "path": dest_path,
                               "fichiers_archives": archived_filenames, "step": "archivage_success"})
        else:
            logger.warning(f"Aucun fichier trouvé à déplacer dans {folder_path}", 
                           extra={"run_id": run_id, "client": client_schema, "path": folder_path, "step": "archivage_empty"})

        # Nettoyage automatique : Si c'est un dossier temporaire (queue), on le supprime de force
        if "queue" in folder_path:
            try:
                shutil.rmtree(folder_path)
                logger.debug(f"Dossier de file d'attente nettoyé (avec ses fichiers cachés) : {folder_path}")
            except OSError:
                pass

    except PermissionError as e:
        logger.exception(f"Erreur de permissions d'archivage des fichiers de {folder_path} : {e}", 
                         extra={"run_id": run_id, "client": client_schema, "path": folder_path, "error_code": "FS_PERMISSION_ERROR", "step": "archivage_error"})
    except Exception as e:
        logger.exception(f"Erreur inconnue d'archivage des fichiers de {folder_path} : {e}", 
                         extra={"run_id": run_id, "client": client_schema, "path": folder_path, "error_code": "ARCHIVE_FAILED", "step": "archivage_error"})
