"""
Dash/services/referentiel_service.py
Service Streamlit pour le module Référentiel.
"""
from __future__ import annotations
from typing import Optional
from services.base import call_api


# --- LAYER: API ---

def get_articles(client_schema: str, limit: int = 100000000, filters: Optional[dict] = None) -> list:
    payload = {"client_schema": client_schema, "limit": limit}
    if filters:
        payload.update(filters)
    data = call_api("/api/referentiel/articles/detail", payload)
    return data.get("data", [])


def get_comptes_tiers(client_schema: str, limit: int = 100000000, filters: Optional[dict] = None) -> list:
    payload = {"client_schema": client_schema, "limit": limit}
    if filters:
        payload.update(filters)
    data = call_api("/api/referentiel/comptes-tiers", payload)
    return data.get("data", [])


def get_depots(client_schema: str, limit: int = 100000000) -> list:
    # On utilise stock-depot pour récupérer les dépôts
    payload = {"client_schema": client_schema, "limit": limit}
    data = call_api("/api/referentiel/stock-depot", payload)
    # Groupement par dépôt (de_no, de_intitule)
    depots = {}
    for row in data.get("data", []):
        de_no = row.get("de_no")
        if de_no not in depots:
            depots[de_no] = {
                "Dépôt N°": de_no,
                "Intitulé": row.get("de_intitule", f"Dépôt {de_no}"),
                "Qté Stock": 0,
                "Valeur Achat": 0,
            }
        try:
            qte = float(row.get("as_qtesto") or 0)
        except Exception:
            qte = 0.0
        try:
            val = float(row.get("valeur_stock_achat") or 0)
        except Exception:
            val = 0.0

        depots[de_no]["Qté Stock"] += qte
        depots[de_no]["Valeur Achat"] += val
    return list(depots.values())


def get_familles(client_schema: str, limit: int = 100000000, filters: Optional[dict] = None) -> list:
    payload = {"client_schema": client_schema, "limit": limit, "with_articles_count": True}
    if filters:
        payload.update(filters)
    data = call_api("/api/referentiel/familles", payload)
    return data.get("data", [])


def get_lots_series(client_schema: str, limit: int = 100000000, filters: Optional[dict] = None) -> list:
    payload = {"client_schema": client_schema, "limit": limit}
    if filters:
        payload.update(filters)
    data = call_api("/api/referentiel/lots-series", payload)
    return data.get("data", [])


def get_collaborateurs(client_schema: str, limit: int = 100000000, filters: Optional[dict] = None) -> list:
    payload = {"client_schema": client_schema, "limit": limit}
    if filters:
        payload.update(filters)
    data = call_api("/api/referentiel/collaborateurs", payload)
    return data.get("data", [])
