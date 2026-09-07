"""
api/auth/service.py

Génération et validation des tokens JWT RS256, hashage des mots de passe.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import jwt, JWTError
import uuid

from .config import auth_settings, PRIVATE_KEY, PUBLIC_KEY
from .redis_client import redis_client
from .schemas import UserInDB, TokenData

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash pré-calculé pour éviter les attaques temporelles (timing attack)
_DUMMY_HASH = pwd_context.hash("__dummy_internal_only__")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(user: UserInDB) -> str:
    """Access token : courte durée, vérification purement stateless avec RS256 (et blocklist)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=auth_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = str(uuid.uuid4())
    payload = {
        "sub": user.username,
        "roles": user.roles,
        "schemas": user.allowed_schemas,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": jti,
        "type": "access",
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm=auth_settings.ALGORITHM)

def create_refresh_token(user: UserInDB) -> str:
    """Refresh token : longue durée, JTI stocké dans Redis."""
    expire = datetime.now(timezone.utc) + timedelta(days=auth_settings.REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())
    payload = {
        "sub": user.username,
        "jti": jti,
        "exp": expire,
        "type": "refresh",
    }
    token = jwt.encode(payload, PRIVATE_KEY, algorithm=auth_settings.ALGORITHM)
    redis_client.setex(
        f"refresh:{jti}",
        timedelta(days=auth_settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user.username
    )
    return token

def verify_access_token(token: str) -> Optional[TokenData]:
    """Décoder et valider un access token."""
    try:
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=[auth_settings.ALGORITHM],
        )
        if payload.get("type") != "access":
            return None
        
        jti = payload.get("jti")
        if not jti:
            return None  # Rejeter les tokens sans JTI (legacy)
        
        if redis_client.exists(f"access:blocklist:{jti}"):
            return None  # Token révoqué

        
        username: str = payload.get("sub")
        if username is None:
            return None
            
        return TokenData(
            username=username,
            roles=payload.get("roles", []),
            allowed_schemas=payload.get("schemas", [])
        )
    except JWTError:
        return None

def revoke_refresh_token(token: str):
    """Révoque un refresh token en le supprimant de Redis."""
    try:
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=[auth_settings.ALGORITHM],
        )
        jti = payload.get("jti")
        if jti:
            redis_client.delete(f"refresh:{jti}")
    except JWTError:
        pass

def revoke_access_token(token: str):
    """Révoque un access token en l'ajoutant à la blocklist."""
    try:
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=[auth_settings.ALGORITHM],
            options={"verify_exp": False} # On décode même si expiré
        )
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            now = datetime.now(timezone.utc).timestamp()
            ttl_restant = int(exp - now)
            if ttl_restant > 0:
                redis_client.setex(f"access:blocklist:{jti}", timedelta(seconds=ttl_restant), "revoked")
    except JWTError:
        pass
