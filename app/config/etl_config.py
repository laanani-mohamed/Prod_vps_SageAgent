"""
etl_config.py
Configuration globale du pipeline ETL.
Tout ce qui peut changer selon l’environnement (DEV / TEST / PROD)
DOIT être défini ici, pas dans les modules métiers.
"""

# =========================
# FILESYSTEM PATHS

import os
from map_data.reference.file_table_map import FILE_TABLE_MAP

# Calcule dynamiquement le chemin racine absolu du projet (2 niveaux au-dessus du dossier config)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_ROOT = os.environ.get("STORAGE_ROOT", "/opt/SageAgent")

# Dossier racine où les clients déposent leurs fichiers
UPLOAD_BASE_PATH = os.path.join(STORAGE_ROOT, "storage_srv", "upload")

# Dossier où les imports réussis sont archivés
ARCHIVE_BASE_PATH = os.path.join(STORAGE_ROOT, "storage_srv", "archives")

# Dossier pour les imports en erreur
ERROR_BASE_PATH = os.path.join(STORAGE_ROOT, "storage_srv", "error")

# =========================
# WATCHER CONFIG

# Délai de stabilité (secondes sans modification)
WATCHER_STABILITY_DELAY = 5

# Intervalle entre deux scans du dossier upload
WATCHER_SCAN_INTERVAL = 15

# Nombre de fichiers attendus
MIN_EXPECTED_FILES = len(FILE_TABLE_MAP)

# Délai d'attente maximum (secondes) pour un upload incomplet (4 min)
WATCHER_UPLOAD_TIMEOUT = 30 #240


# =========================
# QUEUE CONFIG

# Nombre de dossiers à dépiler en un seul heartbeat
MAX_QUEUE_LIMIT = 10

# Chemins des dossiers
QUEUE_DIR = os.path.join(STORAGE_ROOT, "storage_srv", "queue")