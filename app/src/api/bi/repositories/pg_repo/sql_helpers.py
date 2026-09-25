"""
api/bi/repositories/pg_repo/sql_helpers.py

Helpers pour la construction dynamique de requêtes SQL BI.
Réutilise les mêmes helpers que le module stock (validate_schema, add_in, etc.)
+ helpers spécifiques au BI (filtres de dates, domaine/type Sage).
"""
import re
from typing import Optional


def validate_schema(schema: str) -> str:
    """Valide et normalise un nom de schéma PostgreSQL (protection injection)."""
    if not re.match(r"^[a-zA-Z0-9_]+$", schema):
        raise ValueError(f"Nom de schéma invalide : {schema}")
    # Quoté car certains noms de client (ex: "cross") sont des mots-clés réservés PostgreSQL
    return f'"{schema.lower()}"'


def add_in(sql: str, column: str, values: list, params: list) -> str:
    """Ajoute AND column IN (%s, ...) si values non vide."""
    if not values:
        return sql
    placeholders = ", ".join(["%s"] * len(values))
    params.extend(values)
    return sql + f" AND {column} IN ({placeholders})"


def add_eq(sql: str, column: str, value, params: list) -> str:
    """Ajoute AND column = %s si value non None."""
    if value is None:
        return sql
    params.append(value)
    return sql + f" AND {column} = %s"


def add_gte(sql: str, column: str, value, params: list) -> str:
    """Ajoute AND column >= %s si value non None."""
    if value is None:
        return sql
    params.append(value)
    return sql + f" AND {column} >= %s"


def add_lte(sql: str, column: str, value, params: list) -> str:
    """Ajoute AND column <= %s si value non None."""
    if value is None:
        return sql
    params.append(value)
    return sql + f" AND {column} <= %s"


def add_date_range(
    sql: str,
    col: str,
    date_from: Optional[str],
    date_to: Optional[str],
    params: list,
) -> str:
    """
    Ajoute un filtre de période sur une colonne date Sage (format YYYY-MM-DD ou timestamp).
    Utilisé par les repos BI qui filtrent sur do_date, dl_date etc.
    """
    sql = add_gte(sql, f"CAST({col} AS TEXT)", date_from, params)
    sql = add_lte(sql, f"CAST({col} AS TEXT)", date_to, params)
    return sql


def sage_vente_filter(schema_alias: str = "") -> str:
    """
    Retourne la condition WHERE pour les factures de vente Sage :
    do_domaine = 0 AND do_type IN (6, 7)
    """
    prefix = f"{schema_alias}." if schema_alias else ""
    return f"{prefix}do_domaine = 0 AND {prefix}do_type IN (6, 7)"


def sage_achat_filter(schema_alias: str = "") -> str:
    """
    Retourne la condition WHERE pour les factures d'achat Sage :
    do_domaine = 1 AND do_type IN (16, 17)
    """
    prefix = f"{schema_alias}." if schema_alias else ""
    return f"{prefix}do_domaine = 1 AND {prefix}do_type IN (16, 17)"
