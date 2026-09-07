"""
api/bi/business_logic/balance_calculations.py

Business logic en Polars pour la balance client.
Calcule la répartition de l'encours selon l'ancienneté des factures.
"""
from typing import List, Dict, Any
import polars as pl
from datetime import date


def calculate_balance_client(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prend les factures impayées, calcule la différence de mois par rapport à aujourd'hui,
    et répartit le reste_a_payer dans les colonnes En Cours, M1..M6, A Nouveau.
    Retourne le résultat agrégé par client, trié par Total décroissant.
    """
    if not data:
        return []

    df = pl.DataFrame(data)

    if df.is_empty():
        return []

    # S'assurer de la présence des colonnes minimales
    expected_cols = ["do_piece", "do_date", "do_tiers", "ct_intitule", "reste_a_payer"]
    for c in expected_cols:
        if c not in df.columns:
            return []

    today = date.today()
    current_year = today.year
    current_month = today.month

    # Convert do_date to datetime and extract year/month
    # We slice the first 10 chars "YYYY-MM-DD" to avoid issues with time or timezone suffixes
    df = df.with_columns([
        pl.col("do_date").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("date_parsed")
    ])

    df = df.with_columns([
        pl.col("date_parsed").dt.year().alias("invoice_year"),
        pl.col("date_parsed").dt.month().alias("invoice_month")
    ])

    # Ensure reste_a_payer is float64 (in case it comes as Decimal from PG)
    df = df.with_columns([
        pl.col("reste_a_payer").cast(pl.Float64)
    ])

    # Calculate month difference
    # If date is invalid (null), we put it in "En Cours" by default (month_diff = 0)
    df = df.with_columns([
        ((pl.lit(current_year) - pl.col("invoice_year")) * 12 + (pl.lit(current_month) - pl.col("invoice_month"))).fill_null(0).alias("month_diff")
    ])

    # Assign each row to a bucket
    # month_diff <= 0 -> En Cours (on inclut les factures post-datées)
    # month_diff == 1 -> M1
    # ...
    # month_diff == 6 -> M6
    # month_diff > 6 -> A Nouveau

    df = df.with_columns([
        pl.when(pl.col("month_diff") <= 0).then(pl.col("reste_a_payer")).otherwise(0.0).alias("en_cours"),
        pl.when(pl.col("month_diff") == 1).then(pl.col("reste_a_payer")).otherwise(0.0).alias("m1"),
        pl.when(pl.col("month_diff") == 2).then(pl.col("reste_a_payer")).otherwise(0.0).alias("m2"),
        pl.when(pl.col("month_diff") == 3).then(pl.col("reste_a_payer")).otherwise(0.0).alias("m3"),
        pl.when(pl.col("month_diff") == 4).then(pl.col("reste_a_payer")).otherwise(0.0).alias("m4"),
        pl.when(pl.col("month_diff") == 5).then(pl.col("reste_a_payer")).otherwise(0.0).alias("m5"),
        pl.when(pl.col("month_diff") == 6).then(pl.col("reste_a_payer")).otherwise(0.0).alias("m6"),
        pl.when(pl.col("month_diff") > 6).then(pl.col("reste_a_payer")).otherwise(0.0).alias("a_nouveau"),
    ])

    # Aggregate by client
    df_agg = df.group_by(["do_tiers", "ct_intitule"]).agg([
        pl.sum("a_nouveau").alias("A Nouveau"),
        pl.sum("m6").alias("M6"),
        pl.sum("m5").alias("M5"),
        pl.sum("m4").alias("M4"),
        pl.sum("m3").alias("M3"),
        pl.sum("m2").alias("M2"),
        pl.sum("m1").alias("M1"),
        pl.sum("en_cours").alias("En Cours")
    ])

    # Calculate Total
    df_agg = df_agg.with_columns([
        (pl.col("A Nouveau") + pl.col("M6") + pl.col("M5") + pl.col("M4") + 
         pl.col("M3") + pl.col("M2") + pl.col("M1") + pl.col("En Cours")).alias("Totale")
    ])

    # Sort by Totale descending
    df_agg = df_agg.sort("Totale", descending=True)

    # Rename identifying columns
    df_agg = df_agg.rename({
        "do_tiers": "Ref Client",
        "ct_intitule": "Nom Client"
    })

    return df_agg.to_dicts()
