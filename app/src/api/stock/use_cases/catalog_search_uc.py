"""
bi/stock/use_cases/catalog_search_uc.py
"""
import polars as pl
from api.stock.schemas import CatalogSearchRequest, StockResponse
from api.stock.repositories.factory_repo import get_repo
from api.stock.business_logic import aggregations

def execute(req: CatalogSearchRequest) -> StockResponse:
    repo = get_repo("catalog", req.source_type)
    raw_data = repo.fetch(req)

    data = aggregations.aggregate_catalog(raw_data)

    # Filtre only_available
    if req.only_available:
        data = [row for row in data if (row.get("quantite_totale", 0) or 0) > 0]

    # Tri
    sort_by = req.sort_by
    if sort_by and data:
        df = pl.DataFrame(data)
        if sort_by == "stock" and "quantite_totale" in df.columns:
            data = df.sort("quantite_totale", descending=True).to_dicts()
        elif sort_by == "price" and "ar_prixven" in df.columns:
            data = df.sort("ar_prixven", descending=True).to_dicts()
        elif sort_by == "name" and "ar_design" in df.columns:
            data = df.sort("ar_design", descending=False).to_dicts()

    metadata = {
        "total_articles": len(data),
        "only_available": req.only_available,
        "sort_by": sort_by,
    }

    out_cols = ["ar_ref", "ar_design", "fa_codefamille", "ar_type", "ar_nature",
                "ar_suivistock", "ar_prixven", "quantite_totale", "qte_par_depot"]
    out_cols = [c for c in out_cols if data and c in data[0]]

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
                source_label = "la base de données" if "db_latest" in source else "les archives"
                warnings.append(f"La référence '{ref}' n'existe pas dans {source_label}.")

    return StockResponse(
        endpoint="/api/stock/catalog",
        client_schema=req.client_schema,
        source=source,
        total_rows=len(data),
        columns=out_cols,
        data=data,
        metadata=metadata,
        warnings=warnings,
    )
