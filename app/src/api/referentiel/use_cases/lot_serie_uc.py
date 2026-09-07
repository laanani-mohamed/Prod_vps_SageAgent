"""
bi/referentiel/use_cases/lot_serie_uc.py
"""
from api.referentiel.schemas import LotSerieRequest, ReferentielResponse
from api.referentiel.repositories.factory_repo import get_repo
from api.referentiel.business_logic import serializers, enrichments

def execute(req: LotSerieRequest) -> ReferentielResponse:
    repo = get_repo("lot_serie", req.source_type)
    raw_data = repo.fetch(req)
    
    source = req.source_type
    if raw_data and "__source_timestamp__" in raw_data[0]:
        source = f"archive:{raw_data[0].pop('__source_timestamp__')}"
        for row in raw_data:
            row.pop("__source_timestamp__", None)

    # Calcul jours_avant_peremption si c'est DB_LATEST car dans l'archive ça n'a pas été fait
    # Sauf que pour DB_LATEST on l'a fait en SQL. Pour Archive on ne l'a pas fait.
    # Donc on le fait toujours ici en Python, c'est plus simple (si absent ou à écraser).
    if req.source_type == "archive":
        raw_data = enrichments.add_jours_avant_peremption(raw_data)

    data = serializers.serialize_rows(raw_data)

    return ReferentielResponse(
        endpoint="/api/referentiel/lots-series",
        client_schema=req.client_schema,
        source=source,
        message=None if data else "lot/série introuvable",
        total_rows=len(data),
        data=data,
    )
