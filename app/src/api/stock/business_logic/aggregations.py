import polars as pl
from typing import List, Dict, Any, Optional
from datetime import date

def aggregate_availability(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Agrège les stocks par référence et désignation."""
    if not raw_data:
        return []
    
    df = pl.DataFrame(raw_data)
    
    # S'assurer que les colonnes nécessaires existent
    if "ar_ref" not in df.columns or "as_qtesto" not in df.columns:
        return []

    group_cols = ["ar_ref"]
    if "ar_design" in df.columns:
        group_cols.append("ar_design")

    df_agg = df.group_by(group_cols).agg([
        pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
    ])
    
    results = df_agg.to_dicts()

    # Construire la répartition par dépôt
    depots_by_ref = {}
    for row in raw_data:
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
            if ref not in depots_by_ref:
                depots_by_ref[ref] = {}
            depots_by_ref[ref][depot] = depots_by_ref[ref].get(depot, 0.0) + qte_f

    # Injecter qte_par_depot dans chaque ligne résultat
    for row in results:
        ref = row.get("ar_ref")
        row["qte_par_depot"] = depots_by_ref.get(ref, {})

    return results


def generate_summary_statistics(
    raw_data: List[Dict[str, Any]], 
    summary_type: str, 
    top_n: int = 10, 
    least_n: int = 10
) -> List[Dict[str, Any]]:
    """Génère des statistiques de résumé de stock (global, famille, top, least)."""
    if not raw_data:
        return []
        
    df = pl.DataFrame(raw_data)
    
    # Si la colonne as_qtesto n'existe pas, on ne peut rien faire
    if "as_qtesto" not in df.columns:
        return []

    if summary_type == "global":
        exprs = [
            pl.col("ar_ref").n_unique().alias("nb_references") if "ar_ref" in df.columns else pl.lit(0).alias("nb_references"),
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale"),
        ]
        if "ar_prixach" in df.columns:
            exprs.append((pl.col("as_qtesto").cast(pl.Float64, strict=False) * pl.col("ar_prixach").cast(pl.Float64, strict=False)).sum().alias("valeur_totale_achat"))
        
        df_agg = df.select(exprs)

    elif summary_type == "by_family":
        if "fa_codefamille" not in df.columns:
            return []
        df_agg = df.group_by("fa_codefamille").agg([
            pl.col("ar_ref").n_unique().alias("nb_references") if "ar_ref" in df.columns else pl.lit(0).alias("nb_references"),
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
        ]).sort("quantite_totale", descending=True)

    elif summary_type == "top_n":
        group_cols = ["ar_ref"]
        if "ar_design" in df.columns:
            group_cols.append("ar_design")
            
        df_agg = df.group_by(group_cols).agg([
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
        ]).sort("quantite_totale", descending=True).head(top_n)

    elif summary_type == "least_n":
        group_cols = ["ar_ref"]
        if "ar_design" in df.columns:
            group_cols.append("ar_design")
            
        df_agg = df.group_by(group_cols).agg([
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
        ]).filter(pl.col("quantite_totale") > 0).sort("quantite_totale", descending=False).head(least_n)

    else:
        # Fallback pour tout autre type
        exprs = [
            pl.col("ar_ref").n_unique().alias("nb_references") if "ar_ref" in df.columns else pl.lit(0).alias("nb_references"),
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
        ]
        df_agg = df.select(exprs)

    return df_agg.to_dicts()


def aggregate_by_depot(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Agrège le stock par article ET par dépôt."""
    if not raw_data:
        return []
    df = pl.DataFrame(raw_data)
    if "ar_ref" not in df.columns or "as_qtesto" not in df.columns:
        return []

    group_cols = ["ar_ref"]
    if "ar_design" in df.columns:
        group_cols.append("ar_design")
    if "de_no" in df.columns:
        group_cols.append("de_no")
    if "de_intitule" in df.columns:
        group_cols.append("de_intitule")

    # Prix : on prend la première valeur (stable par article)
    agg_exprs = [pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_depot")]
    for price_col in ("ar_prixven", "ar_prixach"):
        if price_col in df.columns:
            agg_exprs.append(pl.col(price_col).cast(pl.Float64, strict=False).first().alias(price_col))

    df_agg = df.group_by(group_cols).agg(agg_exprs)

    # Ajouter quantite_totale globale par article
    totals = df.group_by("ar_ref").agg(
        pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
    )
    df_agg = df_agg.join(totals, on="ar_ref", how="left")

    return df_agg.sort(["ar_ref", "de_no"] if "de_no" in df_agg.columns else ["ar_ref"]).to_dicts()


def aggregate_catalog(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Agrège le stock pour le catalogue (par article), conserve les métadonnées techniques."""
    if not raw_data:
        return []
    df = pl.DataFrame(raw_data)
    if "ar_ref" not in df.columns or "as_qtesto" not in df.columns:
        return []

    # Colonnes de groupe : données stables par article
    group_cols = ["ar_ref"]
    stable_cols = ["ar_design", "fa_codefamille", "ar_nature", "ar_type",
                   "ar_suivistock", "ar_prixven", "ar_prixach", "ar_sommeil"]
    group_cols += [c for c in stable_cols if c in df.columns]

    df_agg = df.group_by(group_cols).agg(
        pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
    )

    results = df_agg.sort("ar_design" if "ar_design" in df_agg.columns else "ar_ref").to_dicts()

    # Construire la répartition par dépôt
    depots_by_ref = {}
    for row in raw_data:
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
            if ref not in depots_by_ref:
                depots_by_ref[ref] = {}
            depots_by_ref[ref][depot] = depots_by_ref[ref].get(depot, 0.0) + qte_f

    # Injecter qte_par_depot dans chaque ligne résultat
    for row in results:
        ref = row.get("ar_ref")
        row["qte_par_depot"] = depots_by_ref.get(ref, {})

    return results


def build_article_detail(
    raw_data: List[Dict[str, Any]],
    lots_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Construit la fiche détaillée d'un article avec labels lisibles.

    - nature, type, suivistock, sommeil → traduits en intitulés
    - de_intitule affiché (de_no supprimé)
    - quantite_depot supprimé (juste quantite_totale)
    - lots : affichés uniquement si non vides/null
    """
    # Dictionnaires de traduction
    NATURE_LABELS = {
        "0": "Composant", "1": "Pièce détachée",
        "2": "Produit fini", "3": "Produit semi-fini"
    }
    TYPE_LABELS = {
        "0": "Standard", "1": "Gamme",
        "2": "Ressource prestation", "3": "Ressource location"
    }
    SUIVI_LABELS = {
        "0": "Aucun", "1": "Sérialisé", "2": "CMUP",
        "3": "FIFO", "4": "LIFO", "5": "Par lot"
    }
    SOMMEIL_LABELS = {"0": "Actif", "1": "En sommeil"}

    if not raw_data:
        return []
    df = pl.DataFrame(raw_data)

    # Colonnes stables à garder par article
    stable_cols = ["ar_ref", "ar_design", "fa_codefamille", "ar_nature", "ar_type",
                   "ar_suivistock", "ar_prixven", "ar_prixach", "ar_sommeil"]
    group_cols = [c for c in stable_cols if c in df.columns]

    # Colonnes dépôt (on inclut de_intitule mais PAS de_no ni quantite_depot)
    depot_cols = ["de_intitule"] if "de_intitule" in df.columns else []

    # Agrégation pour avoir un seul enregistrement par article
    # (les données de dépôt seront dans une sous-liste)
    df_article = df.select(group_cols).unique(subset=["ar_ref"])

    # Quantité totale globale
    totals = df.group_by("ar_ref").agg(
        pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
    )
    df_article = df_article.join(totals, on="ar_ref", how="left")

    # Stock par dépôt (sans de_no, sans quantite_depot)
    if "de_intitule" in df.columns:
        df_depots = df.group_by(["ar_ref", "de_intitule"]).agg(
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("qte")
        )
        depots_by_ref: dict = {}
        for d in df_depots.to_dicts():
            ref = d["ar_ref"]
            if ref not in depots_by_ref:
                depots_by_ref[ref] = []
            depots_by_ref[ref].append({"depot": d["de_intitule"], "qte": d["qte"]})
    else:
        depots_by_ref = {}

    result = df_article.sort("ar_ref").to_dicts()

    # Appliquer les labels et nettoyer les champs numériques bruts
    for row in result:
        # Traduire nature
        if "ar_nature" in row:
            row["nature"] = NATURE_LABELS.get(str(row.pop("ar_nature", "")), "Inconnu")
        # Traduire type
        if "ar_type" in row:
            row["type"] = TYPE_LABELS.get(str(row.pop("ar_type", "")), "Inconnu")
        # Traduire suivistock
        if "ar_suivistock" in row:
            row["suivi_stock"] = SUIVI_LABELS.get(str(row.pop("ar_suivistock", "")), "Inconnu")
        # Traduire sommeil
        if "ar_sommeil" in row:
            row["statut"] = SOMMEIL_LABELS.get(str(row.pop("ar_sommeil", "")), "Inconnu")

        # Ajouter les dépôts avec stock
        row["depots"] = depots_by_ref.get(row.get("ar_ref"), [])

    # Intégrer les lots si disponibles et non vides
    if lots_data:
        lots_df = pl.DataFrame(lots_data)
        today = date.today()

        if "ls_peremption" in lots_df.columns:
            lots_df = lots_df.with_columns(
                pl.col("ls_peremption").cast(pl.Date, strict=False)
            ).with_columns(
                ((pl.col("ls_peremption") - pl.lit(today)).dt.total_days()).alias("jours_restants")
            )

        lots_by_ref: dict = {}
        for lot in lots_df.to_dicts():
            ref = lot.get("ar_ref")
            # Ignorer les lots avec numéro de série null
            if not lot.get("ls_noserie"):
                continue
            if ref not in lots_by_ref:
                lots_by_ref[ref] = []
            lots_by_ref[ref].append({
                k: v for k, v in lot.items()
                if k not in ("ar_ref", "de_no") and v is not None
            })

        for row in result:
            ref_lots = lots_by_ref.get(row.get("ar_ref"), [])
            # N'ajouter le champ "lots" QUE si la liste n'est pas vide
            if ref_lots:
                row["lots"] = ref_lots

    return result

