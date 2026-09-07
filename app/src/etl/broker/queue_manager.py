import os
import shutil
import logging
from datetime import datetime
from config.etl_config import QUEUE_DIR, ERROR_BASE_PATH

logger = logging.getLogger("etl.queue_manager")

def enqueue(folder_path: str, client_schema: str) -> str:
    """
    Déplace instantanément les fichiers validés vers la file d'attente (broker_queue)
    en ajoutant un timestamp strict pour garantir l'ordre chronologique (FIFO).
    On déplace uniquement le contenu pour ne pas casser les permissions du dossier SFTP parent.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_folder_name = f"{client_schema}__{timestamp}"
    destination_path = os.path.join(QUEUE_DIR, new_folder_name)
    
    try:
        os.makedirs(destination_path, exist_ok=True)
        files_moved = 0
        
        for filename in os.listdir(folder_path):
            if filename.startswith('.'):
                continue
            src_file = os.path.join(folder_path, filename)
            dst_file = os.path.join(destination_path, filename)
            if os.path.isfile(src_file):
                shutil.move(src_file, dst_file)
                files_moved += 1
                
        logger.debug(f"[Queue] Mise en file d'attente : {new_folder_name} ({files_moved} fichiers)")
        return destination_path
    except Exception as e:
        logger.error(f"[Queue] Échec de la mise en file d'attente pour {client_schema} : {e}")
        return folder_path


def get_queue(limit: int = 5) -> list:
    """
    Récupère les N dossiers les plus anciens en attente.
    Retourne une liste de tuples (chemin_absolu_du_dossier, nom_du_client).
    
    [Mise à jour : Dead Letter Queue / Poison Pill]
    Cette fonction implémente un système de Retry via un fichier caché '.retries'.
    Si un dossier provoque un crash du Worker (Poison Pill), il restera dans la queue.
    Au 3ème essai, il sera considéré comme empoisonné et éjecté de force vers le dossier 'error/'.
    """
    if not os.path.exists(QUEUE_DIR):
        return []
        
    folders = []
    for item in os.listdir(QUEUE_DIR):
        item_path = os.path.join(QUEUE_DIR, item)
        if os.path.isdir(item_path) and "__" in item:
            folders.append(item)
            
    # Le tri alphabétique garantit le FIFO grâce au format YYYYMMDD_HHMMSS
    folders.sort()
    
    # Appliquer le quota (SLA Anti-Famine Inverse)
    folders_to_process = folders[:limit]
    
    queue_items = []
    
    for f in folders_to_process:
        client_schema = f.split("__")[0]
        abs_path = os.path.join(QUEUE_DIR, f)
        
        # --- Gestion des Retries (Dead Letter Queue) ---
        retry_file = os.path.join(abs_path, ".retries")
        retries = 0
        if os.path.exists(retry_file):
            try:
                with open(retry_file, "r") as rf:
                    retries = int(rf.read().strip())
            except Exception:
                retries = 0
                
        if retries >= 3:
            # Poison Pill detectée ! On déplace dans error
            error_dest = os.path.join(ERROR_BASE_PATH, f"{client_schema}_POISON_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(ERROR_BASE_PATH, exist_ok=True)
            try:
                shutil.move(abs_path, error_dest)
                logger.critical(f"[DLQ] Pilule empoisonnée détectée pour {client_schema}. Dossier déplacé vers {error_dest}")
            except Exception as e:
                logger.error(f"[DLQ] Impossible de déplacer le dossier empoisonné {abs_path} : {e}")
            continue # On saute ce dossier
            
        # Incrémenter le compteur pour le crash potentiel à venir
        try:
            with open(retry_file, "w") as rf:
                rf.write(str(retries + 1))
        except Exception as e:
            logger.error(f"[DLQ] Impossible d'écrire le compteur de retry pour {abs_path} : {e}")

        queue_items.append((abs_path, client_schema))
        
    return queue_items
