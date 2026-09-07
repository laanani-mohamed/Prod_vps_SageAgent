"""
validator.py — Module de validation des fichiers avant l'ingestion.
"""
import os
import logging
from map_data.reference.file_table_map import FILE_TABLE_MAP

logger = logging.getLogger("etl.validator.files_names")

def validate_files(folder_path: str, client_schema: str, run_id: str) -> bool:
    """
    Vérifie que tous les fichiers requis (selon FILE_TABLE_MAP) sont présents dans le dossier.
    Ignore systématiquement les fichiers cachés (commençant par '.') comme le compteur .retries.
    Retourne True si le dossier est valide, False sinon.
    """
    expected_files_set = {f.upper() for f in FILE_TABLE_MAP.keys()}
    found_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and not f.startswith('.')]
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
        return False
        
    logger.info(f"Validation réussie — Tous les {len(found_files)} fichier(s) requis détecté(s).", 
                extra={"run_id": run_id, "client": client_schema, "step": "validation_success"})
    return True
