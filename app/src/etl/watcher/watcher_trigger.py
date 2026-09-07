import os
import time
import logging

from config.etl_config import UPLOAD_BASE_PATH, WATCHER_SCAN_INTERVAL

logger = logging.getLogger("etl.watcher_trigger")

def watch():
    """
    Générateur de surveillance par SÉMAPHORE (Trigger File).
    Méthode industrielle : au lieu d'un timer incertain, il attend
    que le processus d'envoi dépose un fichier nommé 'TRANSFERT_TERMINE.txt'.
    """
    logger.info(f"Démarrage du Watcher Sémaphore — Surveillance de : {UPLOAD_BASE_PATH}", 
                extra={"step": "surveillance_start", "path": UPLOAD_BASE_PATH})

    TRIGGER_FILE = "TRANSFERT_TERMINE.txt"

    while True:
        try:
            for item in os.listdir(UPLOAD_BASE_PATH):
                folder_path = os.path.join(UPLOAD_BASE_PATH, item)

                if not os.path.isdir(folder_path) or item.startswith('.'):
                    continue

                trigger_path = os.path.join(folder_path, TRIGGER_FILE)
                
                # Le dossier n'est prêt QUE si le trigger est physiquement présent
                if os.path.exists(trigger_path):
                    logger.info(f"[{item}] Sémaphore '{TRIGGER_FILE}' détecté. Transfert totalement achevé.", 
                                extra={"step": "surveillance_detect", "path": folder_path})
                    
                    # On supprime le sémaphore pour ne pas planter l'ingestion/validation
                    try:
                        os.remove(trigger_path)
                    except Exception as e:
                        logger.warning(f"Impossible de supprimer le sémaphore {trigger_path} : {e}")

                    # On transmet le dossier validé à main.py
                    yield folder_path, item
                else:
                    # S'il y a d'autres fichiers mais pas le trigger, on attend (SAGE exporte...)
                    target_files = [f for f in os.listdir(folder_path) if not f.startswith('.')]
                    if target_files:
                        logger.debug(f"[{item}] Fichiers présents mais aucun sémaphore '{TRIGGER_FILE}'. En attente de finalisation...", 
                                     extra={"step": "surveillance_waiting"})

        except PermissionError as e:
            logger.critical("Erreur permission lors de la boucle de surveillance", 
                             extra={"error_code": "FS_PERMISSION_ERROR", "step": "surveillance_error", "exception": str(e)})
        except Exception as e:
            logger.critical("Erreur inconnue dans la boucle de surveillance", 
                             extra={"error_code": "UNKNOWN_EXCEPTION", "step": "surveillance_error", "exception": str(e)})

        time.sleep(WATCHER_SCAN_INTERVAL)
