"""
api/bi/business_logic/rapport_calculations.py

Logique métier pure pour les rapports BI :
  - Rapport CA (groupé par mois, client ou commercial)
  - Top N Clients
  - Top N Articles

Toutes les fonctions opèrent sur des DataFrames Polars — sans accès archives.
"""
from __future__ import annotations
import logging
from typing import Optional, List, Dict, Any

import polars as pl

from api.bi.repositories.archive_repo.base_bi_archive import safe_float_col

logger = logging.getLogger("api.bi.business_logic.rapport")


def detect_archive_mode(df: pl.DataFrame) -> bool:
    """
    Détecte si le DataFrame provient d'une archive où do_type est toujours 0.
    Dans ce cas, on filtre uniquement sur do_domaine.
    """
    try:
        do_types_unique = df["do_type"].drop_nulls().unique().to_list()
        return all(str(x) in ["0", "None"] for x in do_types_unique)
    except Exception:
        return True


def prepare_docentete_rapport(df_raw: pl.DataFrame) -> tuple[pl.DataFrame, bool]:
    """
    Prépare F_DOCENTETE pour les rapports et détecte le mode archive.
    Retourne (df_préparé, all_zero_types).
    """
    df = df_raw.with_columns([
        pl.col("do_domaine").cast(pl.Int64, strict=False),
        pl.col("do_type").cast(pl.Int64, strict=False),
        safe_float_col(df_raw, "do_totalttc").alias("do_totalttc_f"),
    ])
    all_zero = detect_archive_mode(df)
    return df, all_zero


def filter_ventes(df: pl.DataFrame, all_zero: bool) -> pl.DataFrame:
    """Filtre les documents de vente selon le mode archive ou normal."""
    if all_zero:
        return df.filter(pl.col("do_domaine") == 0)
    return df.filter((pl.col("do_domaine") == 0) & pl.col("do_type").is_in([6, 7]))


def apply_date_filters(df: pl.DataFrame, date_from: Optional[str], date_to: Optional[str]) -> pl.DataFrame:
    """Applique les filtres de période sur la colonne do_date."""
    if date_from:
        df = df.filter(pl.col("do_date").cast(pl.Utf8) >= date_from)
    if date_to:
        df = df.filter(pl.col("do_date").cast(pl.Utf8) <= date_to)
    return df


def group_ca_par_mois(df: pl.DataFrame) -> List[Dict[str, Any]]:
    """Groupe le CA TTC par mois (YYYY-MM) trié chronologiquement."""
    result = df.with_columns(
        pl.col("do_date").cast(pl.Utf8).str.slice(0, 7).alias("mois")
    ).group_by("mois").agg(
        pl.col("do_totalttc_f").sum().alias("ca_ttc"),
        pl.col("do_piece").count().alias("nb_factures"),
    ).sort("mois")
    return result.to_dicts()


def group_ca_par_client(df: pl.DataFrame) -> List[Dict[str, Any]]:
    """Groupe le CA TTC par client (do_tiers / ct_intitule), trié desc."""
    grp_col = "do_tiers"
    label_col = "ct_intitule" if "ct_intitule" in df.columns else "do_tiers"
    result = df.group_by([grp_col, label_col]).agg(
        pl.col("do_totalttc_f").sum().alias("ca_ttc"),
        pl.col("do_piece").count().alias("nb_factures"),
    ).sort("ca_ttc", descending=True)
    return result.to_dicts()


def group_ca_par_commercial(df: pl.DataFrame) -> List[Dict[str, Any]]:
    """Groupe le CA TTC par commercial (co_no + co_fullname), trié desc."""
    group_cols = ["co_no"]
    if "co_fullname" in df.columns:
        group_cols.append("co_fullname")
    result = df.group_by(group_cols).agg(
        pl.col("do_totalttc_f").sum().alias("ca_ttc"),
        pl.col("do_piece").count().alias("nb_factures"),
    ).sort("ca_ttc", descending=True)
    return result.to_dicts()


