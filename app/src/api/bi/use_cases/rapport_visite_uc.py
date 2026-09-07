"""
api/bi/use_cases/rapport_visite_uc.py

Use Case : POST /api/bi/rapport/visite-client
Rapport Client Avant Visite — 7 sections :
  1. BCs en cours
  2. Factures non réglées
  3. Articles vendus par mois (6M glissants + En Cours)
  4. Familles actives (vendues dans les 6 derniers mois)
  5. Familles dormantes (vendues historiquement, pas dans les 6 derniers mois)
  6. Familles mortes (jamais vendues à ce client)
  7. Comparaison CA N vs N-1 par mois (6M glissants + En Cours)
"""
from __future__ import annotations
import logging
from datetime import date, timedelta

import polars as pl

from api.bi.schemas import RapportVisiteClientRequest, RapportResponse
from api.bi.repositories.pg_repo.bi_visite_client_repo import PgBIVisiteClientRepository

logger = logging.getLogger("api.bi.use_cases.rapport_visite")


def execute(req: RapportVisiteClientRequest) -> RapportResponse:
    repo = PgBIVisiteClientRepository()
    today = date.today()

    # Période courante : 6 mois glissants
    date_to   = req.date_to   or today.isoformat()
    date_from = req.date_from or (today - timedelta(days=180)).isoformat()

    # Période N-1 : même fenêtre, un an avant
    date_from_n1 = (today - timedelta(days=365 + 180)).isoformat()
    date_to_n1   = (today - timedelta(days=365)).isoformat()

    # Synchronise req.date_from/to pour que tous les fetch_* SQL
    # utilisent la même fenêtre 6 mois glissants.
    req.date_from = date_from
    req.date_to   = date_to

    result = {
        "bc_en_cours":          _bc_en_cours(repo, req),
        "factures_non_reglees": _factures_impayees(repo, req),
        "articles_par_mois":    _articles_pivot(repo, req, date_from, date_to),
        "familles_actives":     [],
        "familles_dormantes":   [],
        "familles_mortes":      [],
        "comparaison_ca":       _comparaison_ca(repo, req, date_from, date_to, date_from_n1, date_to_n1),
    }

    # Familles : calcul commun depuis les deux fetchs
    familles_vendues = repo.fetch_familles_vendues(req)
    toutes_familles  = repo.fetch_toutes_familles(req)
    fa, fd, fm = _classify_familles(familles_vendues, toutes_familles, date_from)
    result["familles_actives"]   = fa
    result["familles_dormantes"] = fd
    result["familles_mortes"]    = fm

    return RapportResponse(
        endpoint="/api/bi/rapport/visite-client",
        client_schema=req.client_schema,
        source="db_latest",
        total_rows=1,
        data=[result],
    )


# ── Helpers privés ────────────────────────────────────────────────────────────

def _bc_en_cours(repo, req) -> list:
    rows = repo.fetch_bc_en_cours(req)
    return [
        {
            "N° BC":        r["do_piece"],
            "Date BC":      str(r["do_date"])[:10],
            "Montant HT":   round(float(r["do_totalht"]  or 0), 2),
            "Montant TTC":  round(float(r["do_totalttc"] or 0), 2),
        }
        for r in rows
    ]


def _factures_impayees(repo, req) -> list:
    rows = repo.fetch_factures_impayees(req)
    return [
        {
            "N° Facture":   r["do_piece"],
            "Date Facture": str(r["do_date"])[:10],
            "Montant HT":   round(float(r["do_totalht"]    or 0), 2),
            "Montant TTC":  round(float(r["do_totalttc"]   or 0), 2),
            "Reste à Payer":round(float(r["reste_a_payer"] or 0), 2),
        }
        for r in rows
    ]


