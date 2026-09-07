import polars as pl
from typing import List, Dict, Any

def calculate_time_delta(data_from: List[Dict[str, Any]], data_to: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calcule la différence de quantité en stock entre deux périodes.
    """
    df_from = pl.DataFrame(data_from) if data_from else pl.DataFrame()
    df_to = pl.DataFrame(data_to) if data_to else pl.DataFrame()

    if df_from.is_empty() and df_to.is_empty():
        return []

    # On s'assure d'avoir les colonnes minimales pour from
    if not df_from.is_empty() and ("ar_ref" in df_from.columns and "as_qtesto" in df_from.columns):
        df_from_agg = df_from.group_by("ar_ref").agg([
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("qty_from")
        ])
    else:
        df_from_agg = pl.DataFrame({"ar_ref": [], "qty_from": []})

    # On s'assure d'avoir les colonnes minimales pour to
    if not df_to.is_empty() and ("ar_ref" in df_to.columns and "as_qtesto" in df_to.columns):
        df_to_agg = df_to.group_by("ar_ref").agg([
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("qty_to")
        ])
    else:
        df_to_agg = pl.DataFrame({"ar_ref": [], "qty_to": []})
        
    # S'il manque des données pertinentes on retourne vide
    if df_from_agg.is_empty() and df_to_agg.is_empty():
        return []

    # Jointure
    df_res = df_from_agg.join(df_to_agg, on="ar_ref", how="full", coalesce=True)
    df_res = df_res.with_columns([
        pl.col("qty_from").fill_null(0.0),
        pl.col("qty_to").fill_null(0.0),
    ])
    df_res = df_res.with_columns(
        (pl.col("qty_to") - pl.col("qty_from")).alias("delta")
    )
    
    # On ajoute ar_design si on peut (on le prend de l'un ou de l'autre)
    if "ar_design" in df_from.columns or "ar_design" in df_to.columns:
        # On extrait un mapping ref -> design de tout ce qu'on peut
        df_design = pl.concat([
            df_from.select(["ar_ref", "ar_design"]) if "ar_design" in df_from.columns else pl.DataFrame({"ar_ref": [], "ar_design": []}),
            df_to.select(["ar_ref", "ar_design"]) if "ar_design" in df_to.columns else pl.DataFrame({"ar_ref": [], "ar_design": []})
        ]).unique("ar_ref", maintain_order=True)
        
        df_res = df_res.join(df_design, on="ar_ref", how="left")

    results = df_res.to_dicts()

    # Construire la répartition par dépôt pour T1
    depots_by_ref_t1 = {}
    for row in data_from:
        ref = row.get("ar_ref")
        if not ref:
            continue
        depot = row.get("de_intitule")
        if not depot and row.get("de_no") is not None:
            depot = f"Dépôt {row.get('de_no')}"
        elif not depot:
            depot = "Inconnu"
            
        qte = row.get("as_qtesto")
        if qte is not None:
            try:
                qte_f = float(qte)
            except (ValueError, TypeError):
                qte_f = 0.0
            if qte_f != 0.0:
                if ref not in depots_by_ref_t1:
                    depots_by_ref_t1[ref] = {}
                depots_by_ref_t1[ref][depot] = depots_by_ref_t1[ref].get(depot, 0.0) + qte_f

    # Construire la répartition par dépôt pour T2
    depots_by_ref_t2 = {}
    for row in data_to:
        ref = row.get("ar_ref")
        if not ref:
            continue
        depot = row.get("de_intitule")
        if not depot and row.get("de_no") is not None:
            depot = f"Dépôt {row.get('de_no')}"
        elif not depot:
            depot = "Inconnu"
            
        qte = row.get("as_qtesto")
        if qte is not None:
            try:
                qte_f = float(qte)
            except (ValueError, TypeError):
                qte_f = 0.0
            if qte_f != 0.0:
                if ref not in depots_by_ref_t2:
                    depots_by_ref_t2[ref] = {}
                depots_by_ref_t2[ref][depot] = depots_by_ref_t2[ref].get(depot, 0.0) + qte_f

    # Injecter les dictionnaires par dépôt dans chaque ligne résultat
    for row in results:
        ref = row.get("ar_ref")
        row["qte_par_depot_t1"] = depots_by_ref_t1.get(ref, {})
        row["qte_par_depot_t2"] = depots_by_ref_t2.get(ref, {})

    return results

