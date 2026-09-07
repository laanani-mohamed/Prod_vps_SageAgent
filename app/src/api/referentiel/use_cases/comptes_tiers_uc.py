"""
bi/referentiel/use_cases/comptes_tiers_uc.py
"""
from api.referentiel.schemas import ComptesTiersRequest, ReferentielResponse
from api.referentiel.repositories.factory_repo import get_repo
from api.referentiel.business_logic import serializers

def execute(req: ComptesTiersRequest) -> ReferentielResponse:
    repo = get_repo("comptes_tiers", req.source_type)
    raw_data = repo.fetch(req)
    
    # Extract timestamp if archive
    source = req.source_type
    if raw_data and "__source_timestamp__" in raw_data[0]:
        source = f"archive:{raw_data[0].pop('__source_timestamp__')}"
        for row in raw_data:
            row.pop("__source_timestamp__", None)

    data = serializers.serialize_rows(raw_data)

    return ReferentielResponse(
        endpoint="/api/referentiel/comptes-tiers",
        client_schema=req.client_schema,
        source=source,
        message=None if data else "compte tiers introuvable",
        total_rows=len(data),
        data=data,
    )
