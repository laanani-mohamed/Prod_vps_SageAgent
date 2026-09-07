"""
Dash/services/stock_service.py
Service Streamlit pour le module Stock (API /api/stock/*).
"""
from __future__ import annotations
from typing import Optional
import pandas as pd

from services.base import call_api
from services.documents_service import get_documents_ligne, get_documents_entete


# --- LAYER: API ---

def get_stock_availability(
    client_schema: str,
    ar_ref: Optional[list[str]] = None,
    search_terms: Optional[list[str]] = None,
    fa_codefamille: Optional[list[str]] = None,
    with_depots: bool = False,
    by_depot: bool = False,
    only_rupture: bool = False,
    limit: int = 50
) -> dict:
    """Appelle POST /api/stock/availability"""
    payload = {
        "client_schema": client_schema,
        "with_depots": with_depots,
        "by_depot": by_depot,
        "only_rupture": only_rupture,
        "limit": limit
    }
    if ar_ref:
        payload["ar_ref"] = ar_ref
    if search_terms:
        payload["search_terms"] = search_terms
    if fa_codefamille:
        payload["fa_codefamille"] = fa_codefamille
        
    data = call_api("/api/stock/availability", payload)
    return data.get("data", [])


def get_stock_insights(client_schema: str, category: str = "rupture", limit: int = 50, expiry_days: int = 30, dormant_days: int = 90) -> list:
    """
    Appelle POST /api/stock/insights
    Mappe la catégorie de l'interface vers le insight_type attendu par l'API.
    """
    category_mapping = {
        "rupture": "rupture",
        "dormant": "dormant",
        "sommeil": "sommeil",
        "peremption": "expiration",
        "jamais_vendu": "jamais_vendu"
    }

    insight_type = category_mapping.get(category, "rupture")

    payload = {
        "client_schema": client_schema,
        "insight_type": insight_type,
        "limit": limit
    }

    # "expiration" requiert obligatoirement le paramètre "expiry_days"
    if insight_type == "expiration":
        payload["expiry_days"] = expiry_days
    elif insight_type == "dormant":
        payload["dormant_days"] = dormant_days

    data = call_api("/api/stock/insights", payload)
    return data.get("data", [])


# --- LAYER: BUSINESS ---

# Mapping des types de documents par sens de mouvement
ENTRANTS_TYPES: dict[tuple[int, int], dict] = {
    # Achat — livraisons et factures fournisseur
    (1, 13): {"label": "BL Achat",           "domaine": 1, "type": 13},
    (1, 16): {"label": "Facture Achat",       "domaine": 1, "type": 16},
    (1, 17): {"label": "Facture Achat Cpta.", "domaine": 1, "type": 17},
    # Stock — mouvement d'entrée direct
    (2, 20): {"label": "Entrée Stock",        "domaine": 2, "type": 20},
    # Vente — retour client (marchandise qui revient)
    (0,  4): {"label": "Retour Client",       "domaine": 0, "type":  4},
}

SORTANTS_TYPES: dict[tuple[int, int], dict] = {
    # Vente — livraisons et factures client
    (0,  3): {"label": "BL Vente",             "domaine": 0, "type":  3},
    (0,  6): {"label": "Facture Vente",         "domaine": 0, "type":  6},
    (0,  7): {"label": "Facture Vente Cpta.",   "domaine": 0, "type":  7},
    # Stock — mouvement de sortie direct
    (2, 21): {"label": "Sortie Stock",          "domaine": 2, "type": 21},
    # Achat — retour fournisseur (marchandise qui part)
    (1, 14): {"label": "Retour Fournisseur",    "domaine": 1, "type": 14},
}


def _label_from_row(row: pd.Series, mapping: dict) -> str:
    """Retourne le libellé du type de mouvement à partir d'une ligne."""
    d = int(row.get("do_domaine", -1) or -1)
    t = int(row.get("do_type", -1) or -1)
    return mapping.get((d, t), {}).get("label", f"Dom. {d} - Type {t}")


def _build_filters(
    domaines: list[int],
    do_types: list[int],
    ar_ref: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    tiers: Optional[str],
) -> dict:
    """Construit le dict filters pour get_documents_ligne."""
    f: dict = {
        "with_entete": True,
        "do_domaine": domaines,
        "do_type": do_types,
    }
    if ar_ref:
        f["ar_ref"] = [ar_ref]
    if date_from:
        f["date_from"] = date_from
    if date_to:
        f["date_to"] = date_to
    if tiers:
        f["do_tiers"] = [tiers]
    return f