def group_ca_par_region(df: pl.DataFrame) -> List[Dict[str, Any]]:
    """Groupe le CA TTC par region (ct_ville), trié desc."""
    if "ct_ville" not in df.columns:
        return []
    result = df.group_by("ct_ville").agg(
        pl.col("do_totalttc_f").sum().alias("ca_ttc"),
        pl.col("do_piece").count().alias("nb_factures"),
    ).sort("ca_ttc", descending=True)
    return result.to_dicts()


def join_tiers(df: pl.DataFrame, df_tiers: Optional[pl.DataFrame]) -> pl.DataFrame:
    """Enrichit le DataFrame avec ct_intitule et ct_ville depuis F_COMPTET."""
    if df_tiers is not None:
        # Some archives might not have ct_ville, we need to handle that gracefully
        cols_to_select = ["ct_num", "ct_intitule"]
        if "ct_ville" in df_tiers.columns:
            cols_to_select.append("ct_ville")
            
        df = df.join(
            df_tiers.select(cols_to_select),
            left_on="do_tiers", right_on="ct_num", how="left"
        )
    return df


def join_collaborateur(df: pl.DataFrame, df_col: Optional[pl.DataFrame]) -> pl.DataFrame:
    """Enrichit le DataFrame avec co_fullname depuis F_COLLABORATEUR."""
    if df_col is not None:
        df = df.join(
            df_col.with_columns(
                (pl.col("co_nom") + pl.lit(" ") + pl.col("co_prenom")).alias("co_fullname")
            ).select(["co_no", "co_fullname"]),
            on="co_no", how="left"
        )
    return df


def calc_top_clients_rapport(
    df: pl.DataFrame,
    df_tiers: Optional[pl.DataFrame],
    limit: int,
) -> List[Dict[str, Any]]:
    """
    Calcule le top N clients par CA TTC.
    Retourne une liste de dicts : do_tiers, ct_intitule, ca_ttc, nb_factures.
    """
    result = df.group_by("do_tiers").agg(
        pl.col("do_totalttc_f").sum().alias("ca_ttc"),
        pl.col("do_piece").count().alias("nb_factures"),
    ).sort("ca_ttc", descending=True)

    if df_tiers is not None:
        result = result.join(
            df_tiers.select(["ct_num", "ct_intitule"]),
            left_on="do_tiers", right_on="ct_num", how="left"
        )
    return result.to_dicts()


def prepare_docligne_articles(df_raw: pl.DataFrame) -> tuple[pl.DataFrame, bool]:
    """
    Prépare F_DOCLIGNE pour le rapport articles.
    Retourne (df_préparé, all_zero_types).
    """
    df = df_raw.with_columns([
        pl.col("do_domaine").cast(pl.Int64, strict=False),
        pl.col("do_type").cast(pl.Int64, strict=False),
        safe_float_col(df_raw, "dl_qte").alias("dl_qte_f"),
        safe_float_col(df_raw, "dl_montantht").alias("dl_montantht_f"),
    ])
    all_zero = detect_archive_mode(df)
    return df, all_zero


def filter_ventes_lignes(df: pl.DataFrame, all_zero: bool) -> pl.DataFrame:
    """Filtre les lignes de vente selon le mode archive ou normal."""
    if all_zero:
        return df.filter((pl.col("do_domaine") == 0) & pl.col("ar_ref").is_not_null())
    return df.filter(
        (pl.col("do_domaine") == 0) &
        pl.col("do_type").is_in([6, 7]) &
        pl.col("ar_ref").is_not_null()
    )


def calc_top_articles_rapport(
    df: pl.DataFrame,
    df_article: Optional[pl.DataFrame],
) -> List[Dict[str, Any]]:
    """
    Calcule le top articles par CA HT.
    Retourne une liste de dicts : ar_ref, ar_design, qte_vendue, ca_ht.
    """
    result = df.group_by("ar_ref").agg(
        pl.col("dl_qte_f").sum().alias("qte_vendue"),
        pl.col("dl_montantht_f").sum().alias("ca_ht"),
    ).sort("ca_ht", descending=True)

    if df_article is not None:
        result = result.join(
            df_article.select(["ar_ref", "ar_design"]),
            on="ar_ref", how="left"
        )
    return result.to_dicts()
