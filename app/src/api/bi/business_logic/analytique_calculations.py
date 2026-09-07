"""
api/bi/business_logic/analytique_calculations.py

Logique métier pure pour les KPIs analytiques avancés (get_analytique).
Toutes les fonctions opèrent sur des DataFrames Polars — sans accès archives.

Couvre :
  - DSO (Days Sales Outstanding)
  - Taux d'impayés
  - Taux de retour
  - Taux de conversion Devis → Facture
  - Marge Brute avec coût cascade (PrixRU → CMUP → PrixAch)
  - Top 10 Clients
  - Top 10 Fournisseurs (par encours)
  - Top Familles (CA HT)
  - Top Articles par Famille
"""
from __future__ import annotations
import logging
from typing import Optional, List, Dict, Any

import polars as pl

from api.bi.repositories.archive_repo.base_bi_archive import safe_float_col

logger = logging.getLogger("api.bi.business_logic.analytique")


# ---------------------------------------------------------------------------
# Préparation des DataFrames
# ---------------------------------------------------------------------------

def prepare_docentete_analytique(df_raw: pl.DataFrame) -> pl.DataFrame:
    """Caste et enrichit F_DOCENTETE pour les calculs analytiques."""
    return df_raw.with_columns([
        pl.col("do_domaine").cast(pl.Int64, strict=False),
        pl.col("do_type").cast(pl.Int64, strict=False),
        safe_float_col(df_raw, "do_totalht").alias("do_totalht_f"),
        safe_float_col(df_raw, "do_totalttc").alias("do_totalttc_f"),
        safe_float_col(df_raw, "do_montantregle").alias("do_montantregle_f"),
        pl.col("do_date").cast(pl.Utf8).alias("do_date_str"),
    ])


def prepare_docligne_analytique(df_raw: pl.DataFrame) -> pl.DataFrame:
    """Caste F_DOCLIGNE pour les calculs de marge et top clients."""
    cols = [
        pl.col("do_domaine").cast(pl.Int64, strict=False),
        pl.col("do_type").cast(pl.Int64, strict=False),
        safe_float_col(df_raw, "dl_montantht").alias("dl_montantht_f"),
        safe_float_col(df_raw, "dl_qtebl").alias("dl_qtebl_f"),
        safe_float_col(df_raw, "dl_prixru").alias("dl_prixru_f"),
        pl.col("do_date").cast(pl.Utf8).alias("do_date_str"),
    ]
    # Si ar_prixach est déjà présent (repo PG joint F_ARTICLE), on crée ar_prixach_f
    if "ar_prixach" in df_raw.columns:
        cols.append(safe_float_col(df_raw, "ar_prixach").alias("ar_prixach_f"))
    else:
        cols.append(pl.lit(0.0).alias("ar_prixach_f"))

    return df_raw.with_columns(cols)



def join_article_to_docligne(df_dl: pl.DataFrame, df_art: Optional[pl.DataFrame]) -> pl.DataFrame:
    """Enrichit F_DOCLIGNE avec ar_prixach, fa_codefamille, ar_design depuis F_ARTICLE."""
    if df_art is None:
        return df_dl.with_columns(pl.lit(0.0).alias("ar_prixach_f"))

    df_art_clean = df_art.select([
        pl.col("ar_ref"),
        safe_float_col(df_art, "ar_prixach").alias("ar_prixach_f"),
        pl.col("fa_codefamille").cast(pl.Utf8).alias("fa_codefamille")
        if "fa_codefamille" in df_art.columns else pl.lit("").alias("fa_codefamille"),
        pl.col("ar_design").cast(pl.Utf8).alias("ar_design")
        if "ar_design" in df_art.columns else pl.lit("").alias("ar_design"),
    ])
    return df_dl.join(df_art_clean, on="ar_ref", how="left")


def add_cout_cascade(df_dl: pl.DataFrame) -> pl.DataFrame:
    """
    Ajoute la colonne cout_unitaire_revient en cascade :
    PrixRU → CMUP → PrixAch (du plus précis au moins précis).
    """
    if "dl_cmup" in df_dl.columns:
        df_dl = df_dl.with_columns(safe_float_col(df_dl, "dl_cmup").alias("dl_cmup_f"))
    else:
        df_dl = df_dl.with_columns(pl.lit(0.0).alias("dl_cmup_f"))

    return df_dl.with_columns(
        pl.when(pl.col("dl_prixru_f") > 0.0)
        .then(pl.col("dl_prixru_f"))
        .when(pl.col("dl_cmup_f") > 0.0)
        .then(pl.col("dl_cmup_f"))
        .otherwise(pl.col("ar_prixach_f").fill_null(0.0))
        .alias("cout_unitaire_revient")
    )


# ---------------------------------------------------------------------------
# KPIs depuis F_DOCENTETE
# ---------------------------------------------------------------------------

