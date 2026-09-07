"""
api/bi/use_cases/balance_uc.py

Use Case : POST /api/bi/rapport/balance
Orchestre : repository (PG) → business_logic (Polars) → réponse Pydantic.
"""
from __future__ import annotations
import logging

from api.bi.schemas import BalanceClientRequest, RapportResponse
from api.bi.repositories.pg_repo.bi_balance_repo import PgBIBalanceClientRepository
from api.bi.business_logic.balance_calculations import calculate_balance_client

logger = logging.getLogger("api.bi.use_cases.balance_uc")


def execute(req: BalanceClientRequest) -> RapportResponse:
    repo = PgBIBalanceClientRepository()
    
    # 1. Fetch raw un-paid invoices from PG
    raw_data = repo.fetch(req)
    
    if not raw_data:
        return RapportResponse(
            endpoint="/api/bi/rapport/balance",
            client_schema=req.client_schema,
            source="db_latest",
            total_rows=0,
            data=[],
        )

    # 2. Process data with Polars to bucket into M1..M6, En Cours, A Nouveau
    processed_data = calculate_balance_client(raw_data)

    return RapportResponse(
        endpoint="/api/bi/rapport/balance",
        client_schema=req.client_schema,
        source="db_latest",
        total_rows=len(processed_data),
        data=processed_data,
    )
