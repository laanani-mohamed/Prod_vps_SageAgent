"""
api/bi/business_logic/stats_tiers_calculations.py

Statistiques d'un client ou d'un fournisseur sur une période (Polars, sans accès base).

Règles communes :
  - montants HT des factures (types 6/7 en vente, 16/17 en achat), avoirs déduits :
    Sage enregistre les avoirs dans ces mêmes types, avec des montants négatifs ;
  - évolution vs N-1 : (N − N-1) ÷ |N-1| × 100 ; N-1 = 0 → +100 / −100 / 0 selon le signe de N ;
  - marge : même calcul que le KPI « Marge Brute » du Tableau de Bord
    (CA HT des lignes − Σ qté livrée × coût ; coût = prix de revient, sinon CMUP, sinon prix d'achat fiche).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import polars as pl

from api.bi.repositories.archive_repo.base_bi_archive import safe_float_col
from api.bi.business_logic.analytique_calculations import (
    prepare_docligne_analytique, add_cout_cascade, calc_marge_brute,
)
from api.bi.business_logic.balance_calculations import _MOIS_FR

TOP_N = 10
# Seuils des « articles à surveiller » (fournisseur), en %
SEUIL_HAUSSE_PRIX_PCT = 5.0
SEUIL_ECART_FOURNISSEUR_PCT = 5.0


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def un_an_avant(iso: str) -> str:
    """Même jour un an plus tôt (29 février → 28 février)."""
    d = date.fromisoformat(iso)
    d = d.replace(year=d.year - 1, day=28) if (d.month, d.day) == (2, 29) else d.replace(year=d.year - 1)
    return d.isoformat()


def evolution_pct(p1: float, p2: float) -> float:
    """Évolution de p1 (référence) à p2, en %. Le montant peut être négatif (avoirs)."""
    if p1 == 0:
        return 0.0 if p2 == 0 else (100.0 if p2 > 0 else -100.0)
    return round((p2 - p1) / abs(p1) * 100, 2)


def _r(v: Optional[float], n: int = 2) -> Optional[float]:
    return None if v is None else round(float(v), n)


def _entetes(rows: List[Dict[str, Any]]) -> pl.DataFrame:
    schema = {"do_type": pl.Int64, "do_date": pl.Utf8, "do_piece": pl.Utf8,
              "do_totalht": pl.Float64, "co_no": pl.Int64, "co_fullname": pl.Utf8}
    if not rows:
        return pl.DataFrame(schema=schema)
    df = pl.from_dicts(rows, infer_schema_length=None)
    return df.with_columns(
        pl.col("do_type").cast(pl.Int64),
        safe_float_col(df, "do_totalht").alias("do_totalht"),
        pl.col("co_no").cast(pl.Int64),
    )


def _lignes(rows: List[Dict[str, Any]]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame()
    df = pl.from_dicts(rows, infer_schema_length=None)
    return df.with_columns(
        pl.col("do_type").cast(pl.Int64),
        safe_float_col(df, "dl_qte").alias("qte"),
        safe_float_col(df, "dl_montantht").alias("montant"),
        safe_float_col(df, "dl_prixunitaire").alias("prix_unitaire"),
        # Une colonne entièrement vide arrive en type Null : on force le texte
        *[pl.col(c).cast(pl.Utf8) for c in ("ar_ref", "designation", "famille", "do_date", "dl_datebc", "dl_datebl")],
    )


def _base_factures(ent: pl.DataFrame, ent_n1: pl.DataFrame, types_facture: List[int]) -> Dict[str, Any]:
    """Montant net, N-1, évolution, nb factures / avoirs, montant et taux d'avoir, facture moyenne."""
    fac = ent.filter(pl.col("do_type").is_in(types_facture))
    montant = float(fac["do_totalht"].sum() or 0.0)
    montant_n1 = float(ent_n1.filter(pl.col("do_type").is_in(types_facture))["do_totalht"].sum() or 0.0)
    positifs = fac.filter(pl.col("do_totalht") > 0)
    avoirs = fac.filter(pl.col("do_totalht") < 0)
    brut = float(positifs["do_totalht"].sum() or 0.0)
    montant_avoirs = abs(float(avoirs["do_totalht"].sum() or 0.0))  # abs : pas de « -0.0 » sans avoir
    return {
        "montant_ht": _r(montant),
        "montant_ht_n1": _r(montant_n1),
        "evolution_pct": evolution_pct(montant_n1, montant),
        "nb_factures": positifs.height,
        "nb_avoirs": avoirs.height,
        "montant_avoirs": _r(montant_avoirs),
        "taux_avoir_pct": _r(montant_avoirs / brut * 100) if brut else None,
        "facture_moyenne": _r(montant / positifs.height) if positifs.height else None,
    }


