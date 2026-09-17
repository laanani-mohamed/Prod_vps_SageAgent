import logging
from logging.handlers import RotatingFileHandler
import json
import os
import re
import sys
from datetime import datetime, timezone

# Client sans info explicite dans le log (ex: démarrage, heartbeat du watcher)
_GENERAL_LOG_FOLDER = "_general"
_SAFE_FOLDER_PATTERN = re.compile(r'[^a-zA-Z0-9_\-]')


class ClientDateRotatingFileHandler(logging.Handler):
    """
    Handler qui répartit les logs par client puis par date, à l'image de
    l'arborescence storage_srv/<categorie>/<client>/... :

        logs/etl.log/<CLIENT>/<YYYY-MM-DD>.log
        logs/etl_error.log/<CLIENT>/<YYYY-MM-DD>.log

    Le client est lu depuis l'attribut `client` passé en `extra=` par les
    appels de log ETL ; à défaut (logs génériques sans client), les entrées
    sont regroupées dans un dossier `_general`.
    """

    def __init__(self, base_dir: str, level=logging.NOTSET):
        super().__init__(level)
        self.base_dir = base_dir
        self._handlers: dict[tuple[str, str], logging.FileHandler] = {}

    def _safe_folder_name(self, name: str) -> str:
        return _SAFE_FOLDER_PATTERN.sub('_', name) or _GENERAL_LOG_FOLDER

    def _get_file_handler(self, client: str, date_str: str) -> logging.FileHandler:
        key = (client, date_str)
        handler = self._handlers.get(key)
        if handler is None:
            client_dir = os.path.join(self.base_dir, client)
            os.makedirs(client_dir, exist_ok=True)
            handler = logging.FileHandler(
                os.path.join(client_dir, f"{date_str}.log"), encoding='utf-8'
            )
            handler.setFormatter(self.formatter)
            self._handlers[key] = handler
        return handler

    def emit(self, record: logging.LogRecord) -> None:
        try:
            client = getattr(record, 'client', None)
            client = self._safe_folder_name(client) if client else _GENERAL_LOG_FOLDER
            date_str = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime('%Y-%m-%d')
            self._get_file_handler(client, date_str).emit(record)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        for handler in self._handlers.values():
            handler.close()
        super().close()

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

    # Dossiers racines des logs, subdivisés ensuite par client puis par date
    # (ex: logs/etl.log/MULIPARTS/2026-09-17.log), à l'image de storage_srv/.
    etl_log_dir       = os.path.join(log_dir, "etl.log")
    etl_error_log_dir = os.path.join(log_dir, "etl_error.log")

    # Migration : etl.log / etl_error.log existaient auparavant comme fichiers plats.
    # On les conserve (renommés) plutôt que de les écraser en créant le dossier.
    for path in (etl_log_dir, etl_error_log_dir):
        if os.path.isfile(path):
            os.rename(path, path + ".legacy")
    os.makedirs(etl_log_dir, exist_ok=True)
    os.makedirs(etl_error_log_dir, exist_ok=True)

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

    # 2. File Handler Global (Niveau INFO+), réparti par client puis par date
    file_handler = ClientDateRotatingFileHandler(etl_log_dir)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(json_formatter)

    # 3. File Handler Erreurs (Niveau ERROR+), réparti par client puis par date
    error_file_handler = ClientDateRotatingFileHandler(etl_error_log_dir)
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(json_formatter)

    # Ajout des handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_file_handler)

    # Empêcher la propagation au root logger par défaut (pour éviter des logs doublés sur stdout)
    logger.propagate = False
