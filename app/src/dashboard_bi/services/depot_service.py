"""
Dash/services/depot_service.py
Service pour encapsuler la gestion des dépôts.
"""
from __future__ import annotations
import pandas as pd
from services.base import call_api

# --- LAYER: BUSINESS ---

def get_depots_summary(client_schema: str) -> pd.DataFrame:
    """
    Récupère la liste des dépôts avec leur numéro, nom et le nombre d'articles distincts.
    """
    payload = {"client_schema": client_schema, "limit": 5000}
    try:
        data = call_api("/api/referentiel/stock-depot", payload)
    except Exception:
        data = {}
        
    rows_api = data.get("data", [])
    
    depots_map = {}
    for row in rows_api:
        de_no = row.get("de_no")
        if de_no is None:
            continue
            
        de_intitule = row.get("de_intitule") or f"Dépôt {de_no}"
        ar_ref = row.get("ar_ref")
        
        if de_no not in depots_map:
            depots_map[de_no] = {
                "Numéro de Dépôt": de_no,
                "Nom de Dépôt": de_intitule,
                "articles": set()
            }
            
        if ar_ref:
            depots_map[de_no]["articles"].add(ar_ref)
            
    result_rows = []
    for de_no, info in depots_map.items():
        result_rows.append({
            "Numéro de Dépôt": info["Numéro de Dépôt"],
            "Nom de Dépôt": info["Nom de Dépôt"],
            "Nombre d'Articles": len(info["articles"])
        })
        
    df = pd.DataFrame(result_rows)
    if df.empty:
        return pd.DataFrame(columns=["Numéro de Dépôt", "Nom de Dépôt", "Nombre d'Articles"])
        
    return df.sort_values(by="Numéro de Dépôt")
