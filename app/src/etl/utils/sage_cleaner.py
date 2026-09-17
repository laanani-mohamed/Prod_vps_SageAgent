import os
import re
import logging
from map_data.reference.columns_order_number import COLUMNS_COUNT, COLUMNS_ORDER

logger = logging.getLogger("etl.sage_cleaner")

# Un champ purement numérique au format français : "10592,23" ou "-42,5"
_FRENCH_DECIMAL_RE = re.compile(r"^-?\d+,\d+$")
# Une date au format JJ/MM/AAAA : "04/01/2021"
_FR_DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
# Une valeur décimale déjà normalisée avec un point : "204.1"
_DECIMAL_DOT_RE = re.compile(r"^-?\d+\.\d+$")

INTEGER_PG_TYPES = {"integer", "smallint", "bigint", "int2", "int4", "int8"}


def _integer_column_indices(table_name: str, pg_columns) -> set[int]:
    """
    Détermine, par position dans le fichier (COLUMNS_ORDER), les index des colonnes
    dont le type PostgreSQL est entier. Utilisé pour tronquer les valeurs décimales
    (ex: co_no = '204.1') qui feraient échouer un COPY vers une colonne bigint/integer.
    """
    if not pg_columns:
        return set()

    file_col_order = COLUMNS_ORDER.get(table_name)
    if not file_col_order:
        return set()

    pg_type_by_name = {col["column_name"].lower(): col["data_type"].lower() for col in pg_columns}

    return {
        idx
        for idx, col_name in enumerate(file_col_order)
        if pg_type_by_name.get(col_name) in INTEGER_PG_TYPES
    }


def _normalize_locale_fields(line: str, integer_col_indices: set[int] = frozenset()) -> tuple[str, bool]:
    """
    Normalise, champ par champ, les valeurs numériques françaises ('10592,23' → '10592.23')
    et les dates JJ/MM/AAAA ('04/01/2021' → '2021-01-04') afin que le COPY PostgreSQL
    (qui attend le point décimal et le format ISO) accepte des fichiers Sage produits
    avec des paramètres régionaux français.
    Tronque aussi vers l'entier les valeurs décimales tombant dans une colonne PG de
    type entier (ex: co_no = '204,1' ou '204.1' → '204').
    Ne touche qu'aux champs correspondant strictement à ces motifs, pour ne jamais
    altérer un champ texte.
    """
    cols = line.rstrip('\r\n').split('\t')
    changed = False

    for i, val in enumerate(cols):
        if _FRENCH_DECIMAL_RE.match(val):
            val = val.replace(",", ".")
            cols[i] = val
            changed = True
        else:
            m = _FR_DATE_RE.match(val)
            if m:
                cols[i] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                changed = True
                continue

        if i in integer_col_indices and _DECIMAL_DOT_RE.match(val):
            cols[i] = str(int(float(val)))
            changed = True

    return ("\t".join(cols) + "\n", changed)

# Dictionnaire de configuration : { 'nom_de_la_table': index_de_la_colonne_texte (0-indexed) }
# On cible les colonnes "désignation" / "intitulé" qui sont le plus sujettes aux tabulations accidentelles.
CLEANER_CONFIG = {
    "F_ARTICLE": 1,   # ar_design est la 2ème colonne (index 1)
    "F_DOCLIGNE": 12,  # dl_design est la 13ème colonne (index 12) — voir référence article ex: 'AF1733K_MSF' / 'AIR FILTER' + code modèle scindé par erreur (ex: 'R932')
}

# Certains exports Sage (ex: MULIPARTS) omettent en fin de ligne les colonnes
# "montant net" de F_DOCLIGNE (dl_montanthtnet, dl_montantttcnet), absentes de leur
# configuration d'export. À la demande métier, ces colonnes manquantes sont
# complétées avec la même valeur que leurs équivalents bruts (dl_montantht,
# dl_montantttc) plutôt que d'être laissées NULL.
# Format : { table: [(index_colonne_manquante, index_colonne_source), ...] } — dans l'ordre du fichier.
MISSING_TRAILING_COLUMNS_FALLBACK = {
    "F_DOCLIGNE": [(29, 24), (30, 25)],  # dl_montanthtnet ← dl_montantht, dl_montantttcnet ← dl_montantttc
}


def _strip_header_row(filepath: str, table_name: str, run_id: str, client_schema: str) -> bool:
    """
    Certains exports Sage (ex: MULIPARTS) incluent par erreur une ligne d'en-tête
    (ex: 'CO_NO\tCO_NOM\t...') alors que le pipeline attend des fichiers sans header.
    Si la 1ère ligne non vide correspond aux noms de colonnes attendus (COLUMNS_ORDER),
    elle est légitime mais n'est pas une donnée : on la retire avant la validation.
    Retourne True si une ligne a été retirée.
    """
    expected_cols = COLUMNS_ORDER.get(table_name)
    if not expected_cols:
        return False

    try:
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            lines = f.readlines()

        if not lines:
            return False

        first_line = lines[0].rstrip('\r\n')
        first_cols = [c.strip().lower() for c in first_line.split('\t')]

        if first_cols == list(expected_cols):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines[1:])

            logger.warning(
                f"[Nettoyage Auto] Ligne d'en-tête détectée et retirée pour {table_name}.",
                extra={
                    "run_id": run_id,
                    "client": client_schema,
                    "table": table_name,
                    "step": "sage_cleaner",
                }
            )
            return True

        return False

    except Exception as e:
        logger.error(
            f"[Nettoyage Auto] Erreur lors de la détection d'en-tête de {filepath}: {e}",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "step": "sage_cleaner"
            }
        )
        return False


