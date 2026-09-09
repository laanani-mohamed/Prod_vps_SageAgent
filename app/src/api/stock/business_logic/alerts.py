import polars as pl
from typing import List, Dict, Any

def detect_stock_alerts(raw_data: List[Dict[str, Any]], alert_type: str, threshold: float = 0.0) -> List[Dict[str, Any]]:
    """
    Détecte les alertes de stock : rupture, stock bas, dormant avec stock.
    Agrège le stock par article au préalable, ou garde le détail par dépôt pour les ruptures.
    """
    if not raw_data:
        return []

    df = pl.DataFrame(raw_data)
    
    if "ar_ref" not in df.columns or "as_qtesto" not in df.columns:
        return []

    if alert_type == "rupture":
        # Conserver le détail par dépôt et le type de suivi de stock pour la rupture
        group_cols = ["ar_ref"]
        if "ar_design" in df.columns:
            group_cols.append("ar_design")
        if "fa_codefamille" in df.columns:
            group_cols.append("fa_codefamille")
        if "de_intitule" in df.columns:
            group_cols.append("de_intitule")
        if "ar_suivistock" in df.columns:
            group_cols.append("ar_suivistock")
        if "derniere_date_vente" in df.columns:
            group_cols.append("derniere_date_vente")
        if "nbr_jours_inactif" in df.columns:
            group_cols.append("nbr_jours_inactif")

        df_agg = df.group_by(group_cols).agg([
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
        ])

        # Filtrer les stocks en rupture (<= 0)
        df_agg = df_agg.filter(pl.col("quantite_totale") <= 0)

        # Ajouter le flag de suivi par lot ("Oui" si ar_suivistock == 5)
        if "ar_suivistock" in df_agg.columns:
            df_agg = df_agg.with_columns(
                pl.when(pl.col("ar_suivistock").cast(pl.Utf8) == "5")
                .then(pl.lit("Oui"))
                .otherwise(pl.lit("Non"))
                .alias("suivi_lot")
            )
        else:
            df_agg = df_agg.with_columns(pl.lit("Non").alias("suivi_lot"))
    else:
        # Agrégation globale pour stock_bas et dormant
        group_cols = ["ar_ref"]
        if "ar_design" in df.columns:
            group_cols.append("ar_design")
        if "fa_codefamille" in df.columns:
            group_cols.append("fa_codefamille")
        if "derniere_date_vente" in df.columns:
            group_cols.append("derniere_date_vente")
        if "nbr_jours_inactif" in df.columns:
            group_cols.append("nbr_jours_inactif")

        agg_exprs = [
            pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
        ]
        if "ar_prixach" in df.columns:
            agg_exprs.append(pl.col("ar_prixach").cast(pl.Float64, strict=False).mean().alias("prix_achat"))

        df_agg = df.group_by(group_cols).agg(agg_exprs)

        if "prix_achat" in df_agg.columns:
            df_agg = df_agg.with_columns(
                (pl.col("quantite_totale") * pl.col("prix_achat")).alias("valeur_stock")
            )

        if alert_type == "stock_bas":
            df_agg = df_agg.filter((pl.col("quantite_totale") > 0) & (pl.col("quantite_totale") <= threshold))
        elif alert_type == "dormant_with_stock":
            df_agg = df_agg.filter(pl.col("quantite_totale") > 0)

    return df_agg.to_dicts()


def detect_expiring_lots(lots_data: List[Dict[str, Any]], expiry_days: int = 30) -> List[Dict[str, Any]]:
    """
    Détecte les lots qui périment dans les prochains expiry_days jours.
    Calcule automatiquement le nombre de jours restants.
    """
    if not lots_data:
        return []

    from datetime import date
    df = pl.DataFrame(lots_data)

    if "ls_peremption" not in df.columns:
        return []

    today = date.today()
    df = df.with_columns(
        pl.col("ls_peremption").cast(pl.Date, strict=False)
    )

    # Filtrer : périme dans expiry_days jours
    cutoff = pl.lit(today).cast(pl.Date) + pl.duration(days=expiry_days)
    df_filtered = df.filter(
        (pl.col("ls_peremption") <= cutoff) &
        (pl.col("ls_peremption") >= pl.lit(today).cast(pl.Date))
    )

    # Calculer les jours restants et filtrer les lots non épuisés (ls_lotepuise = 0)
    if not df_filtered.is_empty():
        df_filtered = df_filtered.with_columns(
            ((pl.col("ls_peremption") - pl.lit(today)).dt.total_days()).alias("jours_restants")
        )

        # Correction : Cast sûr de ls_lotepuise pour éviter l'erreur type-mismatch (string vs int32)
        if "ls_lotepuise" in df_filtered.columns:
            df_filtered = df_filtered.filter(
                pl.col("ls_lotepuise").cast(pl.Int32, strict=False).fill_null(0) == 0
            )

    return df_filtered.sort("jours_restants").to_dicts() if not df_filtered.is_empty() else []

