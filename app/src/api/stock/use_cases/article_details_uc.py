"""
bi/stock/use_cases/article_details_uc.py
"""
import polars as pl
from api.stock.schemas import ArticleDetailsRequest, StockResponse
from api.stock.repositories.factory_repo import get_repo
from api.stock.business_logic import aggregations

def execute(req: ArticleDetailsRequest) -> StockResponse:
    repo = get_repo("details", req.source_type)
    res = repo.fetch(req)
    raw_data = res["raw_stock"]
    lots_data = res["lots_data"]

    # Filtrer par design s'il est fourni (Polars)
    if req.ar_design and not req.ar_ref and raw_data:
        df = pl.DataFrame(raw_data)
        if "ar_design" in df.columns:
            raw_data = df.filter(pl.col("ar_design").str.contains(f"(?i){req.ar_design}")).to_dicts()
            # Filtrer les lots de même
            found_refs = {row.get("ar_ref") for row in raw_data}
            lots_data = [l for l in lots_data if l.get("ar_ref") in found_refs]

    # Construire la fiche
    data = aggregations.build_article_detail(raw_data, lots_data)

    metadata = {
        "nb_articles": len({row.get("ar_ref") for row in raw_data}),
        "avec_lots": bool(lots_data),
    }

    out_cols = list(data[0].keys()) if data else []
    
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
        endpoint="/api/stock/details",
        client_schema=req.client_schema,
        source=source,
        total_rows=len(data),
        columns=out_cols,
        data=data,
        metadata=metadata,
        warnings=warnings,
    )
