"""
val_schema_quality.py — Validation avancée de la qualité des données ETL.

Architecture : 4 fonctions indépendantes chaînées en fail-fast.

  _get_pg_schema()        → Récupère le schéma PostgreSQL via information_schema
  _validate_column_count() → Phase 1 : Nombre de colonnes
  _validate_column_types() → Phase 2 : Compatibilité des types (TOUTES les lignes)
  _validate_not_null()     → Phase 3 : Contraintes NOT NULL (TOUTES les lignes)
  validate_schema_quality() → Orchestre les 3 phases en fail-fast

Contraintes :
  - Fichiers SANS headers, délimiteur tabulation (\\t)
  - Mapping POSITIONNEL (par index, pas par nom)
  - Source de vérité : information_schema PostgreSQL
  - Aucune ingestion si une phase échoue
"""

import logging
import polars as pl
import psycopg2
from typing import List, Dict

from config.db_config import DB_CONFIG
from map_data.reference.file_table_map import FILE_TABLE_MAP
from map_data.reference.columns_order_number import COLUMNS_ORDER, COLUMNS_COUNT

from etl.utils.db_safe import db_retry
from etl.utils.sage_cleaner import clean_sage_file

logger = logging.getLogger("etl.validation.schema_quality")

# ---------------------------------------------------------------------------
# Matrice de compatibilité : type PostgreSQL → stratégie de validation Polars
# ---------------------------------------------------------------------------
# Chaque entrée : (dtype_polars_cast, description_lisible)
PG_TYPE_MAP: Dict[str, tuple] = {
    # Entiers
    "integer":          (pl.Int64,   "integer"),
    "smallint":         (pl.Int64,   "smallint"),
    "bigint":           (pl.Int64,   "bigint"),
    "int2":             (pl.Int64,   "int2"),
    "int4":             (pl.Int64,   "int4"),
    "int8":             (pl.Int64,   "int8"),
    # Décimaux
    "numeric":          (pl.Float64, "numeric"),
    "decimal":          (pl.Float64, "decimal"),
    "real":             (pl.Float32, "real"),
    "double precision": (pl.Float64, "double precision"),
    "float4":           (pl.Float32, "float4"),
    "float8":           (pl.Float64, "float8"),
    # Booléens
    "boolean":          (pl.Boolean, "boolean"),
    # Dates / Timestamps
    "date":             (pl.Date,    "date"),
    "timestamp without time zone": (pl.Datetime, "timestamp"),
    "timestamp with time zone":    (pl.Datetime, "timestamp with tz"),
    "timestamp":        (pl.Datetime, "timestamp"),
    # Texte — accepté tel quel, aucun cast nécessaire
    "character varying": None,
    "varchar":           None,
    "character":         None,
    "char":              None,
    "text":              None,
    "name":              None,
    "uuid":              None,
}

BOOLEAN_VALID_VALUES = {"0", "1", "t", "f", "true", "false", "yes", "no", "on", "off", ""}


# ---------------------------------------------------------------------------
# Récupération du schéma PostgreSQL (source de vérité)
# ---------------------------------------------------------------------------

