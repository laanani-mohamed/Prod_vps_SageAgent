"""
bi/referentiel/repositories/archive_repo/_loader.py

Helpers partagés pour le chargement des fichiers d'archives CSV (format Sage ERP).

Responsabilités :
  - _load_archive_file()     : charger un fichier {TABLE}_{timestamp}.txt en pl.DataFrame
  - _find_closest_snapshot() : trouver le snapshot le plus proche d'une datetime cible
  - _resolve_target_dt()     : extraire la datetime cible depuis un schéma de requête

Toutes les fonctions sont stateless et réutilisables par tous les archive repos.
"""
from __future__ import annotations
import os
import glob
import logging
import datetime
from typing import Optional

import polars as pl

from config.etl_config import ARCHIVE_BASE_PATH
from map_data.reference.columns_order_number import COLUMNS_ORDER

logger = logging.getLogger("api.referentiel.repositories.archive")


def get_archive_dir(client_schema: str) -> str:
    """Retourne le chemin du répertoire d'archives pour un client."""
    archive_dir = os.path.join(ARCHIVE_BASE_PATH, client_schema)
    if not os.path.isdir(archive_dir):
        raise FileNotFoundError(
            f"Pas d'archives trouvées pour le schema '{client_schema}'. "
            f"Répertoire attendu : {archive_dir}"
        )
    return archive_dir


def resolve_target_dt(req) -> Optional[datetime.datetime]:
    """Extrait la datetime cible depuis un schéma BaseReferentielRequest."""
    snap = getattr(req, "snapshot_datetime", None)
    if snap:
        return datetime.datetime.fromisoformat(snap)
    return None


def find_closest_snapshot(
    archive_dir: str,
    table: str,
    target_dt: Optional[datetime.datetime],
) -> Optional[str]:
    """
    Trouve le timestamp du snapshot le plus proche de target_dt.

    Règles de priorité :
      1. Même minute → le plus proche en secondes
      2. Avant target_dt → le plus récent avant
      3. Après target_dt → le plus ancien disponible
      4. target_dt=None → le snapshot le plus récent

    Returns:
        str : timestamp au format "YYYYMMDD_HHMMSS", ou None si aucun fichier
    """
    pattern = os.path.join(archive_dir, f"{table}_*.txt")
    files = glob.glob(pattern)
    if not files:
        logger.warning(f"[Archive] Aucun fichier {table}_*.txt trouvé dans {archive_dir}")
        return None

    dated = []
    for f in files:
        try:
            ts = os.path.basename(f).replace(f"{table}_", "").replace(".txt", "")
            dated.append((ts, datetime.datetime.strptime(ts, "%Y%m%d_%H%M%S")))
        except Exception:
            continue

    if not dated:
        return None

    # Pas de cible → snapshot le plus récent
    if not target_dt:
        return max(dated, key=lambda x: x[1])[0]

    # Même minute
    same_min = [
        d for d in dated
        if d[1].replace(second=0, microsecond=0) == target_dt.replace(second=0, microsecond=0)
    ]
    if same_min:
        return min(same_min, key=lambda x: abs((x[1] - target_dt).total_seconds()))[0]

    # Avant cible
    before = [d for d in dated if d[1] <= target_dt]
    if before:
        return max(before, key=lambda x: x[1])[0]

    # Après cible (le plus proche disponible)
    return min(dated, key=lambda x: x[1])[0]


def load_archive_file(
    archive_dir: str,
    table: str,
    timestamp: str,
) -> Optional[pl.DataFrame]:
    """
    Charge un fichier d'archive au format TSV sans en-tête.

    Args:
        archive_dir : Chemin du répertoire d'archives du client
        table       : Nom de la table (ex: "F_COMPTET", "F_DOCLIGNE")
        timestamp   : Timestamp du snapshot (ex: "20260115_080000")

    Returns:
        pl.DataFrame ou None si le fichier n'existe pas ou est illisible
    """
    filepath = os.path.join(archive_dir, f"{table}_{timestamp}.txt")

    if not os.path.exists(filepath):
        logger.debug(f"[Archive] Fichier absent : {filepath}")
        return None

    columns = COLUMNS_ORDER.get(table.upper())

    try:
        with open(filepath, "rb") as f:
            content = f.read()
            # Supprimer le BOM UTF-8 si présent
            if content.startswith(b"\xef\xbb\xbf"):
                content = content[3:]

        return pl.read_csv(
            content,
            separator="\t",
            has_header=False,
            new_columns=columns,
            quote_char=None,
            truncate_ragged_lines=True,
            infer_schema_length=0,
            null_values=["", "NULL"],
            encoding="utf8-lossy",
        )
    except Exception as e:
        logger.warning(f"[Archive] Impossible de charger {table}_{timestamp}.txt : {e}")
        return None


def require_snapshot(archive_dir: str, table: str, req) -> tuple[pl.DataFrame, str]:
    """
    Trouve le snapshot le plus proche et charge le fichier correspondant.
    Lève FileNotFoundError si aucun snapshot n'est disponible.

    Returns:
        (DataFrame, timestamp_str)
    """
    target_dt = resolve_target_dt(req)
    timestamp = find_closest_snapshot(archive_dir, table, target_dt)
    if not timestamp:
        raise FileNotFoundError(
            f"Aucun snapshot pour la table '{table}' dans {archive_dir}"
        )
    df = load_archive_file(archive_dir, table, timestamp)
    if df is None:
        raise FileNotFoundError(
            f"Fichier {table}_{timestamp}.txt illisible ou vide"
        )
    return df, timestamp