def calc_dso(df_fac_ytd: pl.DataFrame, df_enc_all: pl.DataFrame, nb_jours: int) -> tuple[float, float, float]:
    """
    Calcule le DSO (Days Sales Outstanding).
    Retourne (ca_ttc_ytd, encours_ttc, dso_jours).
    """
    ca_ttc = float(df_fac_ytd["do_totalttc_f"].sum() or 0.0)
    encours_ttc = float(df_enc_all["reste"].sum() or 0.0)
    dso = round(encours_ttc / ca_ttc * nb_jours, 1) if ca_ttc > 0 else 0.0
    return ca_ttc, encours_ttc, dso


def calc_taux_impayes(df_e_all_fac: pl.DataFrame) -> tuple[int, int, float]:
    """
    Calcule le taux d'impayés.
    Retourne (nb_factures_total, nb_factures_impayees, taux_impayes_pct).
    """
    nb_total = len(df_e_all_fac)
    df_impayees = df_e_all_fac.with_columns(
        (pl.col("do_totalttc_f") - pl.col("do_montantregle_f")).alias("reste")
    ).filter(pl.col("reste") > 1.0)
    nb_impayes = len(df_impayees)
    taux = round(nb_impayes / nb_total * 100, 1) if nb_total > 0 else 0.0
    return nb_total, nb_impayes, taux


def calc_taux_retour(df_br: pl.DataFrame, df_fac: pl.DataFrame) -> tuple[int, int, float]:
    """
    Calcule le taux de retour : nb BR / nb Factures.
    Retourne (nb_bon_retour, nb_fac, taux_retour_pct).
    """
    nb_br = len(df_br)
    nb_fac = len(df_fac)
    taux = round(nb_br / nb_fac * 100, 1) if nb_fac > 0 else 0.0
    return nb_br, nb_fac, taux


def calc_taux_conversion(df_devis: pl.DataFrame, df_fac: pl.DataFrame) -> tuple[int, int, float]:
    """
    Calcule le taux de conversion Devis → Facture.
    Retourne (nb_devis, nb_bc_issus_devis, taux_conversion_pct).
    """
    nb_devis = len(df_devis)
    nb_conv = len(df_fac)
    taux = round((nb_conv / (nb_conv + nb_devis)) * 100, 1) if nb_devis > 0 else 0.0
    return nb_devis, nb_conv, taux


# ---------------------------------------------------------------------------
# KPIs depuis F_DOCLIGNE
# ---------------------------------------------------------------------------

def calc_marge_brute(df_lig_vte: pl.DataFrame) -> tuple[float, float]:
    """
    Calcule la marge brute avec coût cascade.
    Retourne (marge_brute, taux_marge_pct).
    """
    ca_ht = float(df_lig_vte["dl_montantht_f"].sum() or 0.0)
    cout_rev = float(
        (df_lig_vte["dl_qtebl_f"] * df_lig_vte["cout_unitaire_revient"]).sum() or 0.0
    )
    marge = ca_ht - cout_rev
    taux = round(marge / ca_ht * 100, 1) if ca_ht > 0 else 0.0
    return round(marge, 2), taux


def calc_top_clients(
    df_lig_vte: pl.DataFrame,
    df_enc_all: pl.DataFrame,
    df_ct: Optional[pl.DataFrame],
) -> List[Dict[str, Any]]:
    """
    Calcule le top clients par CA HT avec encours.
    Retourne une liste de dicts : ct_num, ct_intitule, ca_ht, pct_ca, encours.
    """
    if "ct_num" not in df_lig_vte.columns:
        return []

    ca_total = float(df_lig_vte["dl_montantht_f"].sum() or 1.0)
    df_top = (
        df_lig_vte
        .group_by("ct_num")
        .agg(pl.col("dl_montantht_f").sum().alias("ca_ht"))
        .sort("ca_ht", descending=True)
    )

    # Joindre intitulé client
    if df_ct is not None and "ct_intitule" in df_ct.columns:
        df_top = df_top.join(df_ct.select(["ct_num", "ct_intitule"]), on="ct_num", how="left")
    else:
        df_top = df_top.with_columns(pl.col("ct_num").alias("ct_intitule"))

    # Joindre encours par client
    df_enc_client = df_enc_all.group_by("do_tiers").agg(
        pl.col("reste").sum().alias("encours")
    )
    df_top = df_top.join(
        df_enc_client, left_on="ct_num", right_on="do_tiers", how="left"
    ).with_columns(pl.col("encours").fill_null(0.0))

    return [
        {
            "ct_num": r["ct_num"],
            "ct_intitule": r.get("ct_intitule") or r["ct_num"],
            "ca_ht": round(r["ca_ht"], 2),
            "pct_ca": round(r["ca_ht"] / ca_total * 100, 1),
            "encours": round(r["encours"], 2),
        }
        for r in df_top.to_dicts()
    ]