def _mois_de_la_periode(date_from: str, date_to: str) -> List[str]:
    y, m = int(date_from[:4]), int(date_from[5:7])
    y2, m2 = int(date_to[:4]), int(date_to[5:7])
    out = []
    while (y, m) <= (y2, m2):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _par_mois(ent: pl.DataFrame, types: List[int]) -> Dict[str, float]:
    fac = ent.filter(pl.col("do_type").is_in(types))
    if fac.is_empty():
        return {}
    agg = fac.group_by(pl.col("do_date").str.slice(0, 7).alias("m")).agg(pl.col("do_totalht").sum())
    return dict(zip(agg["m"].to_list(), agg["do_totalht"].to_list()))


def _mensuel(ent, ent_n1, types, date_from, date_to, marge_mois: Optional[Dict[str, float]] = None) -> List[Dict]:
    """Une ligne par mois de la période : libellé « Mois Année », montant N, montant du même mois N-1."""
    n, n1 = _par_mois(ent, types), _par_mois(ent_n1, types)
    rows = []
    for m in _mois_de_la_periode(date_from, date_to):
        m_n1 = f"{int(m[:4]) - 1:04d}{m[4:]}"
        row = {"mois": m, "libelle": f"{_MOIS_FR[int(m[5:]) - 1]} {m[:4]}",
               "montant_ht": _r(n.get(m, 0.0)), "montant_ht_n1": _r(n1.get(m_n1, 0.0))}
        if marge_mois is not None:
            row["marge"] = _r(marge_mois.get(m, 0.0))
        rows.append(row)
    return rows


def _repartition(df: pl.DataFrame, keys: List[str], total: float, top: Optional[int] = None) -> List[Dict]:
    """Qté et montant par clé, part du total (%), triés par montant décroissant."""
    if df.is_empty():
        return []
    agg = (df.group_by(keys).agg(pl.col("qte").sum(), pl.col("montant").sum())
             .filter(pl.col("montant") != 0).sort("montant", descending=True))
    if top:
        agg = agg.head(top)
    return [{**{k: r[k] for k in keys}, "qte": _r(r["qte"]), "montant_ht": _r(r["montant"]),
             "pct": _r(r["montant"] / total * 100) if total else None} for r in agg.to_dicts()]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def stats_client(rows_ent: List[Dict], rows_ent_n1: List[Dict], rows_lignes: List[Dict],
                 solde: Dict[str, Any], date_from: str, date_to: str) -> Dict:
    types = [6, 7]
    ent, ent_n1 = _entetes(rows_ent), _entetes(rows_ent_n1)
    kpis = _base_factures(ent, ent_n1, types)

    lignes = _lignes(rows_lignes)
    marge, taux_marge, marge_mois = 0.0, 0.0, {}
    if not lignes.is_empty():
        dl = add_cout_cascade(prepare_docligne_analytique(lignes))
        marge, taux_marge = calc_marge_brute(dl)
        dl = dl.with_columns(
            (pl.col("dl_montantht_f") - pl.col("dl_qtebl_f") * pl.col("cout_unitaire_revient")).alias("marge_ligne"),
            pl.col("do_date").str.slice(0, 7).alias("m"),
        )
        agg = dl.group_by("m").agg(pl.col("marge_ligne").sum())
        marge_mois = dict(zip(agg["m"].to_list(), agg["marge_ligne"].to_list()))

    nb_devis = ent.filter(pl.col("do_type") == 0).height
    derniere = solde.get("derniere_facture")
    kpis.update({
        "marge_brute": _r(marge),
        "taux_marge_pct": _r(taux_marge),
        "encours": _r(solde.get("solde") or 0.0),
        "derniere_facture": derniere,
        "nb_devis": nb_devis,
        "taux_transformation_devis_pct": (
            _r(kpis["nb_factures"] / (kpis["nb_factures"] + nb_devis) * 100) if nb_devis else None
        ),
    })

    total_lignes = float(lignes["montant"].sum() or 0.0) if not lignes.is_empty() else 0.0
    articles = lignes.filter(pl.col("ar_ref").is_not_null()) if not lignes.is_empty() else lignes
    fac = ent.filter(pl.col("do_type").is_in(types))
    commerciaux = (fac.group_by(["co_no", "co_fullname"]).agg(pl.col("do_totalht").sum().alias("montant"))
                      .sort("montant", descending=True).to_dicts()) if not fac.is_empty() else []
    return {
        "type": "client",
        "kpis": kpis,
        "mensuel": _mensuel(ent, ent_n1, types, date_from, date_to, marge_mois),
        "top_articles": _repartition(articles, ["ar_ref", "designation"], total_lignes, TOP_N),
        "familles": _repartition(lignes, ["famille"], total_lignes),
        "commerciaux": [{"co_no": c["co_no"], "commercial": c["co_fullname"], "montant_ht": _r(c["montant"]),
                         "pct": _r(c["montant"] / kpis["montant_ht"] * 100) if kpis["montant_ht"] else None}
                        for c in commerciaux],
    }


