import os
import logging
from typing import Optional, Tuple
from config.etl_config import ERROR_REPORT_PREFIX

logger = logging.getLogger("etl.validator.files_sizes")

def validate_sizes(folder_path: str, client_schema: str, run_id: str) -> Tuple[bool, Optional[dict]]:
    """
    Examine chaque fichier dans le répertoire ciblé.
    Ignore systématiquement les fichiers cachés (commençant par '.') comme le compteur .retries,
    ainsi que les rapports d'erreur (préfixe ERROR_REPORT_PREFIX).
    Renvoie (False, detail) si au moins un des fichiers a un poids de 0 octet, (True, None) sinon.
    """
    is_valid = True
    empty_files = []

    for filename in os.listdir(folder_path):
        if filename.startswith('.') or filename.startswith(ERROR_REPORT_PREFIX):
            continue
        fpath = os.path.join(folder_path, filename)
        if os.path.isfile(fpath):
            if os.path.getsize(fpath) == 0:
                empty_files.append(filename)
                is_valid = False

    if empty_files:
        logger.error(f"Validation échouée. Fichiers vides (0 octet) : {', '.join(empty_files)}",
                     extra={
                         "run_id": run_id,
                         "client": client_schema,
                         "error_code": "EMPTY_FILES",
                         "empty_files": empty_files,
                         "step": "validation_failed"
                     })
        return False, {
            "error_code": "EMPTY_FILES",
            "phase": "size",
            "fichiers": empty_files,
        }

    logger.info("Validation des tailles réussie (aucun fichier vide).",
                extra={"run_id": run_id, "client": client_schema, "step": "validation_success"})
    return True, None
