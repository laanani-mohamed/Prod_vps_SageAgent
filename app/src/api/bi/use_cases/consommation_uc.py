"""
api/bi/use_cases/consommation_uc.py

Use Case : POST /api/bi/rapport/consommation
Consommation des articles par famille/produit sur 6 mois glissants —
même logique de pivot que _articles_pivot (rapport_visite_uc.py), généralisée
à tout le client (pas un seul tiers) et enrichie d'un récapitulatif par famille.
"""
from __future__ import annotations
import logging
from datetime import date

import polars as pl

from api.bi.schemas import RapportConsommationRequest, RapportResponse
from api.bi.repositories.pg_repo.bi_consommation_repo import PgBIConsommationRepository
from api.bi.business_logic.balance_calculations import _decale_mois, _label_mois_annee

logger = logging.getLogger("api.bi.use_cases.consommation")


def execute(req: RapportConsommationRequest) -> RapportResponse:
    repo = PgBIConsommationRepository()
    today = date.today()

    # Du 1er jour du mois M6 (6 mois complets + mois en cours) jusqu'à aujourd'hui
    y6, m6 = _decale_mois(today.year, today.month, 6)
    req.date_to   = req.date_to   or today.isoformat()
    req.date_from = req.date_from or date(y6, m6, 1).isoformat()

    rows = repo.fetch(req)
    par_famille, par_article = _pivot_consommation(rows)

    return RapportResponse(
        endpoint="/api/bi/rapport/consommation",
        client_schema=req.client_schema,
        source="db_latest",
        total_rows=1,
        data=[{"par_famille": par_famille, "par_article": par_article}],
    )


def _pivot_consommation(rows: list) -> tuple:
    """
    Pivot articles × mois glissants (Mois en cours, M1..M6) avec Total Consommation
    (somme des 7 colonnes mois) et Moyenne / Mois (6 mois complets ÷ 6, mois en cours
    exclu), plus récapitulatif
    par famille (quantité totale sur la fenêtre). Seules les lignes dont le total
    est non nul sont gardées. Même logique de bucket que _articles_pivot
    (rapport_visite_uc.py).
    """
    if not rows:
        return [], []

    df = pl.from_dicts(rows, infer_schema_length=500)
    df = df.with_columns([
        pl.col("do_date").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("date_parsed"),
        pl.col("dl_qte").cast(pl.Float64),
    ])

    today = date.today()
    cy, cm = today.year, today.month

    df = df.with_columns([
        ((pl.lit(cy) - pl.col("date_parsed").dt.year()) * 12
         + (pl.lit(cm) - pl.col("date_parsed").dt.month())
        ).fill_null(0).alias("month_diff"),
    ])

    df = df.with_columns([
        pl.when(pl.col("month_diff") <= 0).then(pl.col("dl_qte")).otherwise(0.0).alias("mois_en_cours"),
    ])
    for i in range(1, 7):
        df = df.with_columns([
            pl.when(pl.col("month_diff") == i).then(pl.col("dl_qte")).otherwise(0.0).alias(f"m{i}"),
        ])

    # Colonnes du plus ancien (M6) au plus récent (mois en cours)
    mois_complets = [f"m{i}" for i in range(6, 0, -1)]
    month_cols = mois_complets + ["mois_en_cours"]

    # Libellés "Mois Année" pour M6..M1, calculés par rapport au mois en cours
    labels = {f"m{d}": _label_mois_annee(cy, cm, d) for d in range(1, 7)}

    # Articles mouvementés uniquement : total non nul (arrondi pour écarter les résidus flottants)
    par_article = (
        df.group_by(["fa_codefamille", "fa_intitule", "ar_ref", "ar_design"])
        .agg([pl.sum(c).alias(c) for c in month_cols])
        .with_columns(pl.sum_horizontal(month_cols).alias("Total Consommation"))
        # Moyenne sur les 6 mois complets : le mois en cours (incomplet) est exclu
        .with_columns((pl.sum_horizontal(mois_complets) / len(mois_complets)).alias("Moyenne / Mois"))
        .filter(pl.col("Total Consommation").round(3) != 0)
        .rename({
            "fa_intitule": "Famille", "ar_ref": "Réf. Article", "ar_design": "Article",
            "mois_en_cours": "Mois en cours",
            "m1": labels["m1"], "m2": labels["m2"], "m3": labels["m3"],
            "m4": labels["m4"], "m5": labels["m5"], "m6": labels["m6"],
        })
        .sort(["Famille", "Article"])
        .drop("fa_codefamille")
        .to_dicts()
    )

    par_famille = (
        df.group_by(["fa_codefamille", "fa_intitule"])
        .agg(pl.sum("dl_qte").alias("Qté Totale Consommée"))
        .filter(pl.col("Qté Totale Consommée").round(3) != 0)
        .rename({"fa_intitule": "Famille"})
        .sort("Qté Totale Consommée", descending=True)
        .drop("fa_codefamille")
        .to_dicts()
    )

    return par_famille, par_article
