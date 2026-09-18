"""
investigate_error.py — Investigation à la demande d'un fichier client archivé en erreur.

Zéro dépendance à Streamlit : réutilisable en CLI/tests. Ne touche jamais aux
fonctions de production fail-fast de val_schema_quality.py — ce sont des copies
volontairement séparées, en mode "collecte tout", pour ne jamais risquer de
ralentir ou casser le chemin critique d'ingestion.
"""

import os
import re
import logging
from collections import OrderedDict
from typing import Dict, List, Optional

import polars as pl

from config.etl_config import ERROR_BASE_PATH
from map_data.reference.file_table_map import FILE_TABLE_MAP
from map_data.reference.columns_order_number import COLUMNS_ORDER, COLUMNS_COUNT
from etl.validation.val_schema_quality import PG_TYPE_MAP, BOOLEAN_VALID_VALUES, _get_pg_schema

logger = logging.getLogger("etl.reporting.investigate_error")

_ARCHIVE_SUFFIX_RE = re.compile(r"_\d{8}_\d{6}(\.\w+)?$")
_ARCHIVE_TIMESTAMP_RE = re.compile(r"_(\d{8})_(\d{6})(?:\.\w+)?$")

MAX_BAD_ROWS_DISPLAY = 50
MAX_CLEAN_ROWS_DISPLAY = 3


def resolve_table_from_filename(filename: str) -> Optional[str]:
    """
    'F_DOCLIGNE_20260918_113040.txt' -> 'F_DOCLIGNE'
    Tolère la casse et l'absence de suffixe horodaté (nom de fichier brut déposé
    par le client, ex: 'F_DOCLIGNE.txt').
    """
    base = _ARCHIVE_SUFFIX_RE.sub("", filename)
    base_upper = base.upper()
    if not base_upper.endswith(".TXT"):
        base_upper_no_ext = base_upper
    else:
        base_upper_no_ext = base_upper[:-4]

    for known_filename, table_name in FILE_TABLE_MAP.items():
        if known_filename.upper().rsplit(".", 1)[0] == base_upper_no_ext:
            return table_name
    # Fallback : comparer directement aux noms de table connus (ex: fichier "ARTICLE.txt")
    for table_name in FILE_TABLE_MAP.values():
        if table_name.upper() == base_upper_no_ext:
            return table_name
    return None


def find_archived_file(client: str, date_str: str, fichier: str, around_time: Optional[str] = None) -> Optional[str]:
    """
    Cherche le fichier archivé correspondant à `fichier` (nom original, ex: 'F_DOCLIGNE.txt')
    dans storage_srv/error/<client>/<date_str>/. Si plusieurs candidats existent pour la même
    journée (plusieurs runs), choisit celui dont l'horodatage est le plus proche de `around_time`
    (format 'HH:MM:SS', tel que loggé).
    Retourne None si le dossier ou aucun candidat n'existe (ex: run cassé avant l'archivage).
    """
    table_name = resolve_table_from_filename(fichier)
    if not table_name:
        return None

    day_dir = os.path.join(ERROR_BASE_PATH, client, date_str)
    if not os.path.isdir(day_dir):
        return None

    candidates = []
    for name in os.listdir(day_dir):
        base = _ARCHIVE_SUFFIX_RE.sub("", name).upper()
        if base.rsplit(".", 1)[0] != table_name.upper():
            continue
        full_path = os.path.join(day_dir, name)
        if not os.path.isfile(full_path):
            continue
        candidates.append((name, full_path))

    if not candidates:
        return None
    if len(candidates) == 1 or not around_time:
        return candidates[0][1]

    try:
        target_seconds = _hhmmss_to_seconds(around_time)
    except ValueError:
        return candidates[0][1]

    def _distance(item):
        name, _ = item
        m = _ARCHIVE_TIMESTAMP_RE.search(name)
        if not m:
            return float("inf")
        hhmmss = m.group(2)
        try:
            return abs(_hhmmss_to_seconds(f"{hhmmss[0:2]}:{hhmmss[2:4]}:{hhmmss[4:6]}") - target_seconds)
        except ValueError:
            return float("inf")

    candidates.sort(key=_distance)
    return candidates[0][1]


