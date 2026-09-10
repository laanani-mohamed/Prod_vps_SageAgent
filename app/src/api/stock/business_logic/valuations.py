import polars as pl
from typing import List, Dict, Any

def add_unit_financials(data: list[dict]) -> list[dict]:
    """
    Ajoute les colonnes financières unitaires à une liste déjà agrégée par article.
    Requiert ar_prixven et ar_prixach dans les données.

    Ajoute : marge_unitaire (prix_vente - prix_achat) et marge_taux (%)
    """
    if not data:
        return data
    df = pl.DataFrame(data)

    if "ar_prixven" in df.columns and "ar_prixach" in df.columns:
        df = df.with_columns([
            (pl.col("ar_prixven").cast(pl.Float64, strict=False) -
             pl.col("ar_prixach").cast(pl.Float64, strict=False)).alias("marge_unitaire")
        ])
        df = df.with_columns([
            pl.when(pl.col("ar_prixven") > 0)
            .then(
                (pl.col("marge_unitaire") / pl.col("ar_prixven").cast(pl.Float64, strict=False) * 100)
                .round(2)
            )
            .otherwise(None)
            .alias("marge_taux")
        ])
    return df.to_dicts()
