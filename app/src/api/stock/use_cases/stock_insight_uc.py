"""
bi/stock/use_cases/stock_insight_uc.py
"""
from api.stock.schemas import StockInsightRequest, StockResponse
from api.stock.repositories.factory_repo import get_repo
from api.stock.business_logic import alerts

def execute(req: StockInsightRequest) -> StockResponse:
    repo = get_repo("insight", req.source_type)
    raw_data = repo.fetch(req)

    
    insight_type = req.insight_type
    threshold = req.threshold or 0.0
    expiry_days = req.expiry_days or 15

    # Appliquer la logique d'alerte
    if insight_type == "expiration":
        raw_data = repo.fetch(req)
        data = alerts.detect_expiring_lots(raw_data, expiry_days)
        out_cols = ["ar_ref", "ar_design", "fa_intitule", "ls_noserie", "ls_qterestant", "ls_peremption", "jours_restants"]
    else:
        raw_data = repo.fetch(req)
        alert_map = {
            "rupture": "rupture",
            "stock_bas": "stock_bas",
            "dormant": "dormant_with_stock",
            "sommeil": "dormant_with_stock",
            "jamais_vendu": "dormant_with_stock"
        }
        data = alerts.detect_stock_alerts(raw_data, alert_map.get(insight_type, insight_type), threshold)
        if insight_type == "rupture":
            out_cols = ["ar_ref", "ar_design", "fa_intitule", "de_intitule", "suivi_lot", "derniere_date_vente", "nbr_jours_inactif"]
        else:
            out_cols = ["ar_ref", "ar_design", "fa_intitule", "quantite_totale", "derniere_date_vente", "nbr_jours_inactif"]

    metadata = {
        "insight_type": insight_type,
        "threshold": threshold if insight_type == "stock_bas" else None,
        "expiry_days": expiry_days if insight_type == "expiration" else None,
        "nb_articles_concernes": len(data),
    }

    out_cols = [c for c in out_cols if data and c in data[0]]

    # Extraire le timestamp source si présent
    source = req.source_type
    if data and "__source_timestamp__" in data[0]:
        source = f"archive:{data[0].pop('__source_timestamp__')}"
        for row in data:
            row.pop("__source_timestamp__", None)

    return StockResponse(
        endpoint="/api/stock/insights",
        client_schema=req.client_schema,
        source=source,
        total_rows=len(data),
        columns=out_cols,
        data=data,
        metadata=metadata,
        warnings=[],
    )
