import logging
from logging.handlers import RotatingFileHandler
import json
import os
import sys
from datetime import datetime, timezone

class CustomJSONFormatter(logging.Formatter):
    """
    Formatteur de logs JSON personnalisé pour garantir que tous les logs 
    soient émis sous forme de structure JSON standardisée.
    """
    def format(self, record):
        # Format the standard timestamp if not set
        if not hasattr(record, 'asctime'):
            record.asctime = datetime.now(timezone.utc).strftime('%H:%M:%S')

        # Construction du dictionnaire JSON de base
        log_record = {
            "timestamp": record.asctime,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }

        # Pour les exceptions (stack trace)
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Attributs standard du module 'logging' que l'on veut ignorer 
        # lorsqu'on check le record.__dict__ pour d'autres attributs de l'`extra`
        ignore_keys = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module',
            'msecs', 'message', 'msg', 'name', 'pathname', 'process',
            'processName', 'relativeCreated', 'stack_info', 'thread', 'threadName'
        }

        # Injection des attributs "extra" spécifiés dynamiquement dans l'appel du log
        for key, value in record.__dict__.items():
            if key not in ignore_keys:
                log_record[key] = value

        return json.dumps(log_record, ensure_ascii=False)

def setup_logging():
    """
    Configure la racine de l'architecture de logging centralisée pour le pipeline ETL.
    Cette fonction ne doit être appelée qu'une seule fois au démarrage par main.py.
    """
    # Chemin absolu du dossier logs, calculé depuis l'emplacement de ce fichier
    # → fonctionne quel que soit le répertoire depuis lequel main.py est lancé
    _config_dir  = os.path.dirname(os.path.abspath(__file__))   # .../config/
    _project_root = os.path.dirname(_config_dir)                 # .../Project 1/
    log_dir = os.path.join(_project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Chemins des fichiers logs
    etl_log_path       = os.path.join(log_dir, "etl.log")
    etl_error_log_path = os.path.join(log_dir, "etl_error.log")

    # Création du Formatter
    json_formatter = CustomJSONFormatter()

    # Configuration du logger racine "etl"
    logger = logging.getLogger("etl")
    logger.setLevel(logging.DEBUG)  # On capte tout, et on filtre dans les handlers

    # On nettoie les handlers pré-existants s'il y en a (éviter les doublons)
    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. Console Handler (Niveau INFO+)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(json_formatter)

    # 2. File Handler Global (Niveau INFO+) avec rotation
    file_handler = RotatingFileHandler(
        etl_log_path, maxBytes=50 * 1024 * 1024, backupCount=10, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(json_formatter)

    # 3. File Handler Erreurs (Niveau ERROR+) avec rotation
    error_file_handler = RotatingFileHandler(
        etl_error_log_path, maxBytes=50 * 1024 * 1024, backupCount=10, encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(json_formatter)

    # Ajout des handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_file_handler)

    # Empêcher la propagation au root logger par défaut (pour éviter des logs doublés sur stdout)
    logger.propagate = False
