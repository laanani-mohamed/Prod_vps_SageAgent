"""
Dash/services/tiers_service.py
Service pour encapsuler la recherche et le traitement des comptes tiers.
"""
from __future__ import annotations
import pandas as pd
from services.referentiel_service import get_comptes_tiers

# --- LAYER: BUSINESS ---

def search_comptes_tiers(
    client_schema: str,
    search_term: str = "",
    search_ref: str = "",
    type_filter: str = "Tous",
    limit: int = 100000000
) -> pd.DataFrame:
    """
    Recherche les comptes tiers par nom (ct_intitule) ou par type (Client, Fournisseur).
    Retourne un DataFrame formaté avec les colonnes demandées :
    CODE CLIENT, RAISON SOCIALE, ICE, VILLE
    """
    filters = {}
    
    if search_term:
        filters["ct_intitule"] = search_term
        
    if search_ref:
        filters["ct_num"] = [search_ref]
        
    if type_filter == "Clients":
        filters["ct_type"] = [0]
    elif type_filter == "Fournisseurs":
        filters["ct_type"] = [1]
    else:
        filters["ct_type"] = [0, 1]

    tiers_list = get_comptes_tiers(client_schema, limit=limit, filters=filters)
    if not tiers_list:
        return pd.DataFrame(columns=["CODE CLIENT", "RAISON SOCIALE", "ICE", "VILLE"])

    df = pd.DataFrame(tiers_list)
    
    rename_map = {
        "ct_num": "CODE CLIENT",
        "ct_intitule": "RAISON SOCIALE",
        "ice": "ICE",
        "ct_ville": "VILLE"
    }
    
    for col in rename_map.keys():
        if col not in df.columns:
            df[col] = "-"

    df_result = df[list(rename_map.keys())].rename(columns=rename_map)
    return df_result
