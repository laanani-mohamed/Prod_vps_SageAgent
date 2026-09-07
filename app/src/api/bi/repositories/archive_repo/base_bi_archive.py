"""
api/bi/repositories/archive_repo/base_bi_archive.py

Couche d'accès aux archives pour le module BI.
Encapsule les helpers partagés : chargement de fichier, résolution de snapshot,
et cast sécurisé de colonnes Polars.

Réutilise le loader du module référentiel (même format d'archive).
"""
from __future__ import annotations
import logging
from typing import Optional

import polars as pl

from api.referentiel.repositories.archive_repo._loader import (
    get_archive_dir,
    find_closest_snapshot,
    load_archive_file,
    resolve_target_dt,
)

logger = logging.getLogger("api.bi.repositories.archive")


# ---------------------------------------------------------------------------
# Helpers publics réexportés (pour que les use_cases n'importent que ce module)
# ---------------------------------------------------------------------------

def get_bi_archive_dir(client_schema: str) -> str:
    """Retourne le répertoire d'archives pour un schéma client donné."""
    return get_archive_dir(client_schema)


def find_bi_snapshot(archive_dir: str, table: str, target_dt=None) -> Optional[str]:
    """Retourne le timestamp du snapshot le plus proche pour une table BI."""
    return find_closest_snapshot(archive_dir, table, target_dt)


def resolve_bi_target_dt(req):
    """Extrait le datetime cible depuis un objet de requête BI."""
    return resolve_target_dt(req)


def load_bi_table(archive_dir: str, table: str, ts: str) -> Optional[pl.DataFrame]:
    """
    Charge une table archive et retourne un DataFrame Polars.
    Retourne None et loggue un warning si la table est absente.
    """
    df = load_archive_file(archive_dir, table, ts)
    if df is None:
        logger.warning("[BI] Table absente dans les archives : %s_%s", table, ts)
    return df


def safe_float_col(df: pl.DataFrame, col: str) -> pl.Series:
    """
    Cast une colonne vers Float64 en mode silencieux (strict=False).
    Retourne une série de zéros si la colonne est absente ou incompatible.
    """
    try:
        return df[col].cast(pl.Float64, strict=False).fill_null(0.0)
    except Exception:
        return pl.Series([0.0] * len(df))
