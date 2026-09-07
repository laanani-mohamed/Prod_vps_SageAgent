import time
import logging
import re
import psycopg2
from psycopg2 import sql
from typing import List
from functools import wraps

logger = logging.getLogger("etl.db_safe")

# ---------------------------------------------------------------------------
# 1. PROTECTION INJECTION SQL (Identifiants postgres purs)
# ---------------------------------------------------------------------------

_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,62}$')

def validate_identifier(name: str, label: str = "identifiant") -> str:
    """
    Vérifie qu'un nom est un identifiant PostgreSQL légal et sûr.
    Garantit l'absence totale de caractères spéciaux utilisés pour l'injection.
    """
    if not _IDENTIFIER_PATTERN.match(name):
        raise ValueError(f"{label} invalide et potentiellement dangereux : '{name}'")
    return name

def safe_search_path(schema: str) -> sql.Composed:
    """ Produit une requête protégée : SET search_path TO "nom_du_schema" """
    validate_identifier(schema, "schéma client")
    return sql.SQL("SET search_path TO {};").format(sql.Identifier(schema.lower()))

def safe_truncate(schema: str, tables: List[str]) -> sql.Composed:
    """ Produit une requête protégée : TRUNCATE TABLE "schema"."t1", "schema"."t2" CASCADE """
    validate_identifier(schema, "schéma")
    for t in tables:
        validate_identifier(t, "table")
    # On force schema et table en minuscules pour correspondre au stockage standard Postgres
    identifiers = sql.SQL(", ").join(sql.Identifier(schema.lower(), t.lower()) for t in tables)
    return sql.SQL("TRUNCATE TABLE {} CASCADE;").format(identifiers)

def safe_copy(schema: str, table: str, columns: List[str]) -> sql.Composed:
    """ Produit une requête protégée : COPY "schema"."t1" ("c1", "c2") FROM STDIN WITH DELIMITER E'\t' NULL '' """
    validate_identifier(schema, "schéma")
    validate_identifier(table, "table")
    for col in columns:
        validate_identifier(col, "colonne")
    # Formater les colonnes en identifiants sécurisés
    cols_sql = sql.SQL(", ").join(sql.Identifier(col.lower()) for col in columns)
    # NULL '' : les champs vides (tabulations consécutives) sont traités comme SQL NULL
    # Cela est essentiel pour les colonnes FK nullable comme ar_ref dans f_docligne
    return sql.SQL("COPY {} ({}) FROM STDIN WITH DELIMITER E'\\t' NULL ''").format(
        sql.Identifier(schema.lower(), table.lower()),
        cols_sql
    )


# ---------------------------------------------------------------------------
# 2. ROBUSTESSE RÉSEAU (Retry Operations)
# ---------------------------------------------------------------------------

def db_retry(max_attempts: int = 3, delay: int = 5):
    """
    Décorateur qui capte spécifiquement les pertes de connexion PostgreSQL 
    (psycopg2.OperationalError) et retente la fonction automatiquement.
    S'il s'agit d'une erreur de logique métier (DataError, etc), il crash instantanément.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except psycopg2.OperationalError as e:
                    if attempt == max_attempts:
                        logger.error(f"[{func.__name__}] Échec définitif base de données après {max_attempts} tentatives : {e}")
                        raise
                    logger.warning(f"[{func.__name__}] Micro-coupure réseau ! (Tentative {attempt}/{max_attempts}). Réessai dans {delay} sec...")
                    time.sleep(delay)
        return wrapper
    return decorator
