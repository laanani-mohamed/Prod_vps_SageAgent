"""
Dash/services/documents_service.py
Service Streamlit pour le module Documents (Ventes, Achats, etc.)
"""
from __future__ import annotations
from typing import Optional
import pandas as pd

from services.base import call_api
from config import SOURCE_TYPE


# --- LAYER: API ---

def get_documents_entete(
    client_schema: str,
    domaine: list[int],
    do_type: Optional[list[int]] = None,
    limit: int = 100000000,
    filters: Optional[dict] = None
) -> list:
    """Récupère les entêtes de documents (F_DOCENTETE)."""
    payload = {
        "client_schema": client_schema,
        "do_domaine": domaine,
        "limit": limit
    }
    if do_type is not None:
        payload["do_type"] = do_type
    if filters:
        payload.update(filters)
        
    data = call_api("/api/referentiel/documents-entete", payload)
    return data.get("data", [])

def get_documents_ligne(
    client_schema: str,
    do_piece: Optional[str] = None,
    limit: int = 100000000,
    filters: Optional[dict] = None
) -> list:
    """Récupère les lignes (détails) d'un document ou d'un article (F_DOCLIGNE)."""
    payload = {
        "client_schema": client_schema,
        "limit": limit
    }
    if do_piece:
        payload["do_piece"] = [do_piece]
    if filters:
        payload.update(filters)
        
    data = call_api("/api/referentiel/documents-ligne", payload)
    return data.get("data", [])


# --- LAYER: BUSINESS ---

def get_formatted_documents(
    client_schema: str,
    domaine: int,  # 0 = Ventes, 1 = Achats
    category: str, # "general", "devis", "bon_commande", "prep_livraison", "bon_livraison", "bon_retour", "bon_avoir", "facture", "facture_comptab", "archive"
    limit: int = 100000000,
    search_piece: str = "",
    search_tiers: str = "",
    search_intitule: str = "",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    unpaid_only: bool = False
) -> pd.DataFrame:
    """
    Récupère et formate les documents de vente ou d'achat.
    Filtre par do_type en mode live ou par préfixe de do_piece en mode archive.
    """
    # Configuration des do_type par catégorie
    category_map = {
        0: {
            "devis": [0],
            "bon_commande": [1],
            "prep_livraison": [2],
            "bon_livraison": [3],
            "bon_retour": [4],
            "bon_avoir": [5],
            "facture": [6],
            "facture_comptab": [7],
            "archive": [8]
        },
        1: {
            "demande_achat": [10],
            "prep_commande": [11],
            "bon_commande": [12],
            "bon_livraison": [13],
            "bon_retour": [14],
            "bon_avoir": [15],
            "facture": [16],
            "facture_comptab": [17],
            "archive": [18]
        }
    }

    api_filters = {}
    if search_piece:
        api_filters["do_piece"] = [search_piece]
    if search_tiers:
        api_filters["do_tiers"] = [search_tiers]
    if unpaid_only:
        api_filters["montant_regle_unpaid"] = True

    # Si on est en mode live/database, on peut passer do_type en filtre à l'API pour limiter la requête
    do_type_api = None
    if SOURCE_TYPE != "archive":
        if category in category_map[domaine]:
            do_type_api = category_map[domaine][category]
        elif category == "general":
            do_type_api = list(range(0, 9)) if domaine == 0 else list(range(10, 19))

    # Appel de l'API entêtes
    limit_api = limit
    docs = get_documents_entete(
        client_schema,
        domaine=[domaine],
        do_type=do_type_api,
        limit=limit_api,
        filters=api_filters
    )
    
    code_label = "CLIENT CODE" if domaine == 0 else "FOURNISSEUR CODE"
    intitule_label = "CLIENT INTITULE" if domaine == 0 else "FOURNISSEUR INTITULE"
    
    cols_order = [
        "N PIECE", "DATE PIECE", code_label, intitule_label,
        "MONTANT HT", "MONTANT TVA", "MONTANT TTC", "RESTE A PAYER"
    ]
    
    if not docs:
        return pd.DataFrame(columns=cols_order)
    df = pd.DataFrame(docs)

    # Convertir do_type en numérique pour pouvoir comparer
    if "do_type" in df.columns:
        df["do_type_num"] = pd.to_numeric(df["do_type"], errors="coerce").fillna(0).astype(int)
    else:
        df["do_type_num"] = 0

    if "do_date" in df.columns:
        df["do_date_str"] = df["do_date"].astype(str).str.split(" ").str[0]
    else:
        df["do_date_str"] = "-"

    # Filtrer par catégorie de document
    if category in category_map[domaine]:
        df = df[df["do_type_num"].isin(category_map[domaine][category])]
    elif category != "general":
        df = df.head(0)

    # Filtrer par intitulé
    if search_intitule and not df.empty and "ct_intitule" in df.columns:
        df = df[df["ct_intitule"].astype(str).str.contains(search_intitule, case=False, na=False)]

    # Filtrer par date
    if date_from and not df.empty:
        df = df[df["do_date_str"] >= str(date_from)]
    if date_to and not df.empty:
        df = df[df["do_date_str"] <= str(date_to)]

    if df.empty:
        return pd.DataFrame(columns=cols_order)
    # Pas de limite après filtrage

    # Convertir les champs financiers en numérique
    for col in ["do_totalht", "do_totalttc", "do_montantregle"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    # 1. Calcul du montant TVA
    df["MONTANT TVA"] = df["do_totalttc"] - df["do_totalht"]

    # 2. Calcul du Reste à payer
    df["RESTE A PAYER"] = df["do_totalttc"] - df["do_montantregle"]

    # 3. Formater la date (garder uniquement YYYY-MM-DD)
    if "do_date_str" in df.columns:
        df["do_date"] = df["do_date_str"]
    elif "do_date" in df.columns:
        df["do_date"] = df["do_date"].astype(str).str.split(" ").str[0]
    else:
        df["do_date"] = "-"

    # Renommer les colonnes
    rename_map = {
        "do_piece": "N PIECE",
        "do_date": "DATE PIECE",
        "do_tiers": code_label,
        "ct_intitule": intitule_label,
        "do_totalht": "MONTANT HT",
        "MONTANT TVA": "MONTANT TVA",
        "do_totalttc": "MONTANT TTC",
        "RESTE A PAYER": "RESTE A PAYER"
    }

    # S'assurer que toutes les colonnes existent
    for col in rename_map.keys():
        if col not in df.columns:
            df[col] = "-"

    # Réorganiser et renommer
    df_result = df[list(rename_map.keys())].rename(columns=rename_map)
    return df_result
