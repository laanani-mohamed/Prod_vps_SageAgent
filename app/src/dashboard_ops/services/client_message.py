"""
client_message.py — Message d'erreur envoyé au client pour un run (fichier ERREUR_*.txt).
Zéro dépendance Streamlit.

Emplacements, du plus fiable au moins fiable :
  1. copie dans les logs : logs/message_client/<CLIENT>/<YYYY-MM-DD>/ERREUR_*.txt
  2. fichier d'origine du dossier d'upload (supprimé par le client ou la purge à 30 jours)
"""

import os
import re
from typing import List, Optional

from config.etl_config import CLIENT_MESSAGE_LOG_DIR

_FILENAME_DATE_RE = re.compile(r"ERREUR_(\d{4})(\d{2})(\d{2})_\d{6}\.txt$")
_ERROR_CODE_RE = re.compile(r"^error_code:\s*(\S+)", re.MULTILINE)


def _report_line(run_summary: dict) -> Optional[dict]:
    return next(
        (l for l in reversed(run_summary.get("raw_lines", [])) if l.get("step") == "error_report_written"),
        None,
    )


def _candidate_paths(client: str, line: dict) -> List[str]:
    paths = [line.get("message_log_path")]
    upload_path = line.get("path") or ""
    m = _FILENAME_DATE_RE.search(os.path.basename(upload_path))
    if m:
        date_dir = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        paths.append(os.path.join(CLIENT_MESSAGE_LOG_DIR, client, date_dir, os.path.basename(upload_path)))
    paths.append(upload_path)
    return [p for p in paths if p]


def read_client_message(client: str, run_summary: dict) -> Optional[str]:
    """Texte du message envoyé au client pour ce run, ou None s'il est introuvable."""
    line = _report_line(run_summary)
    if not line:
        return None
    for path in _candidate_paths(client, line):
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
    return None


def enrich_with_client_message(client: str, runs: List[dict]) -> List[dict]:
    """
    Ajoute `client_message` (texte ou None) et `client_message_sent` (bool) à chaque run.
    Complète `error_code` quand aucune ligne ERROR ne le porte (ex. rejets du watcher) :
    depuis la ligne de log du message, sinon depuis la section technique du message.
    """
    for run in runs:
        line = _report_line(run)
        run["client_message_sent"] = line is not None
        run["client_message"] = read_client_message(client, run) if line else None
        if not run.get("error_code") and line:
            code = line.get("error_code")
            if not code and run["client_message"]:
                m = _ERROR_CODE_RE.search(run["client_message"])
                code = m.group(1) if m else None
            run["error_code"] = code
    return runs
