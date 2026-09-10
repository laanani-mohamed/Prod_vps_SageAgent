"""
api/bi/use_cases/balance_agee_uc.py

Use Case : POST /api/bi/rapport/balance-agee
Orchestre : repository (PG, réutilisé de balance_uc.py) → business_logic
(Polars, tranches en jours) → réponse Pydantic.
"""
from __future__ import annotations
import logging

from api.bi.schemas import BalanceClientRequest, RapportResponse
from api.bi.repositories.pg_repo.bi_balance_repo import PgBIBalanceClientRepository
from api.bi.business_logic.balance_calculations import calculate_balance_agee

logger = logging.getLogger("api.bi.use_cases.balance_agee_uc")


def execute(req: BalanceClientRequest) -> RapportResponse:
    repo = PgBIBalanceClientRepository()

    # Même source que la balance par mois (bi_balance_repo.py) : factures
    # impayées, do_domaine=0, do_type IN (6,7), reste_a_payer > 0.
    raw_data = repo.fetch(req)

    if not raw_data:
        return RapportResponse(
            endpoint="/api/bi/rapport/balance-agee",
            client_schema=req.client_schema,
            source="db_latest",
            total_rows=0,
            data=[],
        )

    processed_data = calculate_balance_agee(raw_data)

    return RapportResponse(
        endpoint="/api/bi/rapport/balance-agee",
        client_schema=req.client_schema,
        source="db_latest",
        total_rows=len(processed_data),
        data=processed_data,
    )
