"""
Script de maintenance ETL : Purge automatique des dossiers de stockage.
Remplace l'ancien script bash. Il compte les suppressions, calcule l'espace libéré,
et injecte l'événement dans PostgreSQL via Event Sourcing.
Exécution recommandée : Quotidiennement via Cronjob.
"""

import os
import time
import logging
import sys

# Ajouter le root path pour les imports absolus
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from etl.orchestration.event_store import append_event

# Configuration basique de logging pour ce script utilitaire
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("etl.purge")

BASE_DIR = os.path.join(PROJECT_ROOT, "storage_srv")
ARCHIVES_DIR = os.path.join(BASE_DIR, "archives")
ERROR_DIR = os.path.join(BASE_DIR, "error")

RETENTION_DAYS = 30
SYSTEM_UUID = "00000000-0000-0000-0000-000000000000"

def purge_directory(directory: str, max_age_days: int) -> tuple[int, float]:
    """
    Parcourt un dossier, supprime les fichiers plus vieux que max_age_days.
    Retourne (nombre_fichiers_supprimes, megaoctets_liberes).
    """
    if not os.path.exists(directory):
        logger.warning(f"Le dossier {directory} n'existe pas.")
        return 0, 0.0

    deleted_count = 0
    freed_bytes = 0
    now = time.time()
    cutoff = now - (max_age_days * 86400)

    for root, _, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                file_stat = os.stat(filepath)
                if file_stat.st_mtime < cutoff:
                    freed_bytes += file_stat.st_size
                    os.remove(filepath)
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Erreur lors de la suppression de {filepath} : {e}")

    freed_mb = freed_bytes / (1024 * 1024)
    return deleted_count, freed_mb

def main():
    logger.info(f"Début de la purge des archives ETL (Rétention : {RETENTION_DAYS} jours)")
    
    total_deleted = 0
    total_freed_mb = 0.0

    # Purge Archives
    logger.info(f"Scan de {ARCHIVES_DIR}...")
    c, mb = purge_directory(ARCHIVES_DIR, RETENTION_DAYS)
    total_deleted += c
    total_freed_mb += mb

    # Purge Errors
    logger.info(f"Scan de {ERROR_DIR}...")
    c, mb = purge_directory(ERROR_DIR, RETENTION_DAYS)
    total_deleted += c
    total_freed_mb += mb

    logger.info(f"Purge terminée. Fichiers supprimés : {total_deleted}. Espace libéré : {total_freed_mb:.2f} MB")

    # Si on a supprimé des fichiers, on trace l'événement
    if total_deleted > 0:
        event_payload = {
            "retention_days": RETENTION_DAYS,
            "deleted_files": total_deleted,
            "freed_space_mb": round(total_freed_mb, 2)
        }
        success = append_event(SYSTEM_UUID, "SYSTEM", "ArchivePurged", event_payload)
        if success:
            logger.info("Événement ArchivePurged enregistré avec succès dans l'Event Store.")
        else:
            logger.error("Échec de l'enregistrement de l'événement dans l'Event Store.")
    else:
        logger.info("Aucun fichier supprimé, aucun événement généré.")

if __name__ == "__main__":
    main()
