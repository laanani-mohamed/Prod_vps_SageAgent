"""
api/transactions/router.py — Routeur FastAPI pour le module Transactions.
"""
import logging
from fastapi import APIRouter, HTTPException, Request, Depends

from api.auth.dependencies import require_role
from api.auth.schemas import TokenData
from api._base_router import secured_handle

from api.transactions.schemas import TransactionsRequest, TransactionsResponse
from api.transactions.service import get_transactions

logger = logging.getLogger("api.transactions.router")
router = APIRouter(prefix="/api/transactions", tags=["Transactions"])

@router.post("/ventes", response_model=TransactionsResponse)
def get_ventes(
    req: TransactionsRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
):
    # Forcer le domaine vente (0) s'il n'est pas spécifié, ou s'assurer qu'il est inclus
    if 0 not in req.filters.do_domaine:
        req.filters.do_domaine = [0]
    return secured_handle(
        get_transactions,
        endpoint="/api/transactions/ventes",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )

@router.post("/achats", response_model=TransactionsResponse)
def get_achats(
    req: TransactionsRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
):
    # Forcer le domaine achat (1) s'il n'est pas spécifié, ou s'assurer qu'il est inclus
    if 1 not in req.filters.do_domaine:
        req.filters.do_domaine = [1]
    return secured_handle(
        get_transactions,
        endpoint="/api/transactions/achats",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )

@router.post("/documents", response_model=TransactionsResponse)
def get_documents(
    req: TransactionsRequest,
    r: Request,
    current_user: TokenData = Depends(require_role("analyst"))
):
    return secured_handle(
        get_transactions,
        endpoint="/api/transactions/documents",
        request=r,
        current_user=current_user,
        client_schema=req.client_schema,
        req=req,
    )
