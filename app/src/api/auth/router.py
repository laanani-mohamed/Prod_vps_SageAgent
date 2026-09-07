"""
api/auth/router.py

Router pour l'authentification : login, refresh token, logout.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
import psycopg2
from psycopg2.extras import RealDictCursor

from .schemas import Token, RefreshTokenRequest, UserInDB
from .service import verify_password, create_access_token, create_refresh_token, revoke_refresh_token, verify_access_token, revoke_access_token, _DUMMY_HASH
from .audit import log_audit_event
from api.db import get_db
from api.rate_limiter import limiter
from .dependencies import oauth2_scheme

logger = logging.getLogger("api.auth.router")

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_user(conn, username: str) -> Optional[UserInDB]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM auth.users WHERE username = %s", (username,))
        row = cur.fetchone()
        if row:
            return UserInDB(**row)
    return None

@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    conn = Depends(get_db)
):
    ip_address = request.client.host if request.client else "unknown"
    
    user = get_user(conn, form_data.username)
        
    hash_to_check = user.hashed_password if user else _DUMMY_HASH
    password_ok = verify_password(form_data.password, hash_to_check)
        
    if not user or not password_ok:
        log_audit_event("LOGIN", "/api/auth/token", ip_address, "FAILED", username=form_data.username, details="Identifiants incorrects")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
            
    if not user.is_active:
        log_audit_event("LOGIN", "/api/auth/token", ip_address, "FAILED", username=form_data.username, details="Compte inactif")
        raise HTTPException(status_code=400, detail="Compte inactif")

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
        
    log_audit_event("LOGIN", "/api/auth/token", ip_address, "SUCCESS", username=user.username)
        
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
@limiter.limit("10/minute")
def refresh_access_token(
    request: Request,
    body: RefreshTokenRequest,
    conn = Depends(get_db)
):
    ip_address = request.client.host if request.client else "unknown"
    from .config import auth_settings, PUBLIC_KEY
    from jose import jwt, JWTError
    from .redis_client import redis_client
    
    try:
        # 1. Décoder directement le refresh token
        payload = jwt.decode(
            body.refresh_token,
            PUBLIC_KEY,
            algorithms=[auth_settings.ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise ValueError("Type de token invalide")
            
        username = payload.get("sub")
        jti = payload.get("jti")
        
        redis_key = f"refresh:{jti}"
        
        # 2. Vérifier ET consommer atomiquement l'ancien refresh token
        if not redis_client.getdel(redis_key):
            log_audit_event("REFRESH_REUSE", "/api/auth/refresh", ip_address, "FAILED", details="Token révoqué")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token déjà utilisé ou révoqué. Veuillez vous reconnecter.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except JWTError as e:
        log_audit_event("REFRESH", "/api/auth/refresh", ip_address, "FAILED", details=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError as e:
        log_audit_event("REFRESH", "/api/auth/refresh", ip_address, "FAILED", details=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Vérifier l'utilisateur
    user = get_user(conn, username)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou inactif")

    # 4. Émettre de nouveaux tokens
    access_token = create_access_token(user)
    new_refresh_token = create_refresh_token(user)
    log_audit_event("REFRESH", "/api/auth/refresh", ip_address, "SUCCESS", username=user.username)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

@router.post("/logout")
def logout(
    request: Request,
    body: RefreshTokenRequest,
    token: str = Depends(oauth2_scheme)
):
    ip_address = request.client.host if request.client else "unknown"
    # Révoquer l'access token
    revoke_access_token(token)
    # Révoquer le refresh token
    revoke_refresh_token(body.refresh_token)
    log_audit_event("LOGOUT", "/api/auth/logout", ip_address, "SUCCESS")
    return {"message": "Déconnexion réussie"}