def clean_sage_file(filepath: str, table_name: str, run_id: str = "N/A", client_schema: str = "N/A", pg_columns=None) -> int:
    """
    Lit le fichier TSV, détecte les lignes ayant trop de tabulations (colonnes),
    et tente de fusionner les colonnes excédentaires dans la colonne texte ciblée.
    Modifie le fichier sur place. Retourne le nombre de lignes corrigées.
    `pg_columns` (optionnel) : schéma PostgreSQL de la table, utilisé pour tronquer
    les valeurs décimales tombant dans une colonne entière (ex: co_no = '204.1').
    """
    _strip_header_row(filepath, table_name, run_id, client_schema)

    expected_count = COLUMNS_COUNT.get(table_name)
    if not expected_count:
        return 0

    text_col_idx = CLEANER_CONFIG.get(table_name)
    fallback_specs = MISSING_TRAILING_COLUMNS_FALLBACK.get(table_name)
    integer_col_indices = _integer_column_indices(table_name, pg_columns)
    # Nombre de colonnes réellement produites par l'export de ce client, avant padding
    # des colonnes de fin systématiquement absentes (ex: F_DOCLIGNE en fournit 29 sur 31).
    baseline_count = expected_count - (len(fallback_specs) if fallback_specs else 0)

    lines_fixed = 0
    locale_fields_fixed = 0
    blank_lines_removed = 0
    try:
        # Lire avec encodage tolérant, Sage produit souvent des caractères spéciaux.
        # utf-8-sig : consomme le BOM éventuel plutôt que de le laisser comme caractère
        # littéral '﻿' en tête de la 1ère ligne (sinon .strip() ne la voit pas
        # comme vide et une ligne "BOM seul" passe à tort la détection de ligne vide).
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            lines = f.readlines()

        fixed_lines = []
        for line in lines:
            if not line.strip():
                # Une ligne vide n'a aucune colonne : COPY PostgreSQL exige un nombre
                # de colonnes exact par ligne et échoue dessus ("missing data for
                # column..."). On la retire plutôt que de tenter de la "compléter".
                blank_lines_removed += 1
                continue

            line, locale_changed = _normalize_locale_fields(line, integer_col_indices)
            if locale_changed:
                locale_fields_fixed += 1

            line_clean = line.rstrip('\r\n')
            cols = line_clean.split('\t')
            fixed = False

            # Idempotence : une ligne qui a déjà le nombre de colonnes final attendu
            # a déjà été nettoyée (par ce run ou un précédent, ex: retry après une
            # erreur infra). La retraiter fusionnerait/paddérait à tort des colonnes
            # déjà correctes (ex: dl_design qui absorbe dl_qte/dl_qtebc).
            already_clean = len(cols) == expected_count

            # 1) Trop de colonnes par rapport à la baseline du client : une tabulation
            #    parasite a coupé le champ texte (ex: 'AIR FILTER ' / 'R932') → on fusionne.
            baseline_diff = len(cols) - baseline_count
            if not already_clean and baseline_diff > 0 and text_col_idx is not None:
                end_idx = text_col_idx + baseline_diff
                merged_text = " ".join(cols[text_col_idx : end_idx + 1])
                merged_text = " ".join(merged_text.split())
                cols = cols[:text_col_idx] + [merged_text] + cols[end_idx + 1:]
                fixed = True

            # 2) Colonnes de fin systématiquement absentes chez ce client : on les
            #    complète avec les valeurs sources configurées (ex: montants nets).
            if not already_clean and fallback_specs and len(cols) == baseline_count:
                new_cols = list(cols)
                for missing_idx, source_idx in sorted(fallback_specs):
                    if missing_idx != len(new_cols) or source_idx >= len(new_cols):
                        break  # positions inattendues : on laisse Phase 1 rejeter la ligne
                    new_cols.append(new_cols[source_idx])
                else:
                    cols = new_cols
                    fixed = True

            if fixed:
                fixed_lines.append("\t".join(cols) + "\n")
                lines_fixed += 1
            else:
                fixed_lines.append(line)

        # Si on a corrigé des lignes (tabulations, formats locaux et/ou lignes vides), on réécrit le fichier
        if lines_fixed > 0 or locale_fields_fixed > 0 or blank_lines_removed > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(fixed_lines)

            if lines_fixed > 0:
                logger.warning(
                    f"[Nettoyage Auto] {lines_fixed} lignes avec tabulations excessives corrigées dans {table_name}.",
                    extra={
                        "run_id": run_id,
                        "client": client_schema,
                        "table": table_name,
                        "step": "sage_cleaner"
                    }
                )
            if locale_fields_fixed > 0:
                logger.warning(
                    f"[Nettoyage Auto] {locale_fields_fixed} lignes avec formats locaux (virgule décimale / date JJ-MM-AAAA) normalisées dans {table_name}.",
                    extra={
                        "run_id": run_id,
                        "client": client_schema,
                        "table": table_name,
                        "step": "sage_cleaner"
                    }
                )
            if blank_lines_removed > 0:
                logger.warning(
                    f"[Nettoyage Auto] {blank_lines_removed} ligne(s) vide(s) supprimée(s) dans {table_name}.",
                    extra={
                        "run_id": run_id,
                        "client": client_schema,
                        "table": table_name,
                        "step": "sage_cleaner"
                    }
                )

        return lines_fixed

    except Exception as e:
        logger.error(
            f"[Nettoyage Auto] Erreur lors du nettoyage de {filepath}: {e}",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "step": "sage_cleaner"
            }
        )
        return 0
