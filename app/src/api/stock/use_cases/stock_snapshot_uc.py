"""
bi/stock/use_cases/stock_snapshot_uc.py
"""
from api.stock.schemas import StockSnapshotRequest, StockResponse
from api.stock.repositories.factory_repo import get_repo
from api.stock.business_logic import aggregations

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

    # Extraire le timestamp source si présent
    source = req.source_type
    if data and "__source_timestamp__" in data[0]:
        source = f"archive:{data[0].pop('__source_timestamp__')}"
        for row in data:
            row.pop("__source_timestamp__", None)

    # Warnings pour réf manquantes
    warnings = []
    if req.ar_ref:
        found_refs = {str(row.get("ar_ref", "")).strip() for row in data}
        for ref in req.ar_ref:
            if ref not in found_refs:
                source_label = "les archives"
                warnings.append(f"La référence '{ref}' n'existe pas dans {source_label}.")

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
