"""
api/auth/dependencies.py

Dépendances FastAPI pour l'authentification et l'autorisation RBAC.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import logging

from .service import verify_access_token
from .schemas import TokenData
from .redis_client import redis_client

logger = logging.getLogger("api.auth.dependencies")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Décode le JWT, vérifie sa validité et retourne le TokenData.
    Renvoie 401 si invalide.
    """
    token_data = verify_access_token(token)
    if not token_data:
        logger.warning("[AUTH] Tentative d'accès avec token invalide ou expiré")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data

def require_role(*required_roles: str):
    """
    Factory de dépendance pour vérifier que l'utilisateur possède l'un des rôles spécifiés.
    Utilisation : Depends(require_role("analyst"))
    """
    async def _check(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if not any(role in current_user.roles for role in required_roles):
            logger.warning("[AUTH] Accès refusé pour %s (rôle manquant : %s)", current_user.username, required_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Nécessite l'un des rôles: {', '.join(required_roles)}"
            )
        return current_user
    return _check
