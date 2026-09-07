import os
import time
import logging
from config.etl_config import UPLOAD_BASE_PATH, WATCHER_STABILITY_DELAY, WATCHER_SCAN_INTERVAL, MIN_EXPECTED_FILES, WATCHER_UPLOAD_TIMEOUT

logger = logging.getLogger("etl.watcher")

def _is_folder_stable(folder_path: str) -> bool:
    """
    Vérifie que tous les fichiers du dossier n'ont pas été modifiés
    depuis STABILITY_DELAY secondes (protection contre les uploads partiels).
    """
    now = time.time()
    for filename in os.listdir(folder_path):
        fpath = os.path.join(folder_path, filename)
        if os.path.isfile(fpath):
            if now - os.stat(fpath).st_mtime < WATCHER_STABILITY_DELAY:
                return False
    return True

def watch():
    """
    Générateur de surveillance (Polling).
    Responsabilité unique : détecter les dossiers clients stables et les signaler.
    Produit (yield) un tuple (folder_path, client_schema) dès qu'un dossier est prêt.
    L'orchestration (ingestor + archiver) est entièrement gérée par main.py.
    """
    logger.info(f"Démarrage du Watcher ETL — Surveillance de : {UPLOAD_BASE_PATH}", 
                extra={"step": "surveillance_start", "path": UPLOAD_BASE_PATH})

    while True:
        try:
            for item in os.listdir(UPLOAD_BASE_PATH):
                folder_path = os.path.join(UPLOAD_BASE_PATH, item)

                # Ignorer les fichiers et les dossiers cachés (ex: .DS_Store)
                if not os.path.isdir(folder_path) or item.startswith('.'):
                    continue

                # Ignorer les dossiers complètement vides
                files_in_dir = [f for f in os.listdir(folder_path)
                                 if os.path.isfile(os.path.join(folder_path, f))]
                if not files_in_dir:
                    continue

                logger.info(f"[{item}] Scan : {len(files_in_dir)} fichier(s) présent(s).", 
                            extra={"step": "surveillance_scan", "path": folder_path, "found": len(files_in_dir)})

                # Attendre la fin du transfert FTP/réseau
                if not _is_folder_stable(folder_path):
                    logger.info(f"[{item}] Upload en cours (fichiers instables), on attend...", 
                                 extra={"step": "surveillance_wait_upload", "path": folder_path})
                    continue

                # Dossier stable : Vérification du nombre de fichiers
                if len(files_in_dir) == MIN_EXPECTED_FILES:
                    logger.info(f"[{item}] Dossier stable et complet détecté → Transmission à l'orchestrateur.", 
                                extra={"step": "surveillance_detect", "path": folder_path})
                    yield folder_path, item, "READY"
                elif len(files_in_dir) > MIN_EXPECTED_FILES:
                    logger.error(f"[{item}] Trop de fichiers détectés : {len(files_in_dir)}/{MIN_EXPECTED_FILES}. Rejet.", 
                                 extra={"step": "surveillance_too_many", "path": folder_path})
                    yield folder_path, item, "TOO_MANY_FILES"
                else:
                    # Calculer l'âge du plus vieux fichier pour le timeout
                    oldest_file_time = min(os.stat(os.path.join(folder_path, f)).st_mtime for f in files_in_dir)
                    if time.time() - oldest_file_time > WATCHER_UPLOAD_TIMEOUT:
                        logger.warning(f"[{item}] Timeout atteint : {len(files_in_dir)}/{MIN_EXPECTED_FILES} fichiers après délai imparti.", 
                                       extra={"step": "surveillance_timeout", "path": folder_path})
                        yield folder_path, item, "TIMEOUT"
                    else:
                        logger.info(f"[{item}] Fichiers manquants ({len(files_in_dir)}/{MIN_EXPECTED_FILES}). En attente...", 
                                     extra={"step": "surveillance_wait_files", "path": folder_path})
                        continue
        except PermissionError as e:
            logger.critical("Erreur permission lors de la boucle de surveillance", 
                             extra={"error_code": "FS_PERMISSION_ERROR", "step": "surveillance_error", "exception": str(e)})
        except Exception as e:
            logger.critical("Erreur inconnue dans la boucle de surveillance", 
                             extra={"error_code": "UNKNOWN_EXCEPTION", "step": "surveillance_error", "exception": str(e)})

        # Envoi du battement de coeur pour réveiller le traitement de la file d'attente (dépileur)
        yield None, "SYSTEM", "HEARTBEAT"
        time.sleep(WATCHER_SCAN_INTERVAL)

