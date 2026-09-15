"""
api/bi/business_logic/kpi_calculations.py

Logique métier pure pour le calcul des KPIs du tableau de bord.
Toutes les fonctions prennent des DataFrames Polars et retournent
des valeurs scalaires ou des listes — sans accès aux archives.

Couvre :
  - Chiffre d'Affaires (avec filtre période)
  - CA N-1 (comparaison annuelle)
  - Évolution CA mensuelle
  - Encours clients
  - Dettes fournisseurs
  - Achats
  - Valorisation du stock
  - Nombre de clients actifs
"""
from __future__ import annotations
import logging
from typing import Optional, List, Dict, Any

import polars as pl

from api.bi.repositories.archive_repo.base_bi_archive import safe_float_col

logger = logging.getLogger("api.bi.business_logic.kpi")


def prepare_docentete(df_raw: pl.DataFrame) -> pl.DataFrame:
    """
    Prépare le DataFrame F_DOCENTETE avec les colonnes castées nécessaires.
    Retourne un DataFrame enrichi avec les colonnes *_f (float).
    """
    return df_raw.with_columns([
        pl.col("do_domaine").cast(pl.Int64, strict=False),
        pl.col("do_type").cast(pl.Int64, strict=False),
        safe_float_col(df_raw, "do_totalht").alias("do_totalht_f"),
        safe_float_col(df_raw, "do_totalttc").alias("do_totalttc_f"),
        safe_float_col(df_raw, "do_montantregle").alias("do_montantregle_f"),
    ])


def calc_chiffre_affaires(df_e: pl.DataFrame, date_from: Optional[str], date_to: Optional[str]) -> float:
    """Calcule le CA TTC sur les factures vente (do_type=6, do_domaine=0) avec filtre période."""
    df = df_e
    if date_from:
        df = df.filter(pl.col("do_date").cast(pl.Utf8) >= date_from)
    if date_to:
        df = df.filter(pl.col("do_date").cast(pl.Utf8) <= date_to)
    df_ca = df.filter((pl.col("do_domaine") == 0) & pl.col("do_type").is_in([6, 7]))
    return float(df_ca["do_totalttc_f"].sum() or 0)


def calc_ca_n_minus_1(df_e_unfiltered: pl.DataFrame, date_from: str, date_to: str) -> float:
    """Calcule le CA TTC de la même période un an en arrière."""
    from datetime import datetime

    def subtract_one_year(dt):
        try:
            return dt.replace(year=dt.year - 1)
        except ValueError:
            return dt.replace(year=dt.year - 1, day=28)

    try:
        d_from = datetime.fromisoformat(date_from)
        d_to = datetime.fromisoformat(date_to)
        d_from_n1 = subtract_one_year(d_from).strftime("%Y-%m-%d")
        d_to_n1 = subtract_one_year(d_to).strftime("%Y-%m-%d")

        df_ca_n1 = df_e_unfiltered.filter(
            (pl.col("do_domaine") == 0) &
            pl.col("do_type").is_in([6, 7]) &
            (pl.col("do_date").cast(pl.Utf8) >= d_from_n1) &
            (pl.col("do_date").cast(pl.Utf8) <= d_to_n1)
        )
        return float(df_ca_n1["do_totalttc_f"].sum() or 0)
    except Exception as e:
        logger.warning("[BI] Erreur calcul CA N-1 : %s", e)
        return 0.0


