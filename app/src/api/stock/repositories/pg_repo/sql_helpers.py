"""
bi/stock/repositories/pg_repo/sql_helpers.py

Helpers pour la construction dynamique de requêtes SQL.
"""
import re
from typing import Optional

def validate_schema(schema: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_]+$", schema):
        raise ValueError(f"Nom de schéma invalide : {schema}")
    return schema.lower()

def add_in(sql: str, column: str, values: list, params: list) -> str:
    """Ajoute un filtre AND column IN (%s, %s, ...) si values non vide."""
    if not values:
        return sql
    placeholders = ", ".join(["%s"] * len(values))
    params.extend(values)
    return sql + f" AND {column} IN ({placeholders})"

def add_ilike(sql: str, column: str, value: Optional[str], params: list) -> str:
    """Ajoute un filtre AND LOWER(column) LIKE LOWER(%value%) si value fourni."""
    if not value:
        return sql
    params.append(f"%{value}%")
    return sql + f" AND LOWER({column}::text) LIKE LOWER(%s)"

def add_eq(sql: str, column: str, value, params: list) -> str:
    """Ajoute AND column = %s si value non None."""
    if value is None:
        return sql
    params.append(value)
    return sql + f" AND {column} = %s"

def add_gte(sql: str, column: str, value, params: list) -> str:
    if value is None:
        return sql
    params.append(value)
    return sql + f" AND {column} >= %s"

def add_lte(sql: str, column: str, value, params: list) -> str:
    if value is None:
        return sql
    params.append(value)
    return sql + f" AND {column} <= %s"
