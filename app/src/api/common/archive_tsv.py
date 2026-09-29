"""
api/common/archive_tsv.py

Lecture d'un fichier d'archive Sage (TSV sans en-tête, tout en texte) nommé selon
COLUMNS_ORDER. Partagé par les loaders d'archives (referentiel, stock, transactions).
"""
from __future__ import annotations
from typing import List

import polars as pl

from map_data.reference.columns_order_number import COLONNES_FIN_AJOUTEES


def read_archive_tsv(content: bytes, columns: List[str]) -> pl.DataFrame:
    """
    Nomme les colonnes du fichier dans l'ordre de `columns`.
    Un fichier archivé avant l'ajout d'une colonne de fin (COLONNES_FIN_AJOUTEES,
    ex. F_ARTSTOCK sans as_montsto) est accepté : ces colonnes sont ajoutées à NULL.
    Tout autre écart du nombre de colonnes échoue comme avant (ShapeError).
    """
    df = pl.read_csv(
        content,
        separator="\t",
        has_header=False,
        quote_char=None,
        truncate_ragged_lines=True,
        infer_schema_length=0,
        null_values=["", "NULL"],
        encoding="utf8-lossy",
    )
    manquantes = columns[df.width:]
    if manquantes and not set(manquantes) <= COLONNES_FIN_AJOUTEES:
        raise pl.exceptions.ShapeError(
            f"{len(columns)} column names provided for a DataFrame of width {df.width}"
        )
    df = df.rename(dict(zip(df.columns, columns)))
    if manquantes:
        df = df.with_columns([pl.lit(None, dtype=pl.Utf8).alias(c) for c in manquantes])
    return df