def _hhmmss_to_seconds(hhmmss: str) -> int:
    h, m, s = hhmmss.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def _read_lines_by_number(filepath: str, line_numbers: set) -> Dict[int, str]:
    """Lit uniquement les lignes demandées (1-indexées), en un seul passage du fichier."""
    result = {}
    if not line_numbers:
        return result
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        for idx, line in enumerate(f, start=1):
            if idx in line_numbers:
                result[idx] = line.rstrip("\n").rstrip("\r")
                if len(result) == len(line_numbers):
                    break
    return result


def _split_row_fields(raw_line: str, table_name: str) -> "OrderedDict[str, str]":
    """
    Découpe une ligne brute (séparateur \\t) en un dict {nom_de_colonne: valeur},
    dans l'ordre réel du fichier (COLUMNS_ORDER), pour un affichage tabulaire
    (une colonne du tableau = une colonne du fichier Sage), plutôt qu'un seul
    bloc de texte brut. Les champs en trop (ligne plus longue que prévu) sont
    nommés "colonne_extra_N" ; les champs manquants sont laissés vides.
    """
    parts = raw_line.split("\t") if raw_line else []
    col_names = COLUMNS_ORDER.get(table_name, [])
    fields: "OrderedDict[str, str]" = OrderedDict()
    for i in range(max(len(parts), len(col_names))):
        name = col_names[i] if i < len(col_names) else f"colonne_extra_{i + 1}"
        fields[name] = parts[i] if i < len(parts) else ""
    return fields


def investigate_column_count(filepath: str, table_name: str) -> dict:
    """
    Compare le nombre de colonnes de chaque ligne au nombre attendu (COLUMNS_COUNT).
    Retourne toutes les lignes fautives (contrairement à Phase 1 en production qui
    ne logue que les 10 premières), plafonnées à MAX_BAD_ROWS_DISPLAY pour l'affichage.
    """
    expected = COLUMNS_COUNT.get(table_name)
    if expected is None:
        return {"error": f"Table '{table_name}' absente de COLUMNS_COUNT."}

    bad_line_counts: Dict[int, int] = {}
    clean_line_numbers = []

    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        for idx, line in enumerate(f, start=1):
            stripped = line.rstrip("\n").rstrip("\r")
            if not stripped:
                continue
            col_count = stripped.count("\t") + 1
            if col_count != expected:
                bad_line_counts[idx] = col_count
            elif len(clean_line_numbers) < MAX_CLEAN_ROWS_DISPLAY:
                clean_line_numbers.append(idx)

    total_bad = len(bad_line_counts)
    display_bad = list(bad_line_counts.keys())[:MAX_BAD_ROWS_DISPLAY]
    raw_lines = _read_lines_by_number(filepath, set(display_bad) | set(clean_line_numbers))

    return {
        "expected": expected,
        "total_bad_rows": total_bad,
        "bad_rows": [
            {
                "line_number": n,
                "colonnes_trouvees": bad_line_counts[n],
                **_split_row_fields(raw_lines.get(n, ""), table_name),
            }
            for n in display_bad
        ],
        "clean_sample": [
            {"line_number": n, **_split_row_fields(raw_lines.get(n, ""), table_name)}
            for n in clean_line_numbers
        ],
    }


def _resolve_pg_column(pg_columns: List[Dict], table_name: str, col_position: int):
    file_col_order = COLUMNS_ORDER.get(table_name)
    if not file_col_order or col_position < 1 or col_position > len(file_col_order):
        return None, None
    file_col_name = file_col_order[col_position - 1]
    pg_type_by_name = {col["column_name"].lower(): col for col in pg_columns}
    pg_col = pg_type_by_name.get(file_col_name.lower())
    return file_col_name, pg_col


def _build_cast_expr(col_polars_name: str, target_dtype) -> pl.Expr:
    """Mêmes règles de tolérance que _validate_column_types (val_schema_quality.py)."""
    expr_raw = pl.col(col_polars_name).str.strip_chars()
    if target_dtype in (pl.Date, pl.Datetime):
        return pl.coalesce(
            expr_raw.str.slice(0, 10).cast(pl.Date, strict=False),
            expr_raw.str.to_date("%d/%m/%Y", strict=False),
        )
    elif target_dtype in (pl.Float32, pl.Float64):
        return expr_raw.str.replace(",", ".", literal=True).cast(target_dtype, strict=False)
    elif target_dtype == pl.Int64:
        return pl.coalesce(
            expr_raw.cast(pl.Int64, strict=False),
            expr_raw.cast(pl.Float64, strict=False).cast(pl.Int64, strict=False),
        )
    return expr_raw.cast(target_dtype, strict=False)