# ---------------------------------------------------------------------------
# Fournisseur
# ---------------------------------------------------------------------------

def _prix_par_article(fac_lignes: pl.DataFrame) -> pl.DataFrame:
    """
    Par article (lignes de facture, qté > 0, prix > 0) : qté, montant, prix moyen payé,
    premier et dernier prix (prix moyen du jour, date la plus ancienne / la plus récente),
    nb de dates d'achat. Prix payé = montant HT ÷ qté (remises incluses).
    """
    achats = fac_lignes.filter(pl.col("ar_ref").is_not_null() & (pl.col("qte") > 0) & (pl.col("prix_unitaire") > 0))
    if achats.is_empty():
        return pl.DataFrame()
    par_jour = (achats.group_by(["ar_ref", "do_date"])
                      .agg(pl.col("qte").sum(), pl.col("montant").sum())
                      .with_columns((pl.col("montant") / pl.col("qte")).alias("prix_jour"))
                      .sort("do_date"))
    return par_jour.group_by("ar_ref").agg(
        pl.col("qte").sum(), pl.col("montant").sum(),
        pl.col("prix_jour").first().alias("premier_prix"),
        pl.col("prix_jour").last().alias("dernier_prix"),
        pl.col("do_date").n_unique().alias("nb_dates"),
    ).with_columns(
        (pl.col("montant") / pl.col("qte")).alias("prix_moyen"),
        pl.when(pl.col("nb_dates") >= 2)
          .then((pl.col("dernier_prix") - pl.col("premier_prix")) / pl.col("premier_prix") * 100)
          .otherwise(None).alias("evolution_prix_pct"),
    )


