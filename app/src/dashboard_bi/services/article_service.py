"""
Dash/services/article_service.py
Service pour encapsuler les calculs et analyses spécifiques aux articles.
"""
from __future__ import annotations
import pandas as pd
from services.documents_service import get_documents_ligne
from services.stock_service import get_stock_availability

# --- LAYER: BUSINESS ---

def get_article_top_clients(client_schema: str, ar_ref: str, limit: int = 10) -> pd.DataFrame:
    """
    Calcule le Top 10 des clients pour un article donné.
    Retourne uniquement le Nom Client, la Quantité, et un index (N°) de 1 à limit.
    """
    lignes_art = get_documents_ligne(
        client_schema, 
        limit=5000, 
        filters={"ar_ref": [ar_ref], "with_entete": True}
    )
    if not lignes_art:
        return pd.DataFrame()
        
    df_l = pd.DataFrame(lignes_art)
    if "do_domaine" in df_l.columns:
        df_l = df_l[df_l["do_domaine"].astype(str) == "0"]
        
    if df_l.empty:
        return pd.DataFrame()

    if "dl_qte" not in df_l.columns:
        df_l["dl_qte"] = 0
    df_l["dl_qte"] = pd.to_numeric(df_l["dl_qte"], errors="coerce").fillna(0)
    
    if "dl_montantht" not in df_l.columns:
        df_l["dl_montantht"] = 0
    df_l["dl_montantht"] = pd.to_numeric(df_l["dl_montantht"], errors="coerce").fillna(0)
    
    if "ct_intitule" not in df_l.columns:
        df_l["ct_intitule"] = None
        
    if "ct_num" in df_l.columns:
        df_l["ct_intitule"] = df_l["ct_intitule"].fillna(df_l["ct_num"]).fillna("Client Inconnu")
    else:
        df_l["ct_intitule"] = df_l["ct_intitule"].fillna("Client Inconnu")
        
    top_c = df_l.groupby("ct_intitule").agg(
        Quantité=("dl_qte", "sum"),
        CA_HT=("dl_montantht", "sum")
    ).reset_index()
    top_c = top_c.rename(columns={"ct_intitule": "Nom Client"})
    
    top_c = top_c.sort_values(by="CA_HT", ascending=False).head(limit)
    
    if not top_c.empty:
        top_c.insert(0, "N°", range(1, len(top_c) + 1))
        
    return top_c[["N°", "Nom Client", "Quantité", "CA_HT"]].rename(columns={"CA_HT": "CA HT (DH)"})


def get_article_stock_depots(client_schema: str, ar_ref: str) -> pd.DataFrame:
    """
    Récupère la répartition du stock par dépôt et par lot pour un article.
    Combine les informations de stock par dépôt avec les lots/séries.
    """
    from services.referentiel_service import get_lots_series
    
    stock_det = get_stock_availability(client_schema, ar_ref=[ar_ref], with_depots=True)
    qte_par_depot = {}
    if stock_det:
        qte_par_depot = stock_det[0].get("qte_par_depot", {})

    try:
        lots = get_lots_series(client_schema, limit=1000, filters={"ar_ref": [ar_ref]})
    except Exception:
        lots = []

    rows = []
    lots_qte_by_depot = {}
    
    for lot in lots:
        depot = lot.get("de_intitule")
        if not depot and lot.get("de_no") is not None:
            depot = f"Dépôt {lot.get('de_no')}"
        elif not depot:
            depot = "Dépôt principal"
            
        lot_no = lot.get("ls_noserie") or "-"
        
        try:
            qte_rest = float(lot.get("ls_qterestant") or lot.get("ls_qte") or 0.0)
        except Exception:
            qte_rest = 0.0
            
        peremption = lot.get("ls_peremption") or "-"
        
        lots_qte_by_depot[depot] = lots_qte_by_depot.get(depot, 0.0) + qte_rest
        
        rows.append({
            "Dépôt": depot,
            "Lot / N° Série": lot_no,
            "Quantité": qte_rest,
            "Péremption": peremption
        })
        
    for depot, total_qte in qte_par_depot.items():
        try:
            tot_q = float(total_qte or 0.0)
        except Exception:
            tot_q = 0.0
            
        qte_lots_somme = lots_qte_by_depot.get(depot, 0.0)
        diff = tot_q - qte_lots_somme
        
        if diff > 0.01 or (depot not in lots_qte_by_depot and not lots):
            q_sans = diff if depot in lots_qte_by_depot else tot_q
            rows.append({
                "Dépôt": depot,
                "Lot / N° Série": "-",
                "Quantité": q_sans,
                "Péremption": "-"
            })
        elif tot_q == 0.0 and depot not in lots_qte_by_depot:
            rows.append({
                "Dépôt": depot,
                "Lot / N° Série": "-",
                "Quantité": 0.0,
                "Péremption": "-"
            })
            
    if not rows and qte_par_depot:
        for depot, q in qte_par_depot.items():
            rows.append({
                "Dépôt": depot,
                "Lot / N° Série": "-",
                "Quantité": q,
                "Péremption": "-"
            })
            
    return pd.DataFrame(rows)


