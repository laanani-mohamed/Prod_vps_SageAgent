"""
validator.py — Module de validation des fichiers avant l'ingestion.
"""
import os
import logging
from typing import Optional, Tuple
from map_data.reference.file_table_map import FILE_TABLE_MAP
from config.etl_config import ERROR_REPORT_PREFIX

logger = logging.getLogger("etl.validator.files_names")

def validate_files(folder_path: str, client_schema: str, run_id: str) -> Tuple[bool, Optional[dict]]:
    """
    Vérifie que tous les fichiers requis (selon FILE_TABLE_MAP) sont présents dans le dossier.
    Ignore systématiquement les fichiers cachés (commençant par '.') comme le compteur .retries,
    ainsi que les rapports d'erreur (préfixe ERROR_REPORT_PREFIX).
    Retourne (True, None) si le dossier est valide, (False, detail) sinon.
    """
    expected_files_set = {f.upper() for f in FILE_TABLE_MAP.keys()}
    found_files = [f for f in os.listdir(folder_path)
                   if os.path.isfile(os.path.join(folder_path, f))
                   and not f.startswith('.')
                   and not f.startswith(ERROR_REPORT_PREFIX)]
    found_files_upper = {f.upper() for f in found_files}

    if found_files_upper != expected_files_set:
        logger.error("Validation des fichiers échouée : mismatch avec FILE_TABLE_MAP",
                     extra={
                         "run_id": run_id,
                         "client": client_schema,
                         "expected_files": list(expected_files_set),
                         "found_files": found_files,
                         "error_code": "INVALID_INPUT_FILES",
                         "step": "validation_failed"
                     })
        return False, {
            "error_code": "INVALID_INPUT_FILES",
            "phase": "filename",
            "fichiers_attendus": sorted(expected_files_set),
            "fichiers_trouves": sorted(found_files_upper),
        }

    logger.info(f"Validation réussie — Tous les {len(found_files)} fichier(s) requis détecté(s).",
                extra={"run_id": run_id, "client": client_schema, "step": "validation_success"})
    return True, None
