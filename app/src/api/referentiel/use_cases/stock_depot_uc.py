"""
bi/referentiel/use_cases/stock_depot_uc.py
"""
from api.referentiel.schemas import StockDepotRequest, ReferentielResponse
from api.referentiel.repositories.factory_repo import get_repo
from api.referentiel.business_logic import serializers, enrichments

def execute(req: StockDepotRequest) -> ReferentielResponse:
    repo = get_repo("stock_depot", req.source_type)
    raw_data = repo.fetch(req)
    
    source = req.source_type
    if raw_data and "__source_timestamp__" in raw_data[0]:
        source = f"archive:{raw_data[0].pop('__source_timestamp__')}"
        for row in raw_data:
            row.pop("__source_timestamp__", None)

    if req.source_type == "archive":
        raw_data = enrichments.add_valeur_stock(raw_data)

    data = serializers.serialize_rows(raw_data)

    return ReferentielResponse(
        endpoint="/api/referentiel/stock-depot",
        client_schema=req.client_schema,
        source=source,
        message=None if data else "stock introuvable",
        total_rows=len(data),
        data=data,
    )
