"""
log_reader.py — Lecture brute des logs JSON du pipeline ETL.
Zéro dépendance Streamlit : ne fait que parser des fichiers, pas de logique métier.
"""

import os
import json
from typing import List, Dict

from config.etl_config import ETL_LOG_DIR, ETL_ERROR_LOG_DIR

_EXCLUDED_CLIENT_FOLDERS = {"_general"}


def list_clients() -> List[str]:
    """Sous-dossiers de logs/etl.log/, hors dossier générique '_general'."""
    if not os.path.isdir(ETL_LOG_DIR):
        return []
    return sorted(
        d for d in os.listdir(ETL_LOG_DIR)
        if os.path.isdir(os.path.join(ETL_LOG_DIR, d)) and d not in _EXCLUDED_CLIENT_FOLDERS
    )


def list_dates(client: str) -> List[str]:
    """Dates (YYYY-MM-DD) disponibles pour un client, triées les plus récentes d'abord."""
    client_dir = os.path.join(ETL_LOG_DIR, client)
    if not os.path.isdir(client_dir):
        return []
    dates = [
        f[:-4] for f in os.listdir(client_dir)
        if f.endswith(".log")
    ]
    return sorted(dates, reverse=True)


def read_log_lines(client: str, date_str: str, errors_only: bool = False) -> List[Dict]:
    """
    Parse les lignes JSON de logs/etl.log/<client>/<date>.log (ou etl_error.log si
    errors_only=True). Ignore silencieusement les lignes corrompues/non-JSON.
    """
    base_dir = ETL_ERROR_LOG_DIR if errors_only else ETL_LOG_DIR
    filepath = os.path.join(base_dir, client, f"{date_str}.log")
    if not os.path.isfile(filepath):
        return []

    lines = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                lines.append(json.loads(raw_line))
            except json.JSONDecodeError:
                continue
    return lines