def stats_fournisseur(rows_ent: List[Dict], rows_ent_n1: List[Dict], rows_lignes: List[Dict],
                      solde: Dict[str, Any], rows_achats: List[Dict], rows_prix_autres: List[Dict],
                      ct_num: str, date_from: str, date_to: str) -> Dict:
    types = [16, 17]
    ent, ent_n1 = _entetes(rows_ent), _entetes(rows_ent_n1)
    kpis = _base_factures(ent, ent_n1, types)

    # Part dans les achats et rang parmi les fournisseurs de la période
    achats = sorted(((r["do_tiers"], float(r["achats_ht"] or 0)) for r in rows_achats), key=lambda t: -t[1])
    total_achats = sum(v for _, v in achats)
    rang = next((i + 1 for i, (t, _) in enumerate(achats) if t == ct_num), None)
    kpis.update({
        "dettes": _r(solde.get("solde") or 0.0),
        "part_achats_pct": _r(kpis["montant_ht"] / total_achats * 100) if total_achats else None,
        "rang": rang,
        "nb_fournisseurs_actifs": len(achats),
        "nb_bons_retour": ent.filter(pl.col("do_type") == 14).height,
    })

    lignes = _lignes(rows_lignes)
    # Délai de livraison : lignes datées (BC et BL), moyenne sur celles livrées après la commande
    delai = {"nb_lignes_datees": 0, "nb_lignes_bl_apres_bc": 0, "delai_moyen_jours": None}
    if not lignes.is_empty():
        datees = lignes.filter(pl.col("dl_datebc").is_not_null() & pl.col("dl_datebl").is_not_null()).with_columns(
            (pl.col("dl_datebl").str.to_date(strict=False) - pl.col("dl_datebc").str.to_date(strict=False))
            .dt.total_days().alias("jours"))
        apres = datees.filter(pl.col("jours") > 0)
        delai = {"nb_lignes_datees": datees.height, "nb_lignes_bl_apres_bc": apres.height,
                 "delai_moyen_jours": _r(apres["jours"].mean(), 1) if apres.height else None}
    kpis.update(delai)

    fac_lignes = lignes.filter(pl.col("do_type").is_in(types)) if not lignes.is_empty() else lignes
    prix = _prix_par_article(fac_lignes) if not fac_lignes.is_empty() else pl.DataFrame()
    evol_ponderee = None
    if not prix.is_empty():
        avec = prix.filter(pl.col("evolution_prix_pct").is_not_null())
        if avec.height and float(avec["qte"].sum()):
            evol_ponderee = float((avec["evolution_prix_pct"] * avec["qte"]).sum() / avec["qte"].sum())
    kpis.update({"evolution_prix_ponderee_pct": _r(evol_ponderee),
                 "nb_articles_prix_compares": int(prix.filter(pl.col("evolution_prix_pct").is_not_null()).height)
                 if not prix.is_empty() else 0})

    designations = ({r["ar_ref"]: r["designation"] for r in fac_lignes.select(["ar_ref", "designation"]).unique("ar_ref").to_dicts()}
                    if not fac_lignes.is_empty() else {})

    # Meilleur prix moyen chez un autre fournisseur, par article
    meilleur_autre: Dict[str, Dict] = {}
    for r in rows_prix_autres:
        if r["do_tiers"] == ct_num or r["prix_moyen"] is None:
            continue
        p = float(r["prix_moyen"])
        if p > 0 and (r["ar_ref"] not in meilleur_autre or p < meilleur_autre[r["ar_ref"]]["prix"]):
            meilleur_autre[r["ar_ref"]] = {"prix": p, "fournisseur": r["fournisseur"]}

    top, surveiller = [], []
    for r in (prix.sort("montant", descending=True).to_dicts() if not prix.is_empty() else []):
        autre = meilleur_autre.get(r["ar_ref"])
        ecart = (r["prix_moyen"] - autre["prix"]) / autre["prix"] * 100 if autre else None
        row = {
            "ar_ref": r["ar_ref"], "designation": designations.get(r["ar_ref"], r["ar_ref"]),
            "qte": _r(r["qte"]), "montant_ht": _r(r["montant"]),
            "prix_moyen": _r(r["prix_moyen"]), "premier_prix": _r(r["premier_prix"]),
            "dernier_prix": _r(r["dernier_prix"]), "evolution_prix_pct": _r(r["evolution_prix_pct"]),
            "meilleur_prix_autre": _r(autre["prix"]) if autre else None,
            "fournisseur_moins_cher": autre["fournisseur"] if autre else None,
            "ecart_meilleur_prix_pct": _r(ecart),
        }
        if len(top) < TOP_N:
            top.append(row)
        motifs = []
        if r["evolution_prix_pct"] is not None and r["evolution_prix_pct"] >= SEUIL_HAUSSE_PRIX_PCT:
            motifs.append(f"hausse de prix ≥ {SEUIL_HAUSSE_PRIX_PCT:g} %")
        if ecart is not None and ecart >= SEUIL_ECART_FOURNISSEUR_PCT:
            motifs.append(f"autre fournisseur ≥ {SEUIL_ECART_FOURNISSEUR_PCT:g} % moins cher")
        if motifs:
            surveiller.append({**row, "motif": " ; ".join(motifs)})

    return {
        "type": "fournisseur",
        "kpis": kpis,
        "mensuel": _mensuel(ent, ent_n1, types, date_from, date_to),
        "top_articles": top,
        "articles_a_surveiller": surveiller,
        "seuils": {"hausse_prix_pct": SEUIL_HAUSSE_PRIX_PCT, "ecart_fournisseur_pct": SEUIL_ECART_FOURNISSEUR_PCT},
    }