def _get_pg_schema(client_schema: str, table_name: str, run_id: str) -> List[Dict]:
    """
    Interroge information_schema.columns pour récupérer le schéma ordonné
    de la table cible dans le schéma client.
    Retourne une liste ordonnée par ordinal_position :
      [{"column_name": str, "data_type": str, "is_nullable": str}, ...]
    Retourne [] en cas d'erreur (table inexistante ou problème de connexion).
    """

    @db_retry(max_attempts=3, delay=5)
    def _execute():
        pg_schema = client_schema.lower()
        pg_table  = table_name.lower()

        sql = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name   = %s
            ORDER BY ordinal_position ASC
        """
        conn = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute(sql, (pg_schema, pg_table))
            rows = cur.fetchall()

            if not rows:
                logger.error(
                    f"Schéma introuvable dans information_schema pour {table_name}.",
                    extra={
                        "run_id": run_id,
                        "client": client_schema,
                        "table": table_name,
                        "error_code": "SCHEMA_NOT_FOUND",
                        "step": "validation_schema_quality",
                    },
                )
                return []

            return [
                {"column_name": col, "data_type": dtype, "is_nullable": nullable}
                for col, dtype, nullable in rows
            ]

        finally:
            if conn:
                conn.close()

    return _execute()


# ---------------------------------------------------------------------------
# Phase 1 — Validation du NOMBRE DE COLONNES
# ---------------------------------------------------------------------------

def _validate_column_count_all_rows(
    filepath: str,
    pg_columns: List[Dict],
    table_name: str,
    client_schema: str,
    run_id: str,
) -> bool:
    """
    Phase 1 : vérifie que le nombre de colonnes du fichier
    correspond exactement au nombre de colonnes PostgreSQL attendu.

    Stratégie PyArrow :
      - open_csv() ouvre un lecteur en streaming (aucun chargement complet)
      - read_next_batch() lit uniquement le premier batch pour extraire le schéma
      - len(batch.schema) donne le nombre de colonnes sans scanner le reste du fichier
    Séparateur tabulation, sans header (autogenerate_column_names=True).
    """
    expected = COLUMNS_COUNT.get(table_name, len(pg_columns))
    logger.info(
        f"[Phase 1] Vérification du nombre de colonnes pour {table_name}.",
        extra={
            "run_id": run_id,
            "client": client_schema,
            "table": table_name,
            "nb_colonnes_attendues": expected,
            "step": "validation_schema_quality",
        },
    )
    try:
        # Lire le fichier entier comme une seule colonne pour compter les tabulations sans erreur de parsing
        # \x1f est utilisé comme délimiteur fictif pour éviter de séparer les colonnes
        lazy_df = pl.scan_csv(
            filepath,
            separator="\x1f",
            has_header=False,
            quote_char=None,
            encoding="utf8-lossy",
        ).with_row_index("line_number", offset=1)
        
        # Le nombre de colonnes = nombre de tabulations + 1
        lazy_df = lazy_df.with_columns(
            (pl.col("column_1").str.count_matches("\t") + 1).alias("col_count")
        )
        
        # Filtrer toutes les lignes asymétriques
        bad_rows_df = lazy_df.filter(pl.col("col_count") != expected).collect()
        
        if len(bad_rows_df) > 0:
            bad_rows = bad_rows_df.to_dicts()
            # Logger jusqu'à 10 erreurs maximum
            for i, row in enumerate(bad_rows):
                if i >= 10:
                    logger.error(
                        f"[Phase 1] ... et {len(bad_rows) - 10} autres lignes asymétriques masquées.",
                        extra={
                            "run_id": run_id,
                            "client": client_schema,
                            "table": table_name,
                            "step": "validation_schema_quality",
                        }
                    )
                    break
                
                logger.error(
                    f"[Phase 1] ÉCHEC — {table_name} Ligne {row['line_number']} : {expected} colonnes attendues, {row['col_count']} trouvées.",
                    extra={
                        "run_id": run_id,
                        "client": client_schema,
                        "table": table_name,
                        "fichier": filepath.split("/")[-1],
                        "nb_colonnes_attendues": expected,
                        "nb_colonnes_trouvees": row['col_count'],
                        "line_number": row['line_number'],
                        "error_code": "SCHEMA_COLUMN_COUNT_MISMATCH",
                        "step": "validation_schema_quality",
                    },
                )
            return False

        logger.info(
            f"[Phase 1] OK — {table_name} : {expected} colonnes confirmées pour toutes les lignes.",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "step": "validation_schema_quality",
            },
        )
        return True

    except Exception as e:
        logger.error(
            f"[Phase 1] Erreur lecture fichier {filepath} : {e}",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "error_code": "FILE_READ_ERROR",
                "step": "validation_schema_quality",
            },
        )
        return False

# ---------------------------------------------------------------------------
# Phase 2 — Validation des TYPES (toutes les lignes, par position)
# ---------------------------------------------------------------------------

def _validate_column_types(
    filepath: str,
    pg_columns: List[Dict],
    table_name: str,
    client_schema: str,
    run_id: str,
) -> bool:
    """
    Phase 2 : vérifie la compatibilité des types pour TOUTES les lignes du fichier.

    Stratégie Polars LazyFrame :
      - Scan complet en mode String (has_header=False, infer_schema_length=0)
      - Pour chaque colonne dont le type PG nécessite un cast :
          → Cast en LazyFrame → collect() → vérifie les nulls apparus après cast

    Le mapping est POSITIONNEL : colonne 0 = pg_columns[0], etc.
    Retourne False dès la première colonne invalide (fail-fast).
    """
    logger.info(
        f"[Phase 2] Vérification des types pour {table_name} (toutes les lignes).",
        extra={
            "run_id": run_id,
            "client": client_schema,
            "table": table_name,
            "step": "validation_schema_quality",
        },
    )
    try:
        # Scan complet en mode chaîne — pas de conversion automatique
        # quote_char=None : chaque \n est une fin de ligne stricte,
        # évite le crash "CSV malformed" sur les champs Sage contenant des \n internes
        lazy_df = pl.scan_csv(
            filepath,
            separator="\t",
            has_header=False,
            infer_schema_length=0,
            encoding="utf8-lossy",
            truncate_ragged_lines=False, # STRICT MODE
            quote_char=None,
        )
        # Noms de colonnes générés par Polars : column_1, column_2, ...
        col_names = lazy_df.collect_schema().names()

        # --- Lookup PG par nom (source de vérité pour les types) ---
        pg_type_by_name = {col["column_name"].lower(): col for col in pg_columns}

        # --- Ordre des colonnes dans le FICHIER (source : COLUMNS_ORDER) ---
        # Découple l'ordre du fichier Sage de l'ordre ordinal_position PostgreSQL.
        file_col_order = COLUMNS_ORDER.get(table_name)
        if not file_col_order:
            logger.warning(
                f"[Phase 2] Table {table_name} absente de COLUMNS_ORDER — fallback ordre PG.",
                extra={"run_id": run_id, "client": client_schema, "table": table_name, "step": "validation_schema_quality"},
            )
            file_col_order = [col["column_name"].lower() for col in pg_columns]

        for idx, file_col_name in enumerate(file_col_order):
            if idx >= len(col_names):
                break  # Phase 1 aurait déjà bloqué

            col_polars_name = col_names[idx]
            pg_col = pg_type_by_name.get(file_col_name.lower())
            if pg_col is None:
                continue  # colonne du fichier absente du schéma PG → ignorée

            pg_type = pg_col["data_type"].lower()
            col_name_pg = pg_col["column_name"]
            type_mapping = PG_TYPE_MAP.get(pg_type)

            # Pas de validation nécessaire pour les types texte
            if type_mapping is None:
                continue

            target_dtype, type_label = type_mapping

            # --- Cas spécial BOOLEAN : validation par liste de valeurs autorisées ---
            if target_dtype == pl.Boolean:
                invalid_df = (
                    lazy_df
                    .select(
                        pl.col(col_polars_name)
                        .str.strip_chars()
                        .str.to_lowercase()
                        .alias("val")
                    )
                    .filter(
                        ~pl.col("val").is_in(list(BOOLEAN_VALID_VALUES))
                    )
                    .limit(1)
                    .collect(streaming=True)
                )
                if not invalid_df.is_empty():
                    bad_val = invalid_df["val"][0]
                    logger.error(
                        f"[Phase 2] ÉCHEC — {table_name} col {idx + 1} ({col_name_pg}) : "
                        f"type attendu={type_label}, valeur invalide='{bad_val}'",
                        extra={
                            "run_id": run_id,
                            "client": client_schema,
                            "table": table_name,
                            "fichier": filepath.split("/")[-1],
                            "col_position": idx + 1,
                            "col_name_postgres": col_name_pg,
                            "type_attendu": type_label,
                            "valeur_exemple": str(bad_val),
                            "error_code": f"TYPE_MISMATCH_COL_{idx + 1}",
                            "step": "validation_schema_quality",
                        },
                    )
                    return False
                continue

            # --- Cas général : cast Polars, les valeurs non-convertibles → null ---
            # On filtre les vides ET les NULL littéraux avant cast.
            # Les valeurs vides ("") ou "NULL" / "null" dans le fichier Sage
            # sont des absences de valeur légitimes au niveau du type ;
            # seule la Phase 3 (NOT NULL) les interceptera si la colonne est obligatoire.
            expr_raw = pl.col(col_polars_name).str.strip_chars()

            # Pour les dates/timestamps (ex: 2022-06-06 00:00:00.000), le cast() natif de Polars
            # échoue souvent car il attend un 'T'. On valide simplement la partie YYYY-MM-DD.
            if target_dtype in (pl.Date, pl.Datetime):
                expr_cast = expr_raw.str.slice(0, 10).cast(pl.Date, strict=False)
            else:
                expr_cast = expr_raw.cast(target_dtype, strict=False)

            casted = (
                lazy_df
                .select(
                    expr_raw.alias("raw"),
                    expr_cast.alias("casted"),
                )
                .filter(
                    pl.col("raw").is_not_null()
                    & pl.col("raw").str.len_chars().gt(0)
                    & pl.col("raw").str.to_uppercase().ne("NULL")  # NULL littéral → absence légale
                    & pl.col("casted").is_null()
                )
                .limit(1)
                .collect(streaming=True)
            )

            if not casted.is_empty():
                bad_val = casted["raw"][0]
                logger.error(
                    f"[Phase 2] ÉCHEC — {table_name} col {idx + 1} ({col_name_pg}) : "
                    f"type attendu={type_label}, valeur invalide='{bad_val}'",
                    extra={
                        "run_id": run_id,
                        "client": client_schema,
                        "table": table_name,
                        "fichier": filepath.split("/")[-1],
                        "col_position": idx + 1,
                        "col_name_postgres": col_name_pg,
                        "type_attendu": type_label,
                        "valeur_exemple": str(bad_val),
                        "error_code": f"TYPE_MISMATCH_COL_{idx + 1}",
                        "step": "validation_schema_quality",
                    },
                )
                return False

        logger.info(
            f"[Phase 2] OK — {table_name} : tous les types conformes.",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "step": "validation_schema_quality",
            },
        )
        return True

    except Exception as e:
        logger.error(
            f"[Phase 2] Erreur lors de la validation des types pour {table_name} : {e}",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "error_code": "TYPE_VALIDATION_ERROR",
                "step": "validation_schema_quality",
            },
        )
        return False


# ---------------------------------------------------------------------------
# Phase 3 — Validation des contraintes NOT NULL (toutes les lignes)
# ---------------------------------------------------------------------------

def _validate_not_null(
    filepath: str,
    pg_columns: List[Dict],
    table_name: str,
    client_schema: str,
    run_id: str,
) -> bool:
    """
    Phase 3 : vérifie les contraintes NOT NULL pour TOUTES les lignes du fichier.

    Une valeur est considérée invalide si :
      - Elle est null (None)
      - Elle est une chaîne vide après strip ('' ou '  ')

    Mapping POSITIONNEL. Retourne False dès la première colonne invalide.
    """
    logger.info(
        f"[Phase 3] Vérification des contraintes NOT NULL pour {table_name} (toutes les lignes).",
        extra={
            "run_id": run_id,
            "client": client_schema,
            "table": table_name,
            "step": "validation_schema_quality",
        },
    )
    # --- Lookup PG par nom + ordre fichier (COLUMNS_ORDER) ---
    pg_type_by_name = {col["column_name"].lower(): col for col in pg_columns}
    file_col_order = COLUMNS_ORDER.get(table_name)
    if not file_col_order:
        file_col_order = [col["column_name"].lower() for col in pg_columns]

    # Identifier les colonnes NOT NULL selon l'ordre RÉEL du fichier
    not_null_cols = [
        (idx, pg_type_by_name[file_col_name.lower()])
        for idx, file_col_name in enumerate(file_col_order)
        if file_col_name.lower() in pg_type_by_name
        and pg_type_by_name[file_col_name.lower()]["is_nullable"].upper() == "NO"
    ]

    if not not_null_cols:
        logger.info(
            f"[Phase 3] OK — {table_name} : aucune colonne NOT NULL à vérifier.",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "step": "validation_schema_quality",
            },
        )
        return True

    try:
        lazy_df = pl.scan_csv(
            filepath,
            separator="\t",
            has_header=False,
            infer_schema_length=0,
            encoding="utf8-lossy",
            truncate_ragged_lines=False,    # STRICT MODE
            quote_char=None,        # évite le crash sur les \n embarqués
        )
        col_names = lazy_df.collect_schema().names()

        for idx, pg_col in not_null_cols:
            if idx >= len(col_names):
                break

            col_polars_name = col_names[idx]
            col_name_pg = pg_col["column_name"]

            # Recherche d'une valeur null ou vide dans TOUTE la colonne
            # "NULL" littéral Sage étant une représentation de l'absence de valeur,
            # il est aussi considéré comme une violation NOT NULL.
            violations = (
                lazy_df
                .select(
                    pl.col(col_polars_name)
                    .str.strip_chars()
                    .alias("val")
                )
                .filter(
                    pl.col("val").is_null()
                    | pl.col("val").str.len_chars().eq(0)
                    | pl.col("val").str.to_uppercase().eq("NULL")  # NULL littéral Sage = absent
                )
                .limit(1)
                .collect(streaming=True)
            )

            if not violations.is_empty():
                logger.error(
                    f"[Phase 3] ÉCHEC — {table_name} col {idx + 1} ({col_name_pg}) : "
                    f"violation NOT NULL détectée (valeur vide ou null).",
                    extra={
                        "run_id": run_id,
                        "client": client_schema,
                        "table": table_name,
                        "fichier": filepath.split("/")[-1],
                        "col_position": idx + 1,
                        "col_name_postgres": col_name_pg,
                        "type_attendu": pg_col["data_type"],
                        "valeur_exemple": "NULL / vide",
                        "error_code": f"NOT_NULL_VIOLATION_COL_{idx + 1}",
                        "step": "validation_schema_quality",
                    },
                )
                return False

        logger.info(
            f"[Phase 3] OK — {table_name} : toutes les contraintes NOT NULL respectées.",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "step": "validation_schema_quality",
            },
        )
        return True

    except Exception as e:
        logger.error(
            f"[Phase 3] Erreur lors de la validation NOT NULL pour {table_name} : {e}",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "error_code": "NOT_NULL_VALIDATION_ERROR",
                "step": "validation_schema_quality",
            },
        )
        return False


# ---------------------------------------------------------------------------
# Orchestrateur principal — fail-fast inter-fichiers
# ---------------------------------------------------------------------------

def validate_schema_quality(
    folder_path: str,
    client_schema: str,
    run_id: str,
) -> bool:
    """
    Point d'entrée principal.
    Pour chaque fichier connu (FILE_TABLE_MAP) présent dans folder_path :
      (Ignore les fichiers cachés commençant par '.')
      1. Récupère le schéma PostgreSQL
      2. Phase 1 — Nombre de colonnes
      3. Phase 2 — Types (toutes les lignes)
      4. Phase 3 — NOT NULL (toutes les lignes)

    Retourne False dès qu'une phase échoue sur n'importe quel fichier.
    Retourne True uniquement si tous les fichiers passent les 3 phases.
    """
    import os

    logger.info(
        "Démarrage de la validation qualité des données (schema_quality).",
        extra={
            "run_id": run_id,
            "client": client_schema,
            "step": "validation_schema_quality",
        },
    )

    files_in_folder_upper = {
        f.upper(): f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f)) and not f.startswith('.')
    }
    
    files_to_validate = {}
    for expected_filename, table in FILE_TABLE_MAP.items():
        expected_upper = expected_filename.upper()
        if expected_upper in files_in_folder_upper:
            real_filename = files_in_folder_upper[expected_upper]
            files_to_validate[real_filename] = table

    if not files_to_validate:
        logger.warning(
            "Aucun fichier connu à valider dans le dossier.",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "step": "validation_schema_quality",
            },
        )
        return True

    for filename, table_name in files_to_validate.items():
        filepath = os.path.join(folder_path, filename)
        logger.info(
            f"Validation de : {filename} → table {table_name}",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "fichier": filename,
                "step": "validation_schema_quality",
            },
        )

        # --- NETTOYAGE AUTO ---
        # Si le fichier contient des tabulations accidentelles, on les fusionne 
        # AVANT la validation de la Phase 1 pour ne pas bloquer faussement l'ETL.
        clean_sage_file(filepath, table_name, run_id, client_schema)

        # --- Récupération du schéma PG ---
        pg_columns = _get_pg_schema(client_schema, table_name, run_id)
        if not pg_columns:
            return False  # Déjà loggué dans _get_pg_schema

        # --- Phase 1 : Nombre de colonnes ---
        if not _validate_column_count_all_rows(filepath, pg_columns, table_name, client_schema, run_id):
            return False

        # --- Phase 2 : Types ---
        if not _validate_column_types(filepath, pg_columns, table_name, client_schema, run_id):
            return False

        # --- Phase 3 : NOT NULL ---
        if not _validate_not_null(filepath, pg_columns, table_name, client_schema, run_id):
            return False

    logger.info(
        "Validation qualité des données réussie — tous les fichiers conformes.",
        extra={
            "run_id": run_id,
            "client": client_schema,
            "nb_fichiers_valides": len(files_to_validate),
            "step": "validation_schema_quality",
        },
    )
    return True
