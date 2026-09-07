import polars as pl
from typing import List, Dict, Any

def calculate_financial_valuation(raw_data: List[Dict[str, Any]], valuation_type: str = "both") -> List[Dict[str, Any]]:
    """
    Calcule la valorisation financière du stock (achat, vente, marge) pour chaque article.
    Agrège les quantités par article avant de faire le calcul si ce n'est pas déjà fait.
    """
    if not raw_data:
        return []
        
    df = pl.DataFrame(raw_data)
    
    # Vérification des colonnes de base
    if "ar_ref" not in df.columns or "as_qtesto" not in df.columns:
        return []

    group_cols = ["ar_ref"]
    if "ar_design" in df.columns:
        group_cols.append("ar_design")
        
    agg_exprs = [
        pl.col("as_qtesto").cast(pl.Float64, strict=False).sum().alias("quantite_totale")
    ]
    
    if "ar_prixach" in df.columns:
        agg_exprs.append((pl.col("as_qtesto").cast(pl.Float64, strict=False) * pl.col("ar_prixach").cast(pl.Float64, strict=False)).sum().alias("valeur_achat"))
        
    if "ar_prixven" in df.columns:
        agg_exprs.append((pl.col("as_qtesto").cast(pl.Float64, strict=False) * pl.col("ar_prixven").cast(pl.Float64, strict=False)).sum().alias("valeur_vente"))

    df_agg = df.group_by(group_cols).agg(agg_exprs)
    
    # Calcul optionnel de la marge si les deux valeurs sont présentes
    if valuation_type in ["both", "marge"] and "valeur_achat" in df_agg.columns and "valeur_vente" in df_agg.columns:
        df_agg = df_agg.with_columns(
            (pl.col("valeur_vente") - pl.col("valeur_achat")).alias("marge_potentielle")
        )
        
    # Filtrer les colonnes selon le valuation_type si nécessaire (optionnel, on peut tout renvoyer)
    return df_agg.to_dicts()


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
