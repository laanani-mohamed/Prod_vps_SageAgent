"""
Dash/services/sales_service.py
Service pour encapsuler la gestion des ventes.
"""
from __future__ import annotations
import pandas as pd
from services.documents_service import get_documents_entete

# --- LAYER: BUSINESS ---

def get_sales_documents(
    client_schema: str,
    do_types: list[int],
    limit: int = 50,
    search_piece: str = "",
    search_tiers: str = "",
    unpaid_only: bool = False
) -> pd.DataFrame:
    """
    Récupère et formate les documents de vente (domaine=0) pour les types spécifiés.
    """
    filters = {}
    if search_piece:
        filters["do_piece"] = [search_piece]
    if search_tiers:
        filters["do_tiers"] = [search_tiers]
    if unpaid_only:
        filters["montant_regle_unpaid"] = True

    docs = get_documents_entete(
        client_schema,
        domaine=[0],
        do_type=do_types,
        limit=limit,
        filters=filters
    )
    if not docs:
        return pd.DataFrame(columns=[
            "N PIECE", "DATE PIECE", "CLIENT CODE", "CLIENT INTITULE",
            "MONTANT HT", "MONTANT TVA", "MONTANT TTC", "RESTE A PAYER"
        ])

    df = pd.DataFrame(docs)

    for col in ["do_totalht", "do_totalttc", "do_montantregle"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    df["MONTANT TVA"] = df["do_totalttc"] - df["do_totalht"]
    df["RESTE A PAYER"] = df["do_totalttc"] - df["do_montantregle"]

    if "do_date" in df.columns:
        df["do_date"] = df["do_date"].astype(str).str.split(" ").str[0]
    else:
        df["do_date"] = "-"

    rename_map = {
        "do_piece": "N PIECE",
        "do_date": "DATE PIECE",
        "do_tiers": "CLIENT CODE",
        "ct_intitule": "CLIENT INTITULE",
        "do_totalht": "MONTANT HT",
        "MONTANT TVA": "MONTANT TVA",
        "do_totalttc": "MONTANT TTC",
        "RESTE A PAYER": "RESTE A PAYER"
    }

    for col in rename_map.keys():
        if col not in df.columns:
            df[col] = "-"

    df_result = df[list(rename_map.keys())].rename(columns=rename_map)
    return df_result


def Ventes(client_schema: str, date_from: str, date_to: str) -> float:
    filters = {
        "date_from": date_from,
        "date_to": date_to
    }
    
    ventes = get_documents_entete(client_schema, domaine=[0], limit=5000, filters=filters)
    total_ventes = 0.0
    if ventes:
        
        for doc in ventes:
            dtype = doc.get("do_type")
            try:
                dtype_int = int(dtype) if dtype is not None else 0
            except ValueError:
                dtype_int = 0
                
    return total_ventes


def Achats(client_schema: str, date_from: str, date_to: str) -> float:               
    filters = {
        "date_from": date_from,
        "date_to": date_to
    }
    achats = get_documents_entete(client_schema, domaine=[1], limit=5000, filters=filters)
    total_achats = 0.0
    if achats:
        for doc in achats:
            dtype = doc.get("do_type")
            try:
                dtype_int = int(dtype) if dtype is not None else 0
            except ValueError:
                dtype_int = 0
                
                
    return total_achats


def Chiffre_affaire_net(client_schema: str, date_from: str, date_to: str) -> float:
    filters = {
        "date_from": date_from,
        "date_to": date_to
    }
    ventes = Ventes(client_schema, date_from, date_to)
    achats = Achats(client_schema, date_from, date_to)
    return ventes - achats


def get_monthly_sales_and_profit(client_schema: str, date_from: str, date_to: str) -> tuple[list[dict], list[dict]]:
    """
    Récupère et regroupe les ventes et achats par mois pour la période sélectionnée.
    """
    filters = {
        "date_from": date_from,
        "date_to": date_to
    }
    
    ventes_docs = get_documents_entete(client_schema, domaine=[0], limit=5000, filters=filters)
    achats_docs = get_documents_entete(client_schema, domaine=[1], limit=5000, filters=filters)
    
    sales_by_month = {}
    if ventes_docs:
        for doc in ventes_docs:
            dtype = doc.get("do_type")
            try:
                dtype_int = int(dtype) if dtype is not None else 0
            except ValueError:
                dtype_int = 0
                
            if dtype_int in [6]:
                do_date = doc.get("do_date")
                if do_date:
                    mois = str(do_date)[:7]
                    amount = float(doc.get("do_totalht") or 0.0)
                    sales_by_month[mois] = sales_by_month.get(mois, 0.0) + amount

    achats_by_month = {}
    if achats_docs:
        for doc in achats_docs:
            dtype = doc.get("do_type")
            try:
                dtype_int = int(dtype) if dtype is not None else 0
            except ValueError:
                dtype_int = 0
                
            if dtype_int in [16, 17]:
                do_date = doc.get("do_date")
                if do_date:
                    mois = str(do_date)[:7]
                    amount = float(doc.get("do_totalht") or 0.0)
                    achats_by_month[mois] = achats_by_month.get(mois, 0.0) + amount

    all_months = sorted(list(set(sales_by_month.keys()) | set(achats_by_month.keys())))
    
    MONTH_NAMES_FR = {
        "01": "Janvier", "02": "Février", "03": "Mars", "04": "Avril",
        "05": "Mai", "06": "Juin", "07": "Juillet", "08": "Août",
        "09": "Septembre", "10": "Octobre", "11": "Novembre", "12": "Décembre"
    }
    sales_monthly = []
    profit_monthly = []
    for m in all_months:
        v = sales_by_month.get(m, 0.0)
        a = achats_by_month.get(m, 0.0)
        p = v - a
        m_code = m[5:7]
        m_label = MONTH_NAMES_FR.get(m_code, m_code)
        sales_monthly.append({"mois": m_label, "value": v})
        profit_monthly.append({"mois": m_label, "value": p})
    return sales_monthly, profit_monthly


def Valeur_stock(client_schema: str) -> float:
    """Calcul de la valorisation totale du stock."""
    from services.referentiel_service import get_articles
    articles = get_articles(client_schema, limit=5000, filters={"with_stock": True})
    total_val = 0.0
    for art in articles:
        qte = float(art.get("qte_stock_totale") or 0.0)
        prix = float(art.get("ar_prixach") or 0.0)
        total_val += qte * prix
    return total_val


def Encours_clients(client_schema: str, date_from: str, date_to: str) -> float:
    """Calcul de l'encours client total sur la période."""
    filters = {
        "date_from": date_from,
        "date_to": date_to
    }
    ventes = get_documents_entete(client_schema, domaine=[0], limit=5000, filters=filters)
    total_encours = 0.0
    if ventes:
        for doc in ventes:
            dtype = doc.get("do_type")
            try:
                dtype_int = int(dtype) if dtype is not None else 0
            except ValueError:
                dtype_int = 0
                
            if dtype_int in [6]:
                ttc = float(doc.get("do_totalttc") or 0.0)
                regle = float(doc.get("do_montantregle") or 0.0)
                reste = ttc - regle
                if reste > 0:
                    total_encours += reste
    return total_encours


def Clients_actifs(client_schema: str, date_from: str, date_to: str) -> int:
    """Calcul du nombre de clients uniques actifs."""
    filters = {
        "date_from": date_from,
        "date_to": date_to
    }
    ventes = get_documents_entete(client_schema, domaine=[0], limit=5000, filters=filters)
    active_tiers = set()
    if ventes:
        for doc in ventes:
            dtype = doc.get("do_type")
            try:
                dtype_int = int(dtype) if dtype is not None else 0
            except ValueError:
                dtype_int = 0
                
            if dtype_int in [6]:
                tiers = doc.get("do_tiers")
                if tiers:
                    active_tiers.add(tiers)
    return len(active_tiers)
