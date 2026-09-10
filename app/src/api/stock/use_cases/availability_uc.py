"""
bi/stock/use_cases/availability_uc.py
"""
import polars as pl
from api.stock.schemas import CheckAvailabilityRequest, StockResponse
from api.stock.repositories.factory_repo import get_repo
from api.stock.business_logic import aggregations, valuations
from api.stock.business_logic.source_meta import extract_source_and_warnings

def execute(req: CheckAvailabilityRequest) -> StockResponse:
    repo = get_repo("availability", req.source_type)
    raw_data = repo.fetch(req)

    # Filtrer par search_terms s'ils sont fournis (Polars)
    terms = req.search_terms or []
    if terms and raw_data:
        df = pl.DataFrame(raw_data)
        if "ar_design" in df.columns:
            expr = pl.lit(False)
            for t in terms:
                expr = expr | pl.col("ar_design").str.contains(f"(?i){t}")
            raw_data = df.filter(expr).to_dicts()

    by_depot = req.by_depot
    if by_depot:
        data = aggregations.aggregate_by_depot(raw_data)
    else:
        data = aggregations.aggregate_availability(raw_data)

    if req.with_financials and data:
        data = valuations.add_unit_financials(data)

    total_qty = sum(row.get("quantite_totale", 0) or 0 for row in data)
    nb_dispo  = sum(1 for row in data if (row.get("quantite_totale", 0) or 0) > 0)

    metadata = {
        "quantite_totale_globale": total_qty,
        "nb_articles_disponibles": nb_dispo,
        "nb_articles_indisponibles": len(data) - nb_dispo,
    }

    # Colonnes de sortie
    base_cols = ["ar_ref", "ar_design", "quantite_totale", "ar_prixven", "qte_par_depot", "fa_codefamille"]
    if req.with_financials:
        base_cols += ["ar_prixach", "marge_unitaire", "marge_taux"]
    if by_depot:
        base_cols += ["de_intitule", "quantite_depot"]

    out_cols = [c for c in base_cols if data and c in data[0]]

    source, warnings = extract_source_and_warnings(data, req)

    return StockResponse(
        endpoint="/api/stock/availability",
        client_schema=req.client_schema,
        source=source,
        total_rows=len(data),
        columns=out_cols,
        data=data,
        metadata=metadata,
        warnings=warnings,
    )
