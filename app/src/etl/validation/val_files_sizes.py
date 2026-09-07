import os
import logging

logger = logging.getLogger("etl.validator.files_sizes")

def validate_sizes(folder_path: str, client_schema: str, run_id: str) -> bool:
    """
    Examine chaque fichier dans le répertoire ciblé.
    Ignore systématiquement les fichiers cachés (commençant par '.') comme le compteur .retries.
    Renvoie False immédiatement si au moins un des fichiers a un poids de 0 octet.
    """
    is_valid = True
    empty_files = []
    
    for filename in os.listdir(folder_path):
        if filename.startswith('.'):
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
    else:
        logger.info("Validation des tailles réussie (aucun fichier vide).", 
                    extra={"run_id": run_id, "client": client_schema, "step": "validation_success"})
        
    return is_valid