def investigate_column_types(filepath: str, pg_columns: List[Dict], table_name: str, col_position: int) -> dict:
    """
    Recast la SEULE colonne en cause (identifiée via les logs) sur TOUTES les lignes
    (contrairement à Phase 2 en production qui s'arrête à la première ligne fautive),
    et retourne un échantillon de lignes fautives + de lignes propres.
    """
    file_col_name, pg_col = _resolve_pg_column(pg_columns, table_name, col_position)
    if pg_col is None:
        return {"error": f"Colonne en position {col_position} introuvable pour {table_name}."}

    pg_type = pg_col["data_type"].lower()
    col_name_pg = pg_col["column_name"]
    type_mapping = PG_TYPE_MAP.get(pg_type)
    if type_mapping is None:
        return {"error": f"Colonne texte ({pg_type}) — pas de mismatch de type possible."}

    target_dtype, type_label = type_mapping

    try:
        lazy_df = pl.scan_csv(
            filepath, separator="\t", has_header=False, infer_schema_length=0,
            encoding="utf8-lossy", truncate_ragged_lines=False, quote_char=None,
        ).with_row_index("line_number", offset=1)
        col_names = [c for c in lazy_df.collect_schema().names() if c != "line_number"]
        if col_position - 1 >= len(col_names):
            return {"error": "Position de colonne hors limites pour ce fichier."}
        col_polars_name = col_names[col_position - 1]

        if target_dtype == pl.Boolean:
            base = lazy_df.select(
                pl.col("line_number"),
                pl.col(col_polars_name).str.strip_chars().str.to_lowercase().alias("val"),
            )
            bad_df = base.filter(~pl.col("val").is_in(list(BOOLEAN_VALID_VALUES))).collect(streaming=True)
            good_df = base.filter(pl.col("val").is_in(list(BOOLEAN_VALID_VALUES)) & pl.col("val").str.len_chars().gt(0)).limit(MAX_CLEAN_ROWS_DISPLAY).collect(streaming=True)
        else:
            expr_raw = pl.col(col_polars_name).str.strip_chars()
            expr_cast = _build_cast_expr(col_polars_name, target_dtype)
            base = lazy_df.select(
                pl.col("line_number"),
                expr_raw.alias("raw"),
                expr_cast.alias("casted"),
            )
            invalid_mask = (
                pl.col("raw").is_not_null()
                & pl.col("raw").str.len_chars().gt(0)
                & pl.col("raw").str.to_uppercase().ne("NULL")
                & pl.col("casted").is_null()
            )
            bad_df = base.filter(invalid_mask).collect(streaming=True)
            good_df = base.filter(~invalid_mask & pl.col("raw").str.len_chars().gt(0)).limit(MAX_CLEAN_ROWS_DISPLAY).collect(streaming=True)

    except Exception as e:
        logger.warning(f"Erreur investigation type pour {filepath} col {col_position} : {e}")
        return {"error": f"Erreur lors de l'analyse : {e}"}

    total_bad = bad_df.height
    bad_line_numbers = bad_df["line_number"].to_list()[:MAX_BAD_ROWS_DISPLAY]
    clean_line_numbers = good_df["line_number"].to_list()

    raw_lines = _read_lines_by_number(filepath, set(bad_line_numbers) | set(clean_line_numbers))

    return {
        "colonne": col_name_pg,
        "col_position": col_position,
        "type_attendu": type_label,
        "total_bad_rows": total_bad,
        "bad_rows": [
            {"line_number": n, **_split_row_fields(raw_lines.get(n, ""), table_name)}
            for n in bad_line_numbers
        ],
        "clean_sample": [
            {"line_number": n, **_split_row_fields(raw_lines.get(n, ""), table_name)}
            for n in clean_line_numbers
        ],
    }


