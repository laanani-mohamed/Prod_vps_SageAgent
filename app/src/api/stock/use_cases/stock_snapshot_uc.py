"""
bi/stock/use_cases/stock_snapshot_uc.py
"""
from api.stock.schemas import StockSnapshotRequest, StockResponse
from api.stock.repositories.factory_repo import get_repo
from api.stock.business_logic import aggregations
from api.stock.business_logic.source_meta import extract_source_and_warnings

def execute(req: StockSnapshotRequest) -> StockResponse:
    repo = get_repo("snapshot", req.source_type)
    raw_data = repo.fetch(req)

    by_depot = req.by_depot
    if by_depot:
        data = aggregations.aggregate_by_depot(raw_data)
    else:
        data = aggregations.aggregate_availability(raw_data)

    metadata = {
        "snapshot_datetime": req.snapshot_datetime,
    }

    out_cols = ["ar_ref", "ar_design", "quantite_totale", "qte_par_depot"]
    if by_depot:
        out_cols += ["de_no", "de_intitule"]

    source, warnings = extract_source_and_warnings(data, req)

    return StockResponse(
        endpoint="/api/stock/snapshot",
        client_schema=req.client_schema,
        source=source,
        total_rows=len(data),
        columns=out_cols,
        data=data,
        metadata=metadata,
        warnings=warnings,
    )
