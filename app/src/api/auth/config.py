"""
api/auth/config.py

Configuration de l'authentification (clés RSA, durée des tokens).
"""
import os
from typing import List
from pydantic_settings import BaseSettings

class AuthSettings(BaseSettings):
    # Clés asymétriques RS256
    PRIVATE_KEY_PATH: str = os.getenv("PRIVATE_KEY_PATH", "/opt/SageAgent/certs/private.pem")
    PUBLIC_KEY_PATH: str = os.getenv("PUBLIC_KEY_PATH", "/opt/SageAgent/certs/public.pem")
    ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 #30 min
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7 #7 jours
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8505", "http://51.255.161.55:8505", "http://51.255.161.55:8501"]
    ENV: str = "production"
    REDIS_HOST: str = "51.255.161.55"
    REDIS_PORT: int = 6379

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

auth_settings = AuthSettings()

# Chargement des clés en mémoire au démarrage
# S'ils sont absents, le service crashera volontairement (sécurité par défaut)
private_key_path = auth_settings.PRIVATE_KEY_PATH
public_key_path = auth_settings.PUBLIC_KEY_PATH

try:
    with open(private_key_path, "r") as f:
        PRIVATE_KEY = f.read()

    with open(public_key_path, "r") as f:
        PUBLIC_KEY = f.read()
except FileNotFoundError as e:
    import logging
    logging.getLogger("api.auth").error(f"Fichier de clé manquant : {e}")
    # En développement, on crée une fausse clé pour ne pas bloquer les tests unitaires isolés
    if auth_settings.ENV == "development":
        PRIVATE_KEY = "DUMMY_PRIVATE"
        PUBLIC_KEY = "DUMMY_PUBLIC"
        auth_settings.ALGORITHM = "HS256" # Fallback pour les tests
    else:
        raise