def investigate_not_null(filepath: str, pg_columns: List[Dict], table_name: str, col_position: int) -> dict:
    """Même principe que investigate_column_types mais pour une contrainte NOT NULL."""
    file_col_name, pg_col = _resolve_pg_column(pg_columns, table_name, col_position)
    if pg_col is None:
        return {"error": f"Colonne en position {col_position} introuvable pour {table_name}."}

    col_name_pg = pg_col["column_name"]

    try:
        lazy_df = pl.scan_csv(
            filepath, separator="\t", has_header=False, infer_schema_length=0,
            encoding="utf8-lossy", truncate_ragged_lines=False, quote_char=None,
        ).with_row_index("line_number", offset=1)
        col_names = [c for c in lazy_df.collect_schema().names() if c != "line_number"]
        if col_position - 1 >= len(col_names):
            return {"error": "Position de colonne hors limites pour ce fichier."}
        col_polars_name = col_names[col_position - 1]

        base = lazy_df.select(
            pl.col("line_number"),
            pl.col(col_polars_name).str.strip_chars().alias("val"),
        )
        empty_mask = (
            pl.col("val").is_null()
            | pl.col("val").str.len_chars().eq(0)
            | pl.col("val").str.to_uppercase().eq("NULL")
        )
        bad_df = base.filter(empty_mask).collect(streaming=True)
        good_df = base.filter(~empty_mask).limit(MAX_CLEAN_ROWS_DISPLAY).collect(streaming=True)

    except Exception as e:
        logger.warning(f"Erreur investigation NOT NULL pour {filepath} col {col_position} : {e}")
        return {"error": f"Erreur lors de l'analyse : {e}"}

    total_bad = bad_df.height
    bad_line_numbers = bad_df["line_number"].to_list()[:MAX_BAD_ROWS_DISPLAY]
    clean_line_numbers = good_df["line_number"].to_list()
    raw_lines = _read_lines_by_number(filepath, set(bad_line_numbers) | set(clean_line_numbers))

    return {
        "colonne": col_name_pg,
        "col_position": col_position,
        "total_bad_rows": total_bad,
        "bad_rows": [
            {"line_number": n, **_split_row_fields(raw_lines.get(n, ""), table_name)}
            for n in bad_line_numbers
        ],
        "clean_sample": [
            {"line_number": n, **_split_row_fields(raw_lines.get(n, ""), table_name)}
            for n in clean_line_numbers
        ],
    }


def build_investigation_report(client: str, date_str: str, run_summary: dict) -> dict:
    """
    Point d'entrée unique pour la page Streamlit. `run_summary` doit contenir au
    minimum : error_code, fichier, table, et selon le cas col_position. Ne lève
    jamais d'exception — toute erreur interne devient un champ "error" affiché
    tel quel côté UI.
    """
    error_code = run_summary.get("error_code")
    fichier = run_summary.get("fichier") or run_summary.get("table")
    table_name = run_summary.get("table") or (resolve_table_from_filename(fichier) if fichier else None)

    if not fichier or not table_name:
        return {"error": "Fichier ou table concerné non identifiable depuis les logs de ce run."}

    filepath = find_archived_file(client, date_str, fichier, run_summary.get("started_at"))
    if not filepath:
        return {
            "error": (
                f"Fichier archivé introuvable pour {fichier} ({client}, {date_str}). "
                "Le run a peut-être échoué avant l'archivage (ex: FILE_READ_ERROR)."
            )
        }

    report = {
        "client": client,
        "date": date_str,
        "table": table_name,
        "fichier": fichier,
        "filepath": filepath,
        "error_code": error_code,
    }

    if error_code == "SCHEMA_COLUMN_COUNT_MISMATCH":
        report["details"] = investigate_column_count(filepath, table_name)
        return report

    if error_code and (error_code.startswith("TYPE_MISMATCH_COL_") or error_code.startswith("NOT_NULL_VIOLATION_COL_")):
        col_position = run_summary.get("col_position")
        if not col_position:
            report["error"] = "Position de colonne manquante dans les logs pour cette erreur."
            return report

        pg_columns = _get_pg_schema(client, table_name, run_summary.get("run_id", ""))
        if not pg_columns:
            report["error"] = f"Schéma PostgreSQL introuvable pour {client}.{table_name}."
            return report

        if error_code.startswith("TYPE_MISMATCH_COL_"):
            report["details"] = investigate_column_types(filepath, pg_columns, table_name, int(col_position))
        else:
            report["details"] = investigate_not_null(filepath, pg_columns, table_name, int(col_position))
        return report

    report["error"] = f"Catégorie d'erreur '{error_code}' non prise en charge par l'investigation automatique."
    return report
