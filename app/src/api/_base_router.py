"""
api/_base_router.py

Helper générique pour tous les routeurs API.
Gère l'injection des dépendances (current_user), l'audit log asynchrone
et la vérification des permissions (accès aux schémas).
"""
import logging
import time
import inspect
from typing import Callable, Any, Optional
from fastapi import Request, HTTPException, status

from api.auth.schemas import TokenData
from api.auth.audit import log_audit_event

logger = logging.getLogger("api.router.base")

def secured_handle(
    service_func: Callable,
    endpoint: str,
    request: Request,
    current_user: TokenData,
    client_schema: Optional[str] = None,
    *args,
    **kwargs
) -> Any:
    """
    Exécute une fonction de service (ex: get_dashboard) de manière sécurisée :
      1. Vérifie si l'utilisateur a accès au schema demandé
      2. Loggue l'action dans l'audit (fire-and-forget)
      3. Gère les erreurs globales
    """
    start_time = time.time()
    ip_address = request.client.host if request.client else "unknown"

    # Vérification RBAC Schema Level
    is_telegram = current_user.username == "telegram_agent"
    
    if client_schema and not is_telegram and client_schema not in current_user.allowed_schemas:
        logger.warning(
            "[SECURITY] Utilisateur '%s' a tenté d'accéder au schéma '%s' (non autorisé)",
            current_user.username, client_schema
        )
        log_audit_event(
            action="ACCESS_DENIED",
            endpoint=endpoint,
            ip_address=ip_address,
            status="FAILED",
            username=current_user.username,
            client_schema=client_schema,
            details="Accès refusé au schéma"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Vous n'avez pas accès aux données du client '{client_schema}'"
        )

    try:
        # Exécution de la fonction métier
        sig = inspect.signature(service_func)
        if 'client_schema' in sig.parameters and 'client_schema' not in kwargs and client_schema is not None:
            kwargs['client_schema'] = client_schema
        if 'endpoint' in sig.parameters and 'endpoint' not in kwargs:
            kwargs['endpoint'] = endpoint
            
        response = service_func(*args, **kwargs)
        
        # Log succès
        duration_ms = int((time.time() - start_time) * 1000)
        log_audit_event(
            action="API_CALL",
            endpoint=endpoint,
            ip_address=ip_address,
            status="SUCCESS",
            username=current_user.username,
            client_schema=client_schema,
            details=f"Durée: {duration_ms}ms"
        )
        return response

    except Exception as e:
        # Log erreur
        logger.error("[API_ERROR] %s: %s", endpoint, e, exc_info=True)
        log_audit_event(
            action="API_ERROR",
            endpoint=endpoint,
            ip_address=ip_address,
            status="ERROR",
            username=current_user.username,
            client_schema=client_schema,
            details=str(e)
        )
        if isinstance(e, FileNotFoundError):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")
