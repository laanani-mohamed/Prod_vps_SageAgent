"""
Dash/services/reglements_service.py
Service pour encapsuler le traitement et formatage des règlements.
"""
from __future__ import annotations
from typing import Optional
import pandas as pd

from services.base import call_api
from core.constants import TYPE_REGLEMENT_LABEL

# --- LAYER: API ---

def get_reglements_data(
    client_schema: str,
    domaine: list[int],
    do_type: Optional[list[int]] = None,
    limit: int = 100000000,
    filters: Optional[dict] = None
) -> list:
    """Récupère les règlements (F_REGLECH) enrichis depuis l'API."""
    payload = {
        "client_schema": client_schema,
        "do_domaine": domaine,
        "limit": limit
    }
    if do_type is not None:
        payload["do_type"] = do_type
    if filters:
        payload.update(filters)
        
    data = call_api("/api/referentiel/reglements", payload)
    return data.get("data", [])

# --- LAYER: BUSINESS ---

def get_formatted_reglements(
    client_schema: str,
    domaine: int,  # 0 = Ventes (Encaissem. Clients), 1 = Achats (Decaissem. Fournisseurs)
    limit: int = 100000000,
    search_piece: str = "",
    search_tiers: str = "",
    search_intitule: str = "",
    date_from: str = None,
    date_to: str = None,
    rg_typereg: list[int] = None,
    do_type: list[int] = None
) -> pd.DataFrame:
    """Récupère et formate les règlements clients ou fournisseurs."""
    api_filters = {}
    if search_piece:
        api_filters["do_piece"] = [search_piece]
    if rg_typereg:
        api_filters["rg_typereg"] = rg_typereg
    if date_from:
        api_filters["date_from"] = date_from
    if date_to:
        api_filters["date_to"] = date_to

    # Appel de l'API règlements
    data = get_reglements_data(
        client_schema=client_schema,
        domaine=[domaine],
        do_type=do_type,
        limit=limit,
        filters=api_filters
    )

    code_label = "CODE CLIENT" if domaine == 0 else "CODE FOURNISSEUR"
    intitule_label = "RAISON SOCIALE"
    
    cols_order = [
        "REF REGLEMENT", "N PIECE", "DATE OPERATION", code_label,
        intitule_label, "ICE", "TYPE REGLEMENT", "MONTANT"
    ]
    
    if not data:
        return pd.DataFrame(columns=cols_order)

    df = pd.DataFrame(data)

    # Filtrage manuel pour les champs non pris en charge par l'API
    if search_tiers and "do_tiers" in df.columns:
        df = df[df["do_tiers"].astype(str).str.contains(search_tiers, case=False, na=False)]
    if search_intitule and "ct_intitule" in df.columns:
        df = df[df["ct_intitule"].astype(str).str.contains(search_intitule, case=False, na=False)]

    if df.empty:
        return pd.DataFrame(columns=cols_order)

    # 1. Nettoyer et formater la date
    if "do_date" in df.columns:
        df["DATE OPERATION"] = df["do_date"].astype(str).str.split(" ").str[0]
    else:
        df["DATE OPERATION"] = "-"

    # 2. Nettoyer et formater le type de règlement
    if "rg_typereg" in df.columns:
        df["TYPE REGLEMENT"] = pd.to_numeric(df["rg_typereg"], errors="coerce").fillna(0).astype(int).map(TYPE_REGLEMENT_LABEL).fillna("Autre")
    else:
        df["TYPE REGLEMENT"] = "Règlement"

    # 3. Nettoyer et formater le montant
    if "rc_montant" in df.columns:
        df["MONTANT"] = pd.to_numeric(df["rc_montant"], errors="coerce").fillna(0.0)
    else:
        df["MONTANT"] = 0.0

    # 4. Formater l'ICE (supprimer le préfixe "ICE : " si présent pour plus de propreté)
    if "ct_identifiant" in df.columns:
        df["ICE"] = df["ct_identifiant"].astype(str).str.replace("ICE : ", "", case=False).str.strip()
    else:
        df["ICE"] = "-"

    # Renommages restants
    rename_map = {
        "rg_no": "REF REGLEMENT",
        "do_piece": "N PIECE",
        "do_tiers": code_label,
        "ct_intitule": intitule_label,
    }

    for col, new_col in rename_map.items():
        if col in df.columns:
            df[new_col] = df[col]
        else:
            df[new_col] = "-"

    # S'assurer que toutes les colonnes cibles existent
    for col in cols_order:
        if col not in df.columns:
            df[col] = "-"

    return df[cols_order]
