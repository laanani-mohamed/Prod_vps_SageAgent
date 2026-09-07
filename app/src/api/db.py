import logging
from contextlib import contextmanager
from psycopg2 import pool
from config.db_config import DB_CONFIG

logger = logging.getLogger("api.db")

_connection_pool = None

def init_db_pool():
    global _connection_pool
    try:
        if _connection_pool is None:
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                **DB_CONFIG
            )
            logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        raise e

def close_db_pool():
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        logger.info("Database connection pool closed")

# For FastAPI Depends()
def get_db():
    if not _connection_pool:
        raise Exception("Database connection pool not initialized")
    conn = _connection_pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _connection_pool.putconn(conn)

# Context manager for non-route functions (executors, services, etc.)
@contextmanager
def get_db_connection():
    if not _connection_pool:
        raise Exception("Database connection pool not initialized")
    conn = _connection_pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _connection_pool.putconn(conn)
