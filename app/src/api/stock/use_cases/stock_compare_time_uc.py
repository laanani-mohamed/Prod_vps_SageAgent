"""
bi/stock/use_cases/stock_compare_time_uc.py
"""
from api.stock.schemas import StockCompareTimeRequest, StockSnapshotRequest, StockResponse
from api.stock.repositories.factory_repo import get_repo
from api.stock.business_logic import comparison

def execute(req: StockCompareTimeRequest) -> StockResponse:
    date_from = req.date_from
    date_to = req.date_to

    # --- T1 : Archive snapshot ---
    snap_req_from = StockSnapshotRequest(
        client_schema=req.client_schema,
        source_type="archive",
        snapshot_datetime=f"{date_from}T23:59:59",
        limit=req.limit,
        ar_ref=req.ar_ref,
        fa_codefamille=req.fa_codefamille,
        by_depot=True
    )
    repo_archive = get_repo("snapshot", "archive")
    data_from = repo_archive.fetch(snap_req_from)

    # --- T2 : Archive ou Base Live ---
    if date_to:
        snap_req_to = StockSnapshotRequest(
            client_schema=req.client_schema,
            source_type="archive",
            snapshot_datetime=f"{date_to}T23:59:59",
            limit=req.limit,
            ar_ref=req.ar_ref,
            fa_codefamille=req.fa_codefamille,
            by_depot=True
        )
        data_to = repo_archive.fetch(snap_req_to)
    else:
        # Postgres live
        from api.stock.schemas import CheckAvailabilityRequest
        live_req = CheckAvailabilityRequest(
            client_schema=req.client_schema,
            source_type="db_latest",
            limit=req.limit,
            ar_ref=req.ar_ref,
            fa_codefamille=req.fa_codefamille,
            by_depot=True
        )
        repo_live = get_repo("availability", "db_latest")
        data_to = repo_live.fetch(live_req)

    # Calculer le delta
    data = comparison.calculate_time_delta(data_from, data_to)

    ts_from = data_from[0].get("__source_timestamp__", date_from) if data_from else date_from
    ts_to   = data_to[0].get("__source_timestamp__", date_to or "maintenant") if data_to else (date_to or "maintenant")

    # Nettoyer les timestamps si présents
    for row in data:
        row.pop("__source_timestamp__", None)

    total_delta = sum(row.get("delta", 0) or 0 for row in data)
    nb_hausse   = sum(1 for row in data if (row.get("delta", 0) or 0) > 0)
    nb_baisse   = sum(1 for row in data if (row.get("delta", 0) or 0) < 0)

    metadata = {
        "periode_debut":     ts_from,
        "periode_fin":       ts_to,
        "total_delta":       total_delta,
        "nb_articles_hausse": nb_hausse,
        "nb_articles_baisse": nb_baisse,
        "nb_articles_stables": len(data) - nb_hausse - nb_baisse,
    }

    out_cols = ["ar_ref", "ar_design", "qte_t1", "qte_t2", "delta", "qte_par_depot_t1", "qte_par_depot_t2"]
    out_cols = [c for c in out_cols if data and c in data[0]]

    # Extraire le timestamp source si présent
    source = req.source_type
    if data_from and "__source_timestamp__" in data_from[0]:
        source = f"archive:{data_from[0].get('__source_timestamp__')}"

    # Warnings pour réf manquantes
    warnings = []
    if req.ar_ref:
        found_refs = {str(row.get("ar_ref", "")).strip() for row in data}
        for ref in req.ar_ref:
            if ref not in found_refs:
                source_label = "les archives"
                warnings.append(f"La référence '{ref}' n'existe pas dans {source_label}.")

    return StockResponse(
        endpoint="/api/stock/compare",
        client_schema=req.client_schema,
        source=source,
        total_rows=len(data),
        columns=out_cols,
        data=data,
        metadata=metadata,
        warnings=warnings,
    )
