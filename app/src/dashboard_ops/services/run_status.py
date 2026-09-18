"""
run_status.py — Regroupement des lignes de log par run_id et déduction du statut.
Logique métier pure (pas de Streamlit), opère sur les dicts déjà parsés par log_reader.
"""

from collections import OrderedDict
from typing import Dict, List, Optional

_STANDARD_KEYS = {"timestamp", "level", "logger", "message", "taskName"}


def group_by_run(lines: List[dict]) -> "OrderedDict[str, List[dict]]":
    """Regroupe les lignes par run_id, dans l'ordre de première apparition. Ignore les lignes sans run_id."""
    grouped: "OrderedDict[str, List[dict]]" = OrderedDict()
    for line in lines:
        run_id = line.get("run_id")
        if not run_id:
            continue
        grouped.setdefault(run_id, []).append(line)
    return grouped


def summarize_run(run_id: str, lines: List[dict]) -> dict:
    """
    Déduit le statut d'un run à partir de ses lignes de log :
      1. Ligne "archivage_success" : le champ "path" contient "/archives/" (SUCCESS)
         ou "/error/" (FAILED) — le nom du step est trompeur (utilisé pour les deux cas).
      2. À défaut, présence d'au moins une ligne ERROR -> FAILED.
      3. À défaut -> RUNNING (probablement encore en cours, ou log tronqué).
    """
    client = next((l.get("client") for l in lines if l.get("client")), None)
    started_at = lines[0].get("timestamp") if lines else None
    finished_at = lines[-1].get("timestamp") if lines else None

    archive_line = next(
        (l for l in reversed(lines) if l.get("step") == "archivage_success" and l.get("path")),
        None,
    )
    error_lines = [l for l in lines if l.get("level") == "ERROR"]

    status = "RUNNING"
    if archive_line:
        path = archive_line["path"]
        if "/archives/" in path:
            status = "SUCCESS"
        elif "/error/" in path:
            status = "FAILED"
        elif error_lines:
            status = "FAILED"
    elif error_lines:
        status = "FAILED"

    triggering_error = error_lines[0] if error_lines else None
    detail = {}
    if triggering_error:
        detail = {
            k: v for k, v in triggering_error.items()
            if k not in _STANDARD_KEYS and k not in ("run_id", "client")
        }

    archived_files = archive_line.get("fichiers_archives") if archive_line else None

    return {
        "run_id": run_id,
        "client": client,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "error_code": detail.get("error_code"),
        "table": detail.get("table"),
        "fichier": detail.get("fichier"),
        "col_position": detail.get("col_position"),
        "detail": detail,
        "archive_path": archive_line.get("path") if archive_line else None,
        "archived_files": archived_files,
        "raw_lines": lines,
    }


def list_runs_for_day(client: str, date_str: str, log_lines: Optional[List[dict]] = None) -> List[dict]:
    """
    `log_lines` : lignes déjà lues via log_reader.read_log_lines(client, date_str).
    Retourne la liste des RunSummary, triée du plus récent au plus ancien (par started_at).
    """
    if log_lines is None:
        log_lines = []
    grouped = group_by_run(log_lines)
    summaries = [summarize_run(run_id, lines) for run_id, lines in grouped.items()]
    summaries.sort(key=lambda s: s.get("started_at") or "", reverse=True)
    return summaries
