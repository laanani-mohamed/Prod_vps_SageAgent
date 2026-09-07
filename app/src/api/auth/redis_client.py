"""
api/auth/redis_client.py

Gestion de la connexion Redis pour le stockage des tokens (JTI).
Inclut un fallback en mémoire pour le développement local si Redis n'est pas dispo.
"""
import logging
from datetime import timedelta
import redis
from .config import auth_settings

logger = logging.getLogger("api.auth.redis")

class LocalMemoryCache:
    """Fallback en mémoire pour l'environnement de développement local."""
    def __init__(self):
        self._cache = {}

    def setex(self, key: str, time: timedelta, value: str):
        from datetime import datetime
        # On ignore l'expiration réelle en fallback local
        self._cache[key] = value

    def exists(self, key: str) -> int:
        return 1 if key in self._cache else 0

    def delete(self, key: str):
        self._cache.pop(key, None)

    def getdel(self, key: str):
        return self._cache.pop(key, None)

def get_redis_client():
    if auth_settings.ENV == "development":
        logger.info("[AUTH] Fallback Redis local activé (LocalMemoryCache)")
        return LocalMemoryCache()
    
    try:
        client = redis.Redis(
            host=auth_settings.REDIS_HOST,
            port=auth_settings.REDIS_PORT,
            decode_responses=True,
            socket_timeout=2
        )
        client.ping()
        return client
    except redis.ConnectionError:
        logger.error("[AUTH] ❌ Impossible de se connecter à Redis (%s:%s)", auth_settings.REDIS_HOST, auth_settings.REDIS_PORT)
        return LocalMemoryCache()

# Instance singleton
redis_client = get_redis_client()