def calc_evolution_mensuelle(df_e: pl.DataFrame, date_from: Optional[str], date_to: Optional[str]) -> List[Dict[str, Any]]:
    """Retourne l'évolution CA mensuelle (6 derniers mois) depuis les factures vente."""
    try:
        df = df_e
        if date_from:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) >= date_from)
        if date_to:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) <= date_to)
        df_ca = df.filter((pl.col("do_domaine") == 0) & pl.col("do_type").is_in([6, 7]))

        df_monthly = df_ca.with_columns(
            pl.col("do_date").cast(pl.Utf8).str.slice(0, 7).alias("mois")
        ).group_by("mois").agg(
            pl.col("do_totalttc_f").sum().alias("ca")
        ).sort("mois", descending=False).tail(6)

        return [
            {"mois": r["mois"], "ca": round(r["ca"], 2)}
            for r in df_monthly.to_dicts()
        ]
    except Exception as e:
        logger.warning("[BI] Impossible de calculer l'évolution CA mensuelle : %s", e)
        return []


def calc_encours_clients(df_e_unfiltered: pl.DataFrame) -> float:
    """Calcule l'encours clients total (toutes dates) : somme des restes à payer > 0."""
    df_enc_base = df_e_unfiltered.filter(
        (pl.col("do_domaine") == 0) & pl.col("do_type").is_in([6, 7])
    )
    df_enc = df_enc_base.with_columns(
        (pl.col("do_totalttc_f") - pl.col("do_montantregle_f")).alias("reste")
    ).filter(pl.col("reste") > 0)
    return float(df_enc["reste"].sum() or 0)


def calc_dettes_fournisseurs(df_e_unfiltered: pl.DataFrame) -> float:
    """Calcule les dettes fournisseurs : SUM(TTC - MontantReglé) sur factures achat (do_type=16, 17)."""
    df_dettes_base = df_e_unfiltered.filter(
        (pl.col("do_domaine") == 1) & pl.col("do_type").is_in([16, 17])
    )
    df_dettes = df_dettes_base.with_columns(
        (pl.col("do_totalttc_f") - pl.col("do_montantregle_f")).alias("reste")
    ).filter(pl.col("reste") > 0)
    return float(df_dettes["reste"].sum() or 0)


def calc_total_achats(df_e: pl.DataFrame, date_from: Optional[str], date_to: Optional[str]) -> float:
    """Calcule le total des achats HT (do_type=16, 17) avec filtre période."""
    df = df_e
    if date_from:
        df = df.filter(pl.col("do_date").cast(pl.Utf8) >= date_from)
    if date_to:
        df = df.filter(pl.col("do_date").cast(pl.Utf8) <= date_to)
    df_ach = df.filter(pl.col("do_type").is_in([16, 17]))
    return float(df_ach["do_totalht_f"].sum() or 0)


def calc_nb_clients_actifs(df_e: pl.DataFrame, date_from: Optional[str], date_to: Optional[str]) -> int:
    """Nombre de clients distincts sur les factures vente de la période."""
    df = df_e
    if date_from:
        df = df.filter(pl.col("do_date").cast(pl.Utf8) >= date_from)
    if date_to:
        df = df.filter(pl.col("do_date").cast(pl.Utf8) <= date_to)
    df_ca = df.filter((pl.col("do_domaine") == 0) & pl.col("do_type").is_in([6, 7]))
    return df_ca["do_tiers"].n_unique()


def calc_valeur_stock(df_stock: pl.DataFrame, df_article: pl.DataFrame) -> float:
    """Valorise le stock : SUM(as_qtesto × ar_prixach) via jointure F_ARTSTOCK × F_ARTICLE."""
    try:
        df_s = df_stock.with_columns(
            pl.col("as_qtesto").cast(pl.Float64, strict=False).fill_null(0.0)
        )
        df_a = df_article.select(["ar_ref", "ar_prixach"]).with_columns(
            pl.col("ar_prixach").cast(pl.Float64, strict=False).fill_null(0.0)
        )
        df_merged = df_s.join(df_a, on="ar_ref", how="left")
        df_merged = df_merged.with_columns(
            (pl.col("as_qtesto") * pl.col("ar_prixach")).alias("valeur")
        )
        return float(df_merged["valeur"].sum() or 0)
    except Exception as e:
        logger.warning("[BI] Impossible de valoriser le stock : %s", e)
        return 0.0