def _articles_pivot(repo, req, date_from: str, date_to: str) -> list:
    """
    Pivot articles × mois glissants (M6→M1 + En Cours = BC en cours do_type=1).
    Même logique de bucket que balance_calculations.py.
    """
    rows = repo.fetch_lignes_vente(req)
    if not rows:
        return []

    df = pl.from_dicts(rows, infer_schema_length=200)
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

    # En Cours = Factures du mois courant (do_type IN (6,7) et month_diff <= 0)
    # M1..M6 = Factures des 6 derniers mois
    for i in range(1, 7):
        col = f"M{i}" if i > 0 else "En Cours"
        df = df.with_columns([
            pl.when(
                (pl.col("do_type").is_in([6, 7])) & (pl.col("month_diff") == i)
            ).then(pl.col("dl_qte")).otherwise(0.0).alias(f"m{i}")
        ])

    df = df.with_columns([
        pl.when(
            (pl.col("do_type").is_in([6, 7])) & (pl.col("month_diff") <= 0)
        ).then(pl.col("dl_qte")).otherwise(0.0).alias("en_cours")
    ])

    agg = df.group_by(["ar_ref", "dl_design"]).agg([
        pl.sum("m6").alias("M6"),
        pl.sum("m5").alias("M5"),
        pl.sum("m4").alias("M4"),
        pl.sum("m3").alias("M3"),
        pl.sum("m2").alias("M2"),
        pl.sum("m1").alias("M1"),
        pl.sum("en_cours").alias("En Cours"),
    ]).rename({"ar_ref": "Référence", "dl_design": "Désignation"})

    # Afficher tous les articles (sans filtrer ceux avec qté = 0 ou négative)
    agg = agg.sort("Référence")

    return agg.to_dicts()


def _classify_familles(familles_vendues: list, toutes_familles: list, date_from: str) -> tuple:
    """
    Classifie les familles en 3 catégories :
    - Actives    : vendues ET last_date >= date_from (6M)
    - Dormantes  : vendues MAIS last_date < date_from
    - Mortes     : présentes dans le référentiel, jamais vendues à ce client
    """
    vendues_map = {r["fa_codefamille"]: r for r in familles_vendues}
    vendues_codes = set(vendues_map.keys())
    toutes_codes  = {r["fa_codefamille"] for r in toutes_familles}

    actives, dormantes = [], []
    for code, row in vendues_map.items():
        last = str(row.get("last_date", "") or "")[:10]
        ca   = round(float(row.get("ca_ht", 0) or 0), 2)
        entry = {"Code Famille": code, "Nom Famille": row.get("fa_intitule", ""), "CA HT": ca}
        if last >= date_from:
            actives.append(entry)
        else:
            dormantes.append(entry)

    toutes_map = {r["fa_codefamille"]: r["fa_intitule"] for r in toutes_familles}
    mortes = [
        {"Code Famille": code, "Nom Famille": toutes_map[code]}
        for code in toutes_codes - vendues_codes
    ]

    return (
        sorted(actives,   key=lambda x: x["CA HT"], reverse=True),
        sorted(dormantes, key=lambda x: x["CA HT"], reverse=True),
        sorted(mortes,    key=lambda x: x["Code Famille"]),
    )


def _comparaison_ca(repo, req, date_from: str, date_to: str,
                    date_from_n1: str, date_to_n1: str) -> list:
    """
    Comparaison CA HT par mois glissant (N vs N-1).
    Même logique de bucket M6..M1 + En Cours que balance.
    """
    today = date.today()
    # Remplacer date_from temporairement pour fetcher les deux périodes
    import copy
    req_n   = copy.copy(req); req_n.date_from   = date_from
    req_n1  = copy.copy(req); req_n1.date_from  = date_from_n1

    def _pivot_ca(rows: list, ref_year: int, ref_month: int) -> dict:
        empty = {f"M{i}": 0 for i in range(6, 0, -1)}
        empty["En Cours"] = 0
        if not rows:
            return empty
        df = pl.from_dicts(rows, infer_schema_length=200)
        df = df.with_columns([
            pl.col("do_date").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("date_parsed"),
            pl.col("dl_montantht").cast(pl.Float64),
        ])
        df = df.with_columns([
            ((pl.lit(ref_year) - pl.col("date_parsed").dt.year()) * 12
             + (pl.lit(ref_month) - pl.col("date_parsed").dt.month())
            ).fill_null(0).alias("month_diff")
        ])
        result = {}
        for i in range(6, 0, -1):
            total = df.filter(
                pl.col("do_type").is_in([6, 7]) & (pl.col("month_diff") == i)
            )["dl_montantht"].sum() or 0.0
            result[f"M{i}"] = round(float(total), 2)
        enc = df.filter(
            pl.col("do_type").is_in([6, 7]) & (pl.col("month_diff") <= 0)
        )["dl_montantht"].sum() or 0.0
        result["En Cours"] = round(float(enc), 2)
        return result

    rows_n  = repo.fetch_lignes_vente(req_n)
    rows_n1 = repo.fetch_lignes_vente(req_n1)

    ca_n   = _pivot_ca(rows_n,  today.year,     today.month)
    ca_n1  = _pivot_ca(rows_n1, today.year - 1, today.month)

    row_n   = {"Période": "N"};   row_n.update(ca_n)
    row_n1  = {"Période": "N-1"}; row_n1.update(ca_n1)
    return [row_n, row_n1]

