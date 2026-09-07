import os
import time
import logging

from config.etl_config import ARCHIVE_BASE_PATH, ERROR_BASE_PATH

# Configuration basique du logger car ce script est pensé
# pour tourner hors de l'ETL (via cron) et piper la sortie vers syslog.
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("etl.purge")

RETENTION_DAYS = 30
RETENTION_SECONDS = RETENTION_DAYS * 86400

def purge_old_archives():
    """
    Parcourt les dossiers d'archives et d'erreurs et supprime physiquement
    les fichiers datant de plus de 30 jours, ainsi que les répertoires vides.
    Idéal via un Crontab : `0 2 * * 0 php /opt/etl_sage/venv/bin/python etl/utils/purge_archives.py`
    """
    logger.info(f"Démarrage purge Cron - Rétention configurée à > {RETENTION_DAYS} jours.")
    now = time.time()
    
    deleted_files_count = 0

    for base_dir in [ARCHIVE_BASE_PATH, ERROR_BASE_PATH]:
        if not os.path.exists(base_dir):
            continue
            
        # topdown=False oblige à vider les dossiers enfants avant les parents
        for root, dirs, files in os.walk(base_dir, topdown=False):
            # 1. Purge des fichiers périmés
            for name in files:
                filepath = os.path.join(root, name)
                # Date de dernière modification
                if now - os.path.getmtime(filepath) > RETENTION_SECONDS:
                    try:
                        os.remove(filepath)
                        deleted_files_count += 1
                        logger.debug(f"Jeté (Périmé): {filepath}")
                    except Exception as e:
                        logger.error(f"Échec suppression fichier {filepath}: {e}")
            
            # 2. Nettoyage des dossiers devenus vides suite aux purges
            for name in dirs:
                dirpath = os.path.join(root, name)
                # os.listdir(dirpath) == [] est True si dossier vide
                if not os.listdir(dirpath):
                    try:
                        os.rmdir(dirpath)
                        logger.info(f"Dossier vide supprimé: {dirpath}")
                    except Exception as e:
                        logger.warning(f"Impossible de supprimer le dossier vide {dirpath}: {e}")

    logger.info(f"Purge terminée. {deleted_files_count} fichier(s) très ancien(s) supprimé(s).")

if __name__ == "__main__":
    purge_old_archives()
