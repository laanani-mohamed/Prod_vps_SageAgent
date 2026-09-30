"""
run_volumes.py — Volumétrie des fichiers d'un run et synthèse journalière des uploads.
Zéro dépendance Streamlit.

Source des chiffres d'un fichier, par ordre de priorité :
  1. `fichiers_stats` du log d'archivage (écrit par l'ETL depuis l'ajout de ces chiffres)
  2. calcul sur le fichier archivé (runs plus anciens, tant que le fichier n'est pas purgé)
"""
import os
from functools import lru_cache
from typing import Dict, List, Optional

from etl.utils.file_stats import file_stats
from services.log_reader import list_clients, list_dates, read_log_lines
from services.run_status import list_runs_for_day


def _archive_line(run: dict) -> Optional[dict]:
    return next(
        (l for l in reversed(run.get("raw_lines", [])) if l.get("step") == "archivage_success" and l.get("path")),
        None,
    )


@lru_cache(maxsize=4096)
def _stats_cached(path: str, mtime: float, size: int) -> dict:
    # mtime/size dans la clé : un fichier remplacé est recalculé
    return file_stats(path)


def run_files(run: dict) -> List[Dict]:
    """
    Une entrée par fichier du run : fichier, lignes, colonnes, taille (octets), disponible.
    `disponible=False` : fichier purgé et chiffres absents du log (lignes/colonnes/taille à None).
    """
    line = _archive_line(run)
    if not line:
        return []
    logged = {s["fichier"]: s for s in (line.get("fichiers_stats") or [])}
    out = []
    for name in line.get("fichiers_archives") or []:
        if name in logged:
            out.append({**logged[name], "disponible": True})
            continue
        path = os.path.join(line["path"], name)
        try:
            st = os.stat(path)
            out.append({**_stats_cached(path, st.st_mtime, st.st_size), "disponible": True})
        except OSError:
            out.append({"fichier": name, "lignes": None, "colonnes": None, "taille": None, "disponible": False})
    return out


def _run_size(run: dict) -> Optional[int]:
    """Taille totale déposée pour le run (octets) — sans compter les lignes : os.path.getsize suffit."""
    line = _archive_line(run)
    if not line:
        return None
    logged = {s["fichier"]: s["taille"] for s in (line.get("fichiers_stats") or [])}
    total, known = 0, False
    for name in line.get("fichiers_archives") or []:
        size = logged.get(name)
        if size is None:
            try:
                size = os.path.getsize(os.path.join(line["path"], name))
            except OSError:
                continue
        total += size
        known = True
    return total if known else None


def daily_summary(date_from: str, date_to: str, client: Optional[str] = None) -> List[Dict]:
    """
    Une ligne par (jour, client) sur la période [date_from, date_to] (YYYY-MM-DD, dates des logs) :
    date, client, succes, echecs, en_cours, taille (octets déposés). `client=None` = tous les clients.
    """
    rows = []
    for c in ([client] if client else list_clients()):
        for d in list_dates(c):
            if not (date_from <= d <= date_to):
                continue
            runs = list_runs_for_day(c, d, read_log_lines(c, d))
            if not runs:
                continue
            rows.append({
                "date": d,
                "client": c,
                "succes": sum(r["status"] == "SUCCESS" for r in runs),
                "echecs": sum(r["status"] == "FAILED" for r in runs),
                "en_cours": sum(r["status"] == "RUNNING" for r in runs),
                "taille": sum(_run_size(r) or 0 for r in runs),
            })
    rows.sort(key=lambda r: (r["date"], r["client"]))
    return rows