def _process_lignes(
    lignes: list,
    type_mapping: dict,
    tiers_label: str = "Tiers",
) -> pd.DataFrame:
    """
    Transforme les lignes brutes en DataFrame propre pour l'affichage.
    Colonnes retournées :
      Date | Type | N° Pièce | Réf. Article | Désignation | Qté | PU HT | Montant HT | Tiers
    """
    if not lignes:
        return pd.DataFrame()

    df = pd.DataFrame(lignes)

    # Libellé du type de mouvement
    df["Type Mouvement"] = df.apply(lambda r: _label_from_row(r, type_mapping), axis=1)

    # Nettoyage numérique
    for col in ["dl_qte", "dl_prixunitaire", "dl_montantht"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    # Date propre
    if "do_date" in df.columns:
        df["do_date"] = df["do_date"].astype(str).str[:10]
    else:
        df["do_date"] = "-"

    # Nom du tiers (client/fournisseur/dépôt)
    if "ct_intitule" not in df.columns:
        df["ct_intitule"] = None
    if "do_tiers" in df.columns:
        df["ct_intitule"] = df["ct_intitule"].fillna(df["do_tiers"]).fillna("-")
    else:
        df["ct_intitule"] = df["ct_intitule"].fillna("-")

    rename_map = {
        "do_date":        "Date",
        "Type Mouvement": "Type",
        "do_piece":       "N° Pièce",
        "ar_ref":         "Réf. Article",
        "dl_design":      "Désignation",
        "dl_qte":         "Quantité",
        "dl_prixunitaire":"PU HT",
        "dl_montantht":   "Montant HT",
        "ct_intitule":    tiers_label,
    }

    cols_present = [c for c in rename_map.keys() if c in df.columns]
    df_out = df[cols_present].rename(columns=rename_map)
    return df_out.sort_values("Date", ascending=False).reset_index(drop=True)


def _process_entetes(docs: list) -> pd.DataFrame:
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    
    # Nettoyage
    for col in ["do_totalht", "do_totalttc"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0
            
    if "do_date" in df.columns:
        df["do_date"] = df["do_date"].astype(str).str[:10]
    else:
        df["do_date"] = "-"
        
    if "ct_intitule" not in df.columns:
        df["ct_intitule"] = None
    if "do_tiers" in df.columns:
        df["ct_intitule"] = df["ct_intitule"].fillna(df["do_tiers"]).fillna("-")
    else:
        df["ct_intitule"] = df["ct_intitule"].fillna("-")
        
    rename_map = {
        "do_date": "Date",
        "do_piece": "N° Pièce",
        "ct_intitule": "Tiers / Dépôt",
        "do_totalht": "Montant HT",
        "do_type": "Type"
    }
    
    cols_present = [c for c in rename_map.keys() if c in df.columns]
    df_out = df[cols_present].rename(columns=rename_map)
    return df_out.sort_values("Date", ascending=False).reset_index(drop=True)

def get_mouvements_entrants(
    client_schema: str,
    ar_ref: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tiers: Optional[str] = None,
    limit: int = 500,
) -> pd.DataFrame:
    """
    Récupère les entêtes ENTRANTS (domaine=2, type=21 selon instructions)
    """
    filters = {}
    if date_from: filters["date_from"] = date_from
    if date_to: filters["date_to"] = date_to
    if tiers: filters["do_tiers"] = [tiers]
    # L'utilisateur a demandé de filtrer aussi par ar_ref dans l'entête ? 
    # Non, l'entête n'a pas de ar_ref. Si on cherche un ar_ref, on cherche dans docligne.
    # Pour garder la logique sans erreur d'API : on ignore ar_ref pour la table maître des entêtes.
    
    docs = get_documents_entete(client_schema, domaine=[2], do_type=[21], limit=limit, filters=filters)
    return _process_entetes(docs)


def get_mouvements_sortants(
    client_schema: str,
    ar_ref: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tiers: Optional[str] = None,
    limit: int = 500,
) -> pd.DataFrame:
    """
    Récupère les entêtes SORTANTS (domaine=2, type=20 selon instructions)
    """
    filters = {}
    if date_from: filters["date_from"] = date_from
    if date_to: filters["date_to"] = date_to
    if tiers: filters["do_tiers"] = [tiers]
    
    docs = get_documents_entete(client_schema, domaine=[2], do_type=[20], limit=limit, filters=filters)
    return _process_entetes(docs)
