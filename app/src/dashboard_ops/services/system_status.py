"""
system_status.py — État des services, de la file d'attente, du stockage et de la purge.
Zéro dépendance Streamlit. Lecture seule : aucune commande ne modifie le système
(`systemctl list-units` / `show` ne demandent pas de droits root).
"""
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional

from config.etl_config import STORAGE_ROOT, QUEUE_DIR

STORAGE_DIR = os.path.join(STORAGE_ROOT, "storage_srv")
BROKER_QUEUE_DIR = os.path.join(STORAGE_DIR, "broker_queue")
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PURGE_SCRIPT_SH = os.path.join(_APP_ROOT, "utils", "purge", "purge_archives.sh")
PURGE_SCRIPT_PY = os.path.join(_APP_ROOT, "utils", "purge", "purge_archives.py")
RETENTION_DAYS = 30
_UNIT_PATTERNS = ["SageAgent*", "sageagent*"]


def _run(cmd: List[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def list_services() -> List[Dict]:
    """Services systemd SageAgent : nom, description, état, démarré depuis (UTC), redémarrages auto."""
    units = [l.split()[0] for l in _run(["systemctl", "list-units", "--type=service", "--all",
                                          "--plain", "--no-legend", *_UNIT_PATTERNS]).splitlines() if l.strip()]
    services = []
    for unit in sorted(units):
        props = dict(
            l.split("=", 1) for l in _run([
                "systemctl", "show", unit, "--timestamp=unix",
                "-p", "Description,ActiveState,SubState,ActiveEnterTimestamp,NRestarts,MainPID",
            ]).splitlines() if "=" in l
        )
        ts = props.get("ActiveEnterTimestamp", "").lstrip("@")
        since = datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts.isdigit() else None
        services.append({
            "service": unit.removesuffix(".service"),
            "description": props.get("Description", ""),
            "etat": f"{props.get('ActiveState', '?')} ({props.get('SubState', '?')})",
            "actif": props.get("ActiveState") == "active",
            "depuis": since,
            "redemarrages_auto": int(props.get("NRestarts") or 0),
            "pid": props.get("MainPID"),
        })
    return services


def queue_status() -> Dict[str, int]:
    """Nombre de dossiers en attente dans les deux files de l'ETL."""
    def count(path):
        return len([d for d in os.listdir(path) if not d.startswith(".")]) if os.path.isdir(path) else 0
    return {"queue": count(QUEUE_DIR), "broker_queue": count(BROKER_QUEUE_DIR)}


def disk_usage() -> Dict[str, int]:
    total, used, free = shutil.disk_usage(STORAGE_DIR)
    return {"total": total, "utilise": used, "libre": free}


def storage_folders() -> List[Dict]:
    """Par sous-dossier de storage_srv : taille, nombre de fichiers, plus vieux fichier (UTC)."""
    rows = []
    for name in sorted(os.listdir(STORAGE_DIR)):
        root = os.path.join(STORAGE_DIR, name)
        if not os.path.isdir(root):
            continue
        size, count, oldest = 0, 0, None
        for dirpath, _, files in os.walk(root):
            for f in files:
                try:
                    st = os.stat(os.path.join(dirpath, f))
                except OSError:
                    continue
                size += st.st_size
                count += 1
                oldest = st.st_mtime if oldest is None else min(oldest, st.st_mtime)
        rows.append({
            "dossier": name,
            "taille": size,
            "fichiers": count,
            "plus_ancien": datetime.fromtimestamp(oldest, tz=timezone.utc) if oldest else None,
        })
    return rows


def _purge_targets() -> List[Dict]:
    """Dossier réellement visé par chaque script de purge, tel qu'il le calcule lui-même."""
    targets = []
    if os.path.isfile(PURGE_SCRIPT_SH):
        m = re.search(r'^BASE_DIR="([^"]+)"', open(PURGE_SCRIPT_SH, encoding="utf-8").read(), re.MULTILINE)
        targets.append({"script": PURGE_SCRIPT_SH, "cible": m.group(1) if m else None})
    if os.path.isfile(PURGE_SCRIPT_PY):
        # purge_archives.py : PROJECT_ROOT = dirname(dirname(__file__)) puis "storage_srv"
        targets.append({"script": PURGE_SCRIPT_PY,
                        "cible": os.path.join(os.path.dirname(os.path.dirname(PURGE_SCRIPT_PY)), "storage_srv")})
    for t in targets:
        t["cible_valide"] = bool(t["cible"]) and os.path.normpath(t["cible"]) == os.path.normpath(STORAGE_DIR)
    return targets


def _last_purge_event() -> Optional[datetime]:
    """Date du dernier événement ArchivePurged (écrit par purge_archives.py), None si jamais."""
    try:
        import psycopg2
        from config.db_config import DB_CONFIG
        with psycopg2.connect(**DB_CONFIG) as conn, conn.cursor() as cur:
            cur.execute("SELECT MAX(created_at) FROM etl_events.pipeline_events WHERE event_type = 'ArchivePurged'")
            return cur.fetchone()[0]
    except Exception:
        return None


def purge_status() -> Dict:
    """
    Contrôle de la purge des archives (lecture seule, rien n'est corrigé) :
    dossier visé par chaque script, planification cron, dernière purge enregistrée.
    """
    cron_sources = [_run(["crontab", "-l"])]
    for d in ("/etc/cron.d", "/etc/cron.daily"):
        if os.path.isdir(d):
            for f in os.listdir(d):
                try:
                    cron_sources.append(open(os.path.join(d, f), encoding="utf-8", errors="replace").read())
                except OSError:
                    pass
    planifie = any("purge_archives" in s for s in cron_sources)
    return {
        "scripts": _purge_targets(),
        "chemin_attendu": STORAGE_DIR,
        "planifie": planifie,
        "derniere_purge": _last_purge_event(),
        "retention_jours": RETENTION_DAYS,
    }
