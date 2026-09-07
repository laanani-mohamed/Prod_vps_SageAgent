"""
Dash/services/bi_service.py
Couche service Streamlit pour le module BI — appels API /api/bi/*.
"""
from typing import Optional, List, Dict
import streamlit as st

from services.base import call_api, call_api_get
from utils.cache import cache_data


# --- LAYER: API ---

@cache_data(ttl=300)
def get_dashboard_kpis(
    client_schema: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Appelle POST /api/bi/dashboard et retourne les KPIs."""
    payload = {"client_schema": client_schema}
    if date_from:
        payload["date_from"] = date_from
    if date_to:
        payload["date_to"] = date_to
    return call_api("/api/bi/dashboard", payload)

@cache_data(ttl=300)
def get_dashboard_objectifs(client_schema: str) -> list:
    """Appelle GET /api/bi/dashboard/objectifs et retourne la liste."""
    data = call_api_get("/api/bi/dashboard/objectifs", {"client_schema": client_schema})
    return data.get("objectifs", [])

@cache_data(ttl=300)
def get_dashboard_analytique(client_schema: str, date_from: str, date_to: str) -> dict:
    """Appelle GET /api/bi/dashboard/analytique et retourne tous les KPIs analytiques."""
    return call_api_get(
        "/api/bi/dashboard/analytique",
        {"client_schema": client_schema, "date_from": date_from, "date_to": date_to},
    )

def get_rapport_ca(
    client_schema: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group_by: str = "mois",
) -> list:
    """Appelle POST /api/bi/rapport/ca."""
    payload = {"client_schema": client_schema, "group_by": group_by}
    if date_from:
        payload["date_from"] = date_from
    if date_to:
        payload["date_to"] = date_to
    data = call_api("/api/bi/rapport/ca", payload)
    return data.get("data", [])

@cache_data(ttl=300)
def get_top_clients(
    client_schema: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100000000,
) -> list:
    """Appelle POST /api/bi/top-clients."""
    payload = {"client_schema": client_schema, "limit": limit}
    if date_from:
        payload["date_from"] = date_from
    if date_to:
        payload["date_to"] = date_to
    data = call_api("/api/bi/top-clients", payload)
    return data.get("data", [])

# --- LAYER: BUSINESS ---
