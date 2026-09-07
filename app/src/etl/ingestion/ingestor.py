import logging
import psycopg2
import psycopg2.errors
import os
from config.db_config import DB_CONFIG
from map_data.reference.file_table_map import FILE_TABLE_MAP, INSERTION_ORDER
from map_data.reference.columns_order_number import COLUMNS_ORDER
from etl.utils.db_safe import db_retry, safe_search_path, safe_truncate, safe_copy
from etl.utils.null_cleaner import clean_null_values

logger = logging.getLogger("etl.ingestor")

@db_retry(max_attempts=3, delay=5)
def ingest(folder_path: str, client_schema: str, run_id: str) -> tuple[bool, str, str]:
    """
    Ouvre une transaction unique sur le schéma du client.
    1. TRUNCATE CASCADE de toutes les tables détectées.
    2. COPY dans l'ordre strict de dépendance (FK).
    Retourne un tuple (success, error_type, error_code).
    """
    logger.info("Début de l'ingestion.", 
                extra={"run_id": run_id, "client": client_schema, "step": "ingestion_start"})

    # --- Phase 0 : Nettoyage préalable des fichiers ---
    clean_null_values(folder_path, run_id, client_schema)

    # Identifier uniquement les fichiers présents qui correspondent à une table connue (insensible à la casse)
    expected_upper_map = {k.upper(): v for k, v in FILE_TABLE_MAP.items()}
    
    found_files = []
    tables_present = set()
    for f in os.listdir(folder_path):
        if os.path.isfile(os.path.join(folder_path, f)) and f.upper() in expected_upper_map:
            found_files.append(f)
            tables_present.add(expected_upper_map[f.upper()])

    sorted_tables  = [t for t in INSERTION_ORDER if t in tables_present]

    if not sorted_tables:
        logger.warning("Aucun fichier à ingérer trouvé dans le dossier.", 
                       extra={"run_id": run_id, "client": client_schema, "step": "ingestion_empty"})
        return True, "SUCCESS", "SUCCESS"

    current_action = "CONNECT"
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur  = conn.cursor()

        # Pointer sur le bon schéma client (SÉCURISÉ)
        cur.execute(safe_search_path(client_schema.lower()))

        # Désactiver la vérification des clés étrangères (Foreign Keys) pour la transaction
        cur.execute("SET session_replication_role = 'replica';")

        # --- Phase 1 : Purge globale (TRUNCATE CASCADE) (SÉCURISÉ) ---
        current_action = "TRUNCATE"
        logger.info(f"TRUNCATE CASCADE : {', '.join(sorted_tables)}", 
                    extra={"run_id": run_id, "client": client_schema, "step": "ingestion_truncate"})
        cur.execute(safe_truncate(client_schema.lower(), sorted_tables))

        # --- Phase 2 : Insertion dans l'ordre de dépendance ---
        for table_name in sorted_tables:
            current_action = "COPY"
            filename = next(f for f in found_files if expected_upper_map[f.upper()] == table_name)
            filepath = os.path.join(folder_path, filename)

            logger.info(f"COPY → {table_name}", 
                        extra={"run_id": run_id, "client": client_schema, "table": table_name, "step": "ingestion_copy"})

            # Ouverture binaire : permet de détecter et sauter le BOM Windows (\xef\xbb\xbf)
            # sans que psycopg2 puisse le "court-circuiter" (comme il le ferait en mode texte)
            with open(filepath, 'rb') as f:
                bom = f.read(3)
                if bom != b'\xef\xbb\xbf':
                    f.seek(0)  # Pas de BOM → on revient au début

                # Récupérer l'ordre exact des colonnes défini pour cette table
                cols = COLUMNS_ORDER.get(table_name)
                if not cols:
                    raise ValueError(f"Ordre des colonnes non défini pour la table : {table_name}")

                # Mode TEXT (pas CSV) pour ignorer les guillemets dans les données Sage (SÉCURISÉ)
                cur.copy_expert(sql=safe_copy(client_schema.lower(), table_name, cols), file=f)

            # Si la table est F_COLLABORATEUR, on insère la ligne par défaut co_no = 0 pour éviter des violations FK
            if table_name == "F_COLLABORATEUR":
                from psycopg2 import sql
                insert_query = sql.SQL(
                    "INSERT INTO {schema}.f_collaborateur (co_no, co_nom, co_vendeur, co_acheteur) "
                    "VALUES (0, 'Aucun Collaborateur', 0, 0) "
                    "ON CONFLICT (co_no) DO NOTHING"
                ).format(schema=sql.Identifier(client_schema.lower()))
                cur.execute(insert_query)

            # Si la table est F_ARTICLE, on insère l'article par défaut 'NULL' pour éviter des violations FK dans f_docligne
            if table_name == "F_ARTICLE":
                from psycopg2 import sql
                insert_query = sql.SQL(
                    "INSERT INTO {schema}.f_article (ar_ref, ar_design) "
                    "VALUES ('NULL', 'ARTICLE NULL') "
                    "ON CONFLICT (ar_ref) DO NOTHING"
                ).format(schema=sql.Identifier(client_schema.lower()))
                cur.execute(insert_query)

        # Réactiver la vérification des clés étrangères
        cur.execute("SET session_replication_role = 'origin';")

        conn.commit()
        logger.info("Transaction validée. Base de données à jour.", 
                    extra={"run_id": run_id, "client": client_schema, "step": "ingestion_success"})
        return True, "SUCCESS", "SUCCESS"

    except Exception as e:
        if conn:
            conn.rollback()

        # Qualification stricte du code d'erreur DB
        error_code = "UNKNOWN_EXCEPTION"
        error_type = "INFRA_ERROR"
        
        if current_action == "CONNECT":
            error_code = "DB_CONNECTION_FAILED"
            error_type = "INFRA_ERROR"
        elif current_action == "TRUNCATE":
            error_code = "TRUNCATE_FAILED"
            error_type = "INFRA_ERROR"
        elif current_action == "COPY":
            error_type = "DATA_ERROR"
            if isinstance(e, psycopg2.errors.ForeignKeyViolation):
                error_code = "FK_VIOLATION"
            elif isinstance(e, (psycopg2.errors.DataError, psycopg2.errors.DatatypeMismatch)):
                error_code = "DATA_TYPE_ERROR"
            else:
                error_code = "COPY_FAILED"

        logger.error(f"Rollback déclenché lors de {current_action} : {e}", 
                     extra={"run_id": run_id, "client": client_schema, "error_type": error_type, "error_code": error_code, "step": "ingestion_rollback"})
        return False, error_type, error_code

    finally:
        if conn:
            conn.close()