def get_article_stats(
    client_schema: str,
    ar_ref: str,
    ar_prixach: float,
    ar_prixven: float,
    qte_stock_actuel: float,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """
    Calcule les KPIs analytiques d'un article sélectionné.
    """
    filters: dict = {
        "ar_ref": [ar_ref],
        "with_entete": True,
        "do_domaine": [0],   # domaine Ventes uniquement
    }
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    lignes = get_documents_ligne(client_schema, filters=filters)

    df = pd.DataFrame(lignes) if lignes else pd.DataFrame()

    # Filtrer domaine ventes si la colonne est présente (sécurité)
    if not df.empty and "do_domaine" in df.columns:
        df = df[df["do_domaine"].astype(str) == "0"]

    qte_vendue = 0.0
    ca_ht = 0.0
    monthly: dict[str, dict] = {}

    if not df.empty:
        df["dl_qte"] = pd.to_numeric(df.get("dl_qte", 0), errors="coerce").fillna(0.0)
        df["dl_montantht"] = pd.to_numeric(df.get("dl_montantht", 0), errors="coerce").fillna(0.0)
        df["dl_prixunitaire"] = pd.to_numeric(df.get("dl_prixunitaire", 0), errors="coerce").fillna(0.0)

        qte_vendue = float(df["dl_qte"].sum())

        # Calcul du CA HT : priorité dl_montantht, sinon qte * prix unitaire, sinon qte * prix vente catalogue
        df["_ca_ligne"] = df.apply(
            lambda row: (
                row["dl_montantht"] if row["dl_montantht"] > 0
                else row["dl_qte"] * row["dl_prixunitaire"] if row["dl_prixunitaire"] > 0
                else row["dl_qte"] * float(ar_prixven)
            ),
            axis=1
        )
        ca_ht = float(df["_ca_ligne"].sum())

        if "do_date" in df.columns:
            df["mois"] = df["do_date"].astype(str).str[:7]
            grp = df.groupby("mois").agg(
                ca_mois=("_ca_ligne", "sum"),
                qte=("dl_qte", "sum"),
            ).reset_index()
            for _, row in grp.iterrows():
                mois = str(row["mois"])
                ca_m = float(row["ca_mois"])
                cout_m = float(row["qte"]) * float(ar_prixach)
                monthly[mois] = {"mois": mois, "ca": ca_m, "marge": ca_m - cout_m}

    cout_achat_total = qte_vendue * float(ar_prixach)
    marge_brute = ca_ht - cout_achat_total
    marge_brute_pct = (marge_brute / ca_ht * 100) if ca_ht > 0 else 0.0
    taux_rotation = (qte_vendue / float(qte_stock_actuel)) if float(qte_stock_actuel) > 0 else None
    rentabilite = (marge_brute / cout_achat_total * 100) if cout_achat_total > 0 else 0.0

    return {
        "quantite_vendue": qte_vendue,
        "chiffre_affaires_ht": ca_ht,
        "cout_achat_total": cout_achat_total,
        "marge_brute": marge_brute,
        "marge_brute_pct": marge_brute_pct,
        "taux_rotation_stock": taux_rotation,
        "rentabilite_globale": rentabilite,
        "evolution_mensuelle": sorted(monthly.values(), key=lambda x: x["mois"]),
    }
