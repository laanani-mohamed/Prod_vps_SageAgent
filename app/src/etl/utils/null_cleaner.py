import os
import re
import logging

logger = logging.getLogger("etl.null_cleaner")

def clean_null_values(folder_path: str, run_id: str = "N/A", client_schema: str = "N/A"):
    """
    Parcourt tous les fichiers du dossier et remplace les mots textuels 'NULL' 
    par des vides afin que PostgreSQL les interprète correctement lors du COPY.
    """
    if not os.path.exists(folder_path):
        return

    files_cleaned = 0
    for filename in os.listdir(folder_path):
        filepath = os.path.join(folder_path, filename)
        
        if os.path.isfile(filepath):
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Remplace le mot entier 'NULL' par une chaîne vide
            new_content = re.sub(r'\bNULL\b', '', content)
            
            # Réécrire si des changements ont été faits
            if content != new_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                files_cleaned += 1
                logger.info(f"[Nettoyage NULL] Fichier nettoyé : {filename}", 
                            extra={"run_id": run_id, "client": client_schema, "step": "null_cleaner"})
    
    if files_cleaned > 0:
        logger.info(f"[Nettoyage NULL] {files_cleaned} fichier(s) nettoyé(s) des valeurs NULL textuelles.", 
                    extra={"run_id": run_id, "client": client_schema, "step": "null_cleaner_summary"})
