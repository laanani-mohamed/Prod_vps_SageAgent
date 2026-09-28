"""
api/referentiel/use_cases/date_range_uc.py
"""
from api.referentiel.schemas import DateRangeRequest, ReferentielResponse
from api.referentiel.repositories.factory_repo import get_repo


def execute(req: DateRangeRequest) -> ReferentielResponse:
    rows = get_repo("date_range", req.source_type).fetch(req)
    row = dict(rows[0]) if rows else {"date_min": None, "date_max": None}

    source = req.source_type
    ts = row.pop("__source_timestamp__", None)
    if ts:
        source = f"archive:{ts}"

    data = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()}
    return ReferentielResponse(
        endpoint="/api/referentiel/date-range",
        client_schema=req.client_schema,
        source=source,
        message=None if data.get("date_min") else "aucune date trouvée",
        total_rows=1,
        data=[data],
    )