def calc_top_fournisseurs(
    df_e: pl.DataFrame,
    df_ct: Optional[pl.DataFrame],
) -> List[Dict[str, Any]]:
    """
    Calcule le top fournisseurs par encours (dettes non réglées).
    Retourne une liste de dicts : ct_num, ct_intitule, encours.
    """
    df_enc_fourn = df_e.filter(
        (pl.col("do_domaine") == 1) & pl.col("do_type").is_in([16, 17])
    ).with_columns(
        (pl.col("do_totalttc_f") - pl.col("do_montantregle_f")).alias("reste")
    ).filter(pl.col("reste") > 0)

    if "do_tiers" not in df_enc_fourn.columns or len(df_enc_fourn) == 0:
        return []

    df_top_f = (
        df_enc_fourn
        .group_by("do_tiers")
        .agg(pl.col("reste").sum().alias("encours"))
        .sort("encours", descending=True)
    )

    if df_ct is not None and "ct_intitule" in df_ct.columns:
        df_top_f = df_top_f.join(
            df_ct.select(["ct_num", "ct_intitule"]),
            left_on="do_tiers", right_on="ct_num", how="left"
        )
    else:
        df_top_f = df_top_f.with_columns(pl.col("do_tiers").alias("ct_intitule"))

    return [
        {
            "ct_num": r["do_tiers"],
            "ct_intitule": r.get("ct_intitule") or r["do_tiers"],
            "encours": round(r["encours"], 2),
        }
        for r in df_top_f.to_dicts()
    ]


def calc_top_familles(
    df_lig_vte: pl.DataFrame,
    df_fam_ref: Optional[pl.DataFrame],
) -> List[Dict[str, Any]]:
    """
    Calcule le top familles par CA HT (toutes familles avec CA > 0).
    Retourne une liste de dicts : fa_codefamille, fa_intitule, ca_ht, pct_ca.
    """
    if "fa_codefamille" not in df_lig_vte.columns:
        return []

    ca_total_fam = float(df_lig_vte["dl_montantht_f"].sum() or 1.0)
    df_top_fam = (
        df_lig_vte
        .filter(pl.col("fa_codefamille").is_not_null() & (pl.col("fa_codefamille") != ""))
        .group_by("fa_codefamille")
        .agg(pl.col("dl_montantht_f").sum().alias("ca_ht"))
        .filter(pl.col("ca_ht") > 0)
        .sort("ca_ht", descending=True)
    )

    # Joindre intitulé famille
    if df_fam_ref is not None:
        fam_col_name = next((c for c in ["fa_codefamille", "fa_code", "code"] if c in df_fam_ref.columns), None)
        fam_intitule_col = next((c for c in ["fa_intitule", "fa_libelle", "intitule"] if c in df_fam_ref.columns), None)
        if fam_col_name and fam_intitule_col:
            df_top_fam = df_top_fam.join(
                df_fam_ref.select([
                    pl.col(fam_col_name).cast(pl.Utf8).alias("fa_codefamille"),
                    pl.col(fam_intitule_col).alias("fa_intitule"),
                ]),
                on="fa_codefamille", how="left"
            )
        else:
            df_top_fam = df_top_fam.with_columns(pl.col("fa_codefamille").alias("fa_intitule"))
    else:
        df_top_fam = df_top_fam.with_columns(pl.col("fa_codefamille").alias("fa_intitule"))

    return [
        {
            "fa_codefamille": r["fa_codefamille"],
            "fa_intitule": r.get("fa_intitule") or r["fa_codefamille"],
            "ca_ht": round(r["ca_ht"], 2),
            "pct_ca": round(r["ca_ht"] / ca_total_fam * 100, 1),
        }
        for r in df_top_fam.to_dicts()
    ]


def calc_top_articles_par_famille(
    df_lig_vte: pl.DataFrame,
    fa_codes: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Calcule les articles les plus vendus (CA HT) par famille.
    Retourne un dict {fa_codefamille: [list d'articles]}.
    """
    articles_par_famille: Dict[str, List[Dict[str, Any]]] = {}
    for fa_code in fa_codes:
        df_fam_arts = (
            df_lig_vte
            .filter(pl.col("fa_codefamille") == fa_code)
            .group_by("ar_ref")
            .agg([
                pl.col("dl_montantht_f").sum().alias("ca_ht"),
                pl.col("dl_design").first().alias("dl_design")
                if "dl_design" in df_lig_vte.columns else pl.lit("").alias("dl_design"),
                pl.col("ar_design").first().alias("ar_design")
                if "ar_design" in df_lig_vte.columns else pl.lit("").alias("ar_design"),
            ])
            .filter(pl.col("ca_ht") > 0)
            .sort("ca_ht", descending=True)
        )
        articles_par_famille[fa_code] = [
            {
                "ar_ref": r["ar_ref"],
                "designation": r.get("dl_design") or r.get("ar_design") or r["ar_ref"],
                "ca_ht": round(r["ca_ht"], 2),
            }
            for r in df_fam_arts.to_dicts()
        ]
    return articles_par_famille
