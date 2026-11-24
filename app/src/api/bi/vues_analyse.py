"""
api/bi/vues_analyse.py — Indicateurs ajoutés au front (refonte « verre ») : compléments du Tableau de Bord
et onglets « Analyse » des Ventes et des Achats. Branchés sur POST /api/bi/vues/{nom} (VUES de vues.py).

Mêmes règles que le reste de l'API :
  - CA / achats = HT des factures (ventes 6 et 7, achats 16 et 17), avoirs déduits : Sage enregistre les avoirs
    dans ces mêmes types, avec un montant négatif (stats_tiers_calculations) ;
  - nombre de factures = factures de montant positif ; avoir = facture de montant négatif ;
  - commercial = co_no de l'entête (0 ou vide → « Non identifié ») ; un collaborateur ne voit que ses pièces ;
  - marge = CA HT des lignes − Σ qté livrée × coût, coût = prix de revient, sinon CMUP, sinon prix d'achat fiche
    (KPI « Marge brute » du Tableau de Bord, analytique_calculations.add_cout_cascade) ;
  - reste dû (TTC) = TTC − réglé ; impayé si > 1 MAD (taux d'impayés) ; ancienneté sur la date de facture
    (balance âgée, tranche « +90 j ») ;
  - rupture = stock total ≤ 0 (alerte de stock), ici tous dépôts additionnés ;
  - délai de livraison = date BL − date BC des lignes livrées après la commande (fiche fournisseur) ;
  - évolution du prix d'un article = dernier / premier prix payé du jour (montant ÷ qté), ≥ 2 dates d'achat,
    moyenne pondérée par les quantités (fiche fournisseur, « Évolution des prix »).
Calculs en cache jusqu'au prochain ETL (api.common.cache.memo).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from api.bi.business_logic.stats_tiers_calculations import un_an_avant
from api.bi.repositories.pg_repo.sql_helpers import validate_schema
from api.common.cache import memo
from api.db import get_db_connection

OBJECTIF_CA = 10_000_000.0          # même objectif annuel que objectifs_uc.OBJECTIF_CA
SEUIL_IMPAYE = 1.0                  # MAD : reste dû au-delà duquel une facture est impayée (taux d'impayés)
JOURS_IMPAYE = 90                   # balance âgée : tranche « +90 j »
JOURS_INACTIF = 90                  # client qui n'achète plus : aucune facture depuis 90 jours…
JOURS_HISTORIQUE = 365              # … alors qu'il en avait dans les 12 mois
PART_CLASSE_A = 80.0                # classe A : articles qui font 80 % du CA HT des 12 derniers mois
TOLERANCE_DELAI = 7                 # jours : livraison « régulière » si son délai est à ± 7 j du délai médian du fournisseur
                                    # (Sage ne garde pas de date de livraison promise : pas de « à temps » possible)
PART_MIN_FAMILLE = 0.5              # % des achats : familles plus petites écartées de l'inflation (prix non significatifs)
TOP = 10


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def _sql(sql: str, params: list | None = None) -> pd.DataFrame:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or [])
        return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])


def _perimetre(co_no: list, alias: str = "e") -> tuple[str, list]:
    """Filtre commercial de l'entête (collaborateur : imposé par le jeton ; directeur : filtre facultatif)."""
    return (f" AND COALESCE({alias}.co_no, 0) = ANY(%s)", [list(map(int, co_no))]) if co_no else ("", [])


def _num(df: pd.DataFrame, *colonnes) -> pd.DataFrame:
    for c in colonnes:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)
    return df


def _r(v, n=2):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), n)


def _periode(f: dict) -> tuple[str, str]:
    du, au = str(f["date_from"])[:10], str(f["date_to"])[:10]
    date.fromisoformat(du), date.fromisoformat(au)   # ValueError → 400
    if du > au:
        raise ValueError("La date de début doit précéder la date de fin")
    return du, au


def _cout(df: pd.DataFrame) -> pd.Series:
    """Coût unitaire de revient : prix de revient, sinon CMUP, sinon prix d'achat de la fiche article."""
    return df["dl_prixru"].where(df["dl_prixru"] > 0, df["dl_cmup"].where(df["dl_cmup"] > 0, df["ar_prixach"]))


def _noms_commerciaux(schema: str) -> dict:
    df = memo(schema, "analyse|collaborateurs", lambda: _sql(
        f"SELECT co_no, co_nom, co_prenom FROM {validate_schema(schema)}.f_collaborateur"))
    noms = {}
    for r in df.itertuples():
        nom = " ".join(str(x).strip() for x in [r.co_nom, r.co_prenom] if isinstance(x, str) and x.strip())
        noms[int(r.co_no)] = nom or f"Commercial {int(r.co_no)}"
    return noms


def _nom_commercial(co: int, noms: dict) -> str:
    return "Non identifié" if int(co) == 0 else noms.get(int(co), f"Commercial {int(co)}")


def _entetes(schema: str, domaine: int, types: list, co_no: list) -> pd.DataFrame:
    """Entêtes de factures de tout l'historique (date, tiers, HT, TTC, réglé, commercial), en cache."""
    s = validate_schema(schema)
    filtre, p = _perimetre(co_no)

    def lire():
        df = _sql(f"""SELECT e.do_piece, e.do_type, e.do_date::date AS d, e.do_tiers, COALESCE(e.co_no, 0) AS co_no,
                             e.do_totalht AS ht, e.do_totalttc AS ttc, COALESCE(e.do_montantregle, 0) AS regle
                      FROM {s}.f_docentete e WHERE e.do_domaine = %s AND e.do_type = ANY(%s){filtre}""",
                  [domaine, types] + p)
        df = _num(df, "ht", "ttc", "regle")
        df["d"] = pd.to_datetime(df["d"])
        return df
    return memo(schema, f"analyse|entetes|{domaine}|{types}|{sorted(co_no or [])}", lire).copy()


def _lignes(schema: str, domaine: int, types: list, du: str, au: str, co_no: list) -> pd.DataFrame:
    """Lignes des pièces de la période (date de l'entête), avec famille, coût et commercial de l'entête."""
    s = validate_schema(schema)
    filtre, p = _perimetre(co_no)

    def lire():
        df = _sql(f"""SELECT l.do_type, e.do_piece, e.do_date::date AS d, e.do_tiers, COALESCE(e.co_no, 0) AS co_no,
                             e.do_totalht AS ht_piece, l.ar_ref,
                             COALESCE(NULLIF(TRIM(a.ar_design), ''), l.dl_design, l.ar_ref) AS designation,
                             COALESCE(a.fa_codefamille, '') AS fa_code,
                             COALESCE(NULLIF(TRIM(fa.fa_intitule), ''), NULLIF(a.fa_codefamille, ''), 'Sans famille') AS famille,
                             l.dl_qte, l.dl_qtebl, l.dl_montantht, l.dl_prixunitaire, l.dl_prixru, l.dl_cmup, a.ar_prixach,
                             l.dl_datebc::date AS datebc, l.dl_datebl::date AS datebl, NULLIF(TRIM(l.dl_piecebc), '') AS piecebc
                      FROM {s}.f_docligne l
                      JOIN {s}.f_docentete e ON e.do_domaine = l.do_domaine AND e.do_type = l.do_type AND e.do_piece = l.do_piece
                      LEFT JOIN {s}.f_article a ON a.ar_ref = l.ar_ref
                      LEFT JOIN {s}.f_famille fa ON fa.fa_codefamille = a.fa_codefamille
                      WHERE e.do_domaine = %s AND e.do_type = ANY(%s) AND e.do_date::date BETWEEN %s AND %s{filtre}""",
                  [domaine, types, du, au] + p)
        return _num(df, "ht_piece", "dl_qte", "dl_qtebl", "dl_montantht", "dl_prixunitaire", "dl_prixru", "dl_cmup", "ar_prixach")
    return memo(schema, f"analyse|lignes|{domaine}|{types}|{du}|{au}|{sorted(co_no or [])}", lire).copy()


def _marges(lignes: pd.DataFrame, cle: str) -> pd.DataFrame:
    """CA HT, coût, marge et taux de marge par `cle`, du plus gros CA au plus petit ;
    ca_sans_cout : CA des lignes sans aucun coût connu (marge surestimée d'autant)."""
    if lignes.empty:
        return pd.DataFrame(columns=[cle, "ca", "cout", "marge", "taux", "ca_sans_cout"])
    sans = _cout(lignes) <= 0
    l = lignes.assign(cout=lignes["dl_qtebl"] * _cout(lignes), ca_sans_cout=lignes["dl_montantht"].where(sans, 0.0))
    g = l.groupby(cle).agg(ca=("dl_montantht", "sum"), cout=("cout", "sum"), ca_sans_cout=("ca_sans_cout", "sum")).reset_index()
    g["marge"] = g["ca"] - g["cout"]
    g["taux"] = np.where(g["ca"] > 0, g["marge"] / g["ca"] * 100, np.nan)
    return g.sort_values("ca", ascending=False)


def _enregistrements(df: pd.DataFrame, colonnes: dict) -> list:
    """Lignes de `df` en dicts {nom de sortie : valeur arrondie}, NaN → null."""
    out = []
    for r in df.to_dict("records"):
        out.append({k: (_r(r[c]) if isinstance(r[c], (float, np.floating)) else (int(r[c]) if isinstance(r[c], (np.integer,)) else r[c]))
                    for k, c in colonnes.items()})
    return out


# ---------------------------------------------------------------------------
# Tableau de bord : panier moyen, rythme, alertes, top commerciaux
# ---------------------------------------------------------------------------
def tdb_plus(schema: str, f: dict, co_no: list) -> dict:
    du, au = _periode(f)
    du1, au1 = un_an_avant(du), un_an_avant(au)
    fac = _entetes(schema, 0, [6, 7], co_no)
    dans = lambda a, b: fac[(fac["d"] >= a) & (fac["d"] <= b)]   # noqa: E731

    # Panier moyen = CA HT net ÷ nombre de factures (positives), N et même période N-1
    def panier(a, b):
        p = dans(a, b)
        nb = int((p["ht"] > 0).sum())
        return float(p["ht"].sum()), nb, (float(p["ht"].sum()) / nb if nb else None)
    ca, nb, pm = panier(du, au)
    ca1, nb1, pm1 = panier(du1, au1)
    du2, au2 = un_an_avant(du1), un_an_avant(au1)
    ca2 = float(dans(du2, au2)["ht"].sum())   # CA de la même période deux ans avant (N-2)

    # Rythme : CA par jour écoulé de la période ; requis : reste de l'objectif annuel ÷ jours restants de l'année
    d_du, d_au = date.fromisoformat(du), date.fromisoformat(au)
    jours = (d_au - d_du).days + 1
    fin_annee = date(d_au.year, 12, 31)
    meme_annee = d_du.year == d_au.year
    restants = (fin_annee - d_au).days
    rythme = {"jours_ecoules": jours, "jours_restants": restants if meme_annee else None,
              "actuel": _r(ca / jours) if jours > 0 else None,
              "requis": _r(max(OBJECTIF_CA - ca, 0.0) / restants) if meme_annee and restants > 0 else None,
              "objectif": OBJECTIF_CA if meme_annee else None}

    # Alerte 1 : clients avec un reste dû sur des factures de plus de 90 jours (à aujourd'hui, comme la balance âgée)
    limite = pd.Timestamp(date.today() - timedelta(days=JOURS_IMPAYE))
    vieux = fac[(fac["d"] < limite) & ((fac["ttc"] - fac["regle"]) > SEUIL_IMPAYE)]
    par_client = (vieux["ttc"] - vieux["regle"]).groupby(vieux["do_tiers"]).sum()
    impayes = {"clients": int((par_client > 0).sum()), "montant_ttc": _r(par_client[par_client > 0].sum()), "jours": JOURS_IMPAYE}

    # Alerte 2 : clients qui n'achètent plus (factures dans les 12 mois avant `au`, aucune depuis 90 jours)
    ventes = fac[fac["ht"] > 0]
    t_au = pd.Timestamp(au)
    recents = set(ventes[(ventes["d"] > t_au - pd.Timedelta(days=JOURS_INACTIF)) & (ventes["d"] <= t_au)]["do_tiers"])
    avant = ventes[(ventes["d"] > t_au - pd.Timedelta(days=JOURS_HISTORIQUE)) & (ventes["d"] <= t_au - pd.Timedelta(days=JOURS_INACTIF))]
    perdus = avant[~avant["do_tiers"].isin(recents)]
    inactifs = {"clients": int(perdus["do_tiers"].nunique()), "ca_ht_12_mois": _r(perdus["ht"].sum()),
                "jours": JOURS_INACTIF}

    # Top commerciaux : CA HT et marge des lignes de factures, clients distincts (factures de la période)
    lignes = _lignes(schema, 0, [6, 7], du, au, co_no)
    noms = _noms_commerciaux(schema)
    m = _marges(lignes, "co_no")
    nb_cli = dans(du, au)[lambda x: x["ht"] > 0].groupby("co_no")["do_tiers"].nunique()
    total_ca = float(m["ca"].sum()) if not m.empty else 0.0
    commerciaux = [{"co_no": int(r.co_no), "nom": _nom_commercial(r.co_no, noms), "ca_ht": _r(r.ca), "marge": _r(r.marge),
                    "taux_marge": _r(r.taux, 1), "clients": int(nb_cli.get(r.co_no, 0)),
                    "part_ca": _r(r.ca / total_ca * 100, 1) if total_ca else None}
                   for r in m.head(TOP).itertuples()]
    return {
        "periode": {"du": du, "au": au},
        "panier": {"ca_ht": _r(ca), "factures": nb, "panier_moyen": _r(pm),
                   "ca_ht_n1": _r(ca1), "factures_n1": nb1, "panier_moyen_n1": _r(pm1),
                   "evolution_pct": _r((pm - pm1) / abs(pm1) * 100, 1) if pm is not None and pm1 else None},
        "historique": [{"du": du1, "au": au1, "ca_ht": _r(ca1), "evolution_pct": _r((ca - ca1) / abs(ca1) * 100, 1) if ca1 else None},
                       {"du": du2, "au": au2, "ca_ht": _r(ca2), "evolution_pct": _r((ca - ca2) / abs(ca2) * 100, 1) if ca2 else None}],
        "rythme": rythme,
        "alertes": {"impayes_90": impayes, "clients_inactifs": inactifs},
        "commerciaux": commerciaux,
    }


def ruptures_a(schema: str, f: dict, co_no: list) -> dict:
    """Articles de classe A (80 % du CA HT des 12 mois avant `date_to`) sans stock, tous dépôts additionnés."""
    au = _periode({"date_from": f.get("date_from") or f["date_to"], "date_to": f["date_to"]})[1]
    s = validate_schema(schema)

    def calcul():
        df = _sql(f"""WITH ventes AS (
                          SELECT l.ar_ref, SUM(l.dl_montantht) AS ca FROM {s}.f_docligne l
                          JOIN {s}.f_docentete e ON e.do_domaine = l.do_domaine AND e.do_type = l.do_type AND e.do_piece = l.do_piece
                          WHERE e.do_domaine = 0 AND e.do_type IN (6, 7) AND l.ar_ref IS NOT NULL
                            AND e.do_date::date > %s::date - 365 AND e.do_date::date <= %s::date
                          GROUP BY l.ar_ref HAVING SUM(l.dl_montantht) > 0)
                      SELECT v.ar_ref, a.ar_design, COALESCE(a.ar_sommeil, 0) AS sommeil, v.ca,
                             COALESCE((SELECT SUM(st.as_qtesto) FROM {s}.f_artstock st WHERE st.ar_ref = v.ar_ref), 0) AS stock
                      FROM ventes v LEFT JOIN {s}.f_article a ON a.ar_ref = v.ar_ref""", [au, au])
        df = _num(df, "ca", "stock").sort_values("ca", ascending=False)
        total = float(df["ca"].sum())
        cumul_avant = df["ca"].cumsum().shift(fill_value=0.0) / total * 100 if total else df["ca"] * 0
        classe_a = df[cumul_avant < PART_CLASSE_A]          # inclut l'article qui franchit les 80 %
        rupt = classe_a[(classe_a["stock"] <= 0) & (classe_a["sommeil"] != 1)]
        return {"au": au, "articles_classe_a": int(len(classe_a)), "ruptures": int(len(rupt)),
                "ca_ht_12_mois": _r(rupt["ca"].sum()),
                "exemples": [{"ar_ref": r.ar_ref, "designation": r.ar_design, "ca_ht_12_mois": _r(r.ca), "stock": _r(r.stock)}
                             for r in rupt.head(5).itertuples()]}
    return memo(schema, f"analyse|ruptures_a|{au}", calcul)


# ---------------------------------------------------------------------------
# Ventes : onglet « Analyse »
# ---------------------------------------------------------------------------
def analyse_ventes(schema: str, f: dict, co_no: list) -> dict:
    du, au = _periode(f)
    du1, au1 = un_an_avant(du), un_an_avant(au)
    fac = _entetes(schema, 0, [6, 7], co_no)
    ventes = fac[fac["ht"] > 0]
    t = lambda x: pd.Timestamp(x)   # noqa: E731
    p_n = ventes[(ventes["d"] >= t(du)) & (ventes["d"] <= t(au))]
    p_n1 = ventes[(ventes["d"] >= t(du1)) & (ventes["d"] <= t(au1))]
    actifs_n, actifs_n1 = set(p_n["do_tiers"]), set(p_n1["do_tiers"])
    premiere = ventes.groupby("do_tiers")["d"].min()
    nouveaux = {c for c in actifs_n if premiere.get(c) is not None and premiere[c] >= t(du)}
    perdus = actifs_n1 - actifs_n
    reactives = actifs_n - actifs_n1 - nouveaux
    ca_n = p_n.groupby("do_tiers")["ht"].sum()
    ca_n1 = p_n1.groupby("do_tiers")["ht"].sum()
    net_n = fac[(fac["d"] >= t(du)) & (fac["d"] <= t(au))].groupby("do_tiers")["ht"].sum()
    acquisition = {
        "actifs_n": len(actifs_n), "actifs_n1": len(actifs_n1),
        "nouveaux": len(nouveaux), "ca_nouveaux": _r(net_n.reindex(list(nouveaux)).sum()),
        "perdus": len(perdus), "ca_perdus_n1": _r(ca_n1.reindex(list(perdus)).sum()),
        "reactives": len(reactives), "ca_reactives": _r(net_n.reindex(list(reactives)).sum()),
        "fideles": len(actifs_n & actifs_n1),
    }
    del ca_n
    s = validate_schema(schema)
    intitules = memo(schema, "analyse|intitules", lambda: _sql(f"SELECT ct_num, ct_intitule FROM {s}.f_comptet")) \
        .set_index("ct_num")["ct_intitule"].to_dict()
    noms = _noms_commerciaux(schema)

    # Listes : perdus (CA N-1, dernière facture) et gagnés (CA HT net de la période, 1re facture de la période),
    # du plus gros CA au plus petit ; commercial = celui de la dernière facture du client jusqu'à la fin de la période
    jusqu_au = ventes[ventes["d"] <= t(au)].sort_values("d")
    derniere = jusqu_au.groupby("do_tiers")["d"].max()
    dernier_co = jusqu_au.groupby("do_tiers")["co_no"].last()
    premiere_n = p_n.groupby("do_tiers")["d"].min()
    fiche = lambda c, ca, d: {"code": c, "nom": _nom_tiers(intitules, c), "ca_ht": _r(ca), "date": str(d.date()),   # noqa: E731
                              "commercial": _nom_commercial(dernier_co[c], noms)}
    clients_perdus = [fiche(c, ca_n1[c], derniere[c]) for c in sorted(perdus, key=lambda c: -ca_n1[c])]
    clients_gagnes = [{**fiche(c, net_n.get(c, 0.0), premiere_n[c]), "statut": "nouveau" if c in nouveaux else "réactivé"}
                      for c in sorted(nouveaux | reactives, key=lambda c: -net_n.get(c, 0.0))]

    # Concentration des clients : CA HT net (avoirs déduits) par client sur la période
    concentration = _concentration(net_n[net_n > 0].sort_values(ascending=False), intitules)

    # Marges (lignes de factures de la période)
    lignes = _lignes(schema, 0, [6, 7], du, au, co_no)
    mc = _marges(lignes, "co_no")
    mc["nom"] = [_nom_commercial(c, noms) for c in mc["co_no"]]
    mf = _marges(lignes, "famille")
    art = lignes.assign(article=lignes["ar_ref"].fillna("") + " · " + lignes["designation"].fillna(""))
    ma = _marges(art[art["ar_ref"].notna()], "article")
    cols = {"nom": "nom", "ca_ht": "ca", "marge": "marge", "taux_marge": "taux", "ca_sans_cout": "ca_sans_cout"}
    tot = _marges(lignes.assign(tout="tout"), "tout")
    marges = {
        "total": {"ca_ht": _r(tot["ca"].sum()), "marge": _r(tot["marge"].sum()),
                  "taux_marge": _r(tot["marge"].sum() / tot["ca"].sum() * 100, 1) if float(tot["ca"].sum() or 0) > 0 else None},
        "commerciaux": _enregistrements(mc.head(TOP), cols),
        "familles": _enregistrements(mf.rename(columns={"famille": "nom"}).head(TOP), cols),
        "articles": _enregistrements(ma.rename(columns={"article": "nom"}).head(TOP), cols),
    }

    # Avoirs et retours : par client (factures, avoirs, bons de retour type 4) et par article (quantités)
    periode = fac[(fac["d"] >= t(du)) & (fac["d"] <= t(au))]
    filtre, p = _perimetre(co_no)
    br = _sql(f"""SELECT e.do_tiers, e.do_piece FROM {s}.f_docentete e
                  WHERE e.do_domaine = 0 AND e.do_type = 4 AND e.do_date::date BETWEEN %s AND %s{filtre}""", [du, au] + p)
    lignes_br = _lignes(schema, 0, [4], du, au, co_no)
    cl = pd.DataFrame({
        "factures": periode[periode["ht"] > 0].groupby("do_tiers").size(),
        "brut": periode[periode["ht"] > 0].groupby("do_tiers")["ht"].sum(),
        "avoirs": periode[periode["ht"] < 0].groupby("do_tiers").size(),
        "montant_avoirs": -periode[periode["ht"] < 0].groupby("do_tiers")["ht"].sum(),
        "retours": br.groupby("do_tiers").size() if not br.empty else pd.Series(dtype=float),
    }).fillna(0)
    cl = cl[(cl["avoirs"] > 0) | (cl["retours"] > 0)]
    cl["taux_avoirs"] = np.where(cl["brut"] > 0, cl["montant_avoirs"] / cl["brut"] * 100, np.nan)
    cl["taux_retours"] = np.where(cl["factures"] > 0, cl["retours"] / cl["factures"] * 100, np.nan)
    cl = cl.sort_values(["montant_avoirs", "retours"], ascending=False).reset_index().rename(columns={"index": "do_tiers"})
    cl["nom"] = cl["do_tiers"].map(intitules).fillna(cl["do_tiers"])
    clients_av = [{"code": r.do_tiers, "nom": r.nom, "factures": int(r.factures), "avoirs": int(r.avoirs),
                   "montant_avoirs": _r(r.montant_avoirs), "taux_avoirs": _r(r.taux_avoirs, 1),
                   "retours": int(r.retours), "taux_retours": _r(r.taux_retours, 1)} for r in cl.head(15).itertuples()]
    l_av = lignes[(lignes["ht_piece"] < 0) & lignes["ar_ref"].notna()]
    l_ve = lignes[(lignes["ht_piece"] > 0) & lignes["ar_ref"].notna()]
    ar = pd.DataFrame({
        "designation": pd.concat([l_ve, l_av, lignes_br]).groupby("ar_ref")["designation"].first(),
        "qte_vendue": l_ve.groupby("ar_ref")["dl_qte"].sum(),
        "qte_avoir": l_av.groupby("ar_ref")["dl_qte"].sum().abs(),
        "montant_avoir": l_av.groupby("ar_ref")["dl_montantht"].sum().abs(),
        "qte_retour": lignes_br[lignes_br["ar_ref"].notna()].groupby("ar_ref")["dl_qte"].sum().abs() if not lignes_br.empty else pd.Series(dtype=float),
    })
    for c in ["qte_vendue", "qte_avoir", "montant_avoir", "qte_retour"]:
        ar[c] = ar[c].fillna(0.0)
    ar = ar[(ar["qte_avoir"] > 0) | (ar["qte_retour"] > 0)]
    ar["taux_avoir"] = np.where(ar["qte_vendue"] > 0, ar["qte_avoir"] / ar["qte_vendue"] * 100, np.nan)
    ar["taux_retour"] = np.where(ar["qte_vendue"] > 0, ar["qte_retour"] / ar["qte_vendue"] * 100, np.nan)
    ar = ar.sort_values(["montant_avoir", "qte_retour"], ascending=False).reset_index().rename(columns={"index": "ar_ref"})
    articles_av = [{"ar_ref": r.ar_ref, "designation": r.designation, "qte_vendue": _r(r.qte_vendue), "qte_avoir": _r(r.qte_avoir),
                    "montant_avoir": _r(r.montant_avoir), "taux_avoir": _r(r.taux_avoir, 1),
                    "qte_retour": _r(r.qte_retour), "taux_retour": _r(r.taux_retour, 1)} for r in ar.head(15).itertuples()]
    brut = float(periode[periode["ht"] > 0]["ht"].sum())
    totaux_av = {"factures": int((periode["ht"] > 0).sum()), "avoirs": int((periode["ht"] < 0).sum()),
                 "montant_avoirs": _r(-periode[periode["ht"] < 0]["ht"].sum()),
                 "taux_avoirs": _r(-periode[periode["ht"] < 0]["ht"].sum() / brut * 100, 1) if brut else None,
                 "retours": int(len(br)), "taux_retours": _r(len(br) / int((periode["ht"] > 0).sum()) * 100, 1) if (periode["ht"] > 0).any() else None}

    # Saisonnalité : CA HT net par mois, 3 dernières années (année de `au` et les deux précédentes)
    annees = [int(au[:4]) - 2, int(au[:4]) - 1, int(au[:4])]
    s_df = fac[fac["d"].dt.year.isin(annees)]
    grille = s_df.groupby([s_df["d"].dt.year, s_df["d"].dt.month])["ht"].sum()
    saison = [{"annee": a, "mois": [(_r(grille.get((a, m))) if (a, m) in grille.index else None) for m in range(1, 13)],
               "total": _r(sum(grille.get((a, m), 0.0) for m in range(1, 13)))} for a in annees]

    return {"periode": {"du": du, "au": au, "du_n1": du1, "au_n1": au1}, "acquisition": acquisition,
            "clients_perdus": clients_perdus, "clients_gagnes": clients_gagnes, "concentration": concentration,
            "marges": marges, "avoirs_retours": {"totaux": totaux_av, "clients": clients_av, "articles": articles_av}, "saisonnalite": saison}


def _nom_tiers(intitules: dict, code: str) -> str:
    """Intitulé du tiers (F_COMPTET), sinon son code."""
    nom = intitules.get(code)
    return nom.strip() if isinstance(nom, str) and nom.strip() else code


def _concentration(par_c: pd.Series, intitules: dict) -> dict:
    """Clients classés par CA HT décroissant : HHI (Σ part² en %), nombre de clients pour 80 % du CA,
    tranches de 10 % des clients (Pareto), 5 premiers clients, puis CA du 6ᵉ au dernier des 80 % et des autres (répartition)."""
    total, n = float(par_c.sum()), len(par_c)
    if not total:
        return {"total_ht": 0.0, "clients": 0, "hhi": None, "nb_pour_80": 0, "tranches": [], "premiers": [], "ca_jusqu_80": 0.0, "ca_autres": 0.0}
    cumul = par_c.cumsum() / total * 100
    n80 = int((cumul.shift(fill_value=0.0) < 80).sum())
    bornes = [int(n * k / 10 + 0.5) for k in range(11)]   # 302 clients → 1-30, 31-60, 61-91…
    tranches = [{"de": a + 1, "a": b, "ca_ht": _r(par_c.iloc[a:b].sum()), "part": _r(par_c.iloc[a:b].sum() / total * 100, 2),
                 "cumul": _r(cumul.iloc[b - 1], 2)} for a, b in zip(bornes, bornes[1:]) if b > a]
    premiers = [{"code": c, "nom": _nom_tiers(intitules, c), "ca_ht": _r(v), "part": _r(v / total * 100, 2)} for c, v in par_c.head(5).items()]
    return {"total_ht": _r(total), "clients": n, "hhi": _r(float(((par_c / total * 100) ** 2).sum()), 1), "nb_pour_80": n80,
            "tranches": tranches, "premiers": premiers,
            "ca_jusqu_80": _r(par_c.iloc[5:n80].sum()) if n80 > 5 else 0.0, "ca_autres": _r(par_c.iloc[max(n80, 5):].sum())}


# ---------------------------------------------------------------------------
# Achats : onglet « Analyse » (directeur)
# ---------------------------------------------------------------------------
def analyse_achats(schema: str, f: dict, co_no: list) -> dict:
    du, au = _periode(f)
    s = validate_schema(schema)
    intitules = memo(schema, "analyse|intitules", lambda: _sql(f"SELECT ct_num, ct_intitule FROM {s}.f_comptet")) \
        .set_index("ct_num")["ct_intitule"].to_dict()

    # Dépendance : achats HT nets par fournisseur, part et cumul (Pareto)
    fac = _entetes(schema, 1, [16, 17], co_no)
    per = fac[(fac["d"] >= pd.Timestamp(du)) & (fac["d"] <= pd.Timestamp(au))]
    par_f = per.groupby("do_tiers")["ht"].sum()
    par_f = par_f[par_f > 0].sort_values(ascending=False)
    total = float(par_f.sum())
    cumul = (par_f.cumsum() / total * 100) if total else par_f * 0
    n80 = int((cumul.shift(fill_value=0.0) < 80).sum()) if total else 0
    # tous les fournisseurs (Pareto, répartition) ; HHI = Σ part² (en %) : < 1 500 faible, 1 500-2 500 modérée, > 2 500 forte
    fournisseurs = [{"code": c, "nom": (intitules.get(c) or c).strip(), "achats_ht": _r(v), "part": _r(v / total * 100, 2),
                     "cumul": _r(cumul[c], 2)} for c, v in par_f.items()]
    dependance = {"total_ht": _r(total), "fournisseurs_actifs": int(len(par_f)),
                  "hhi": _r(float(((par_f / total * 100) ** 2).sum()), 1) if total else None,
                  "part_premier": _r(par_f.iloc[0] / total * 100, 2) if total else None,
                  "premier": fournisseurs[0]["nom"] if fournisseurs else None,
                  "nb_pour_80": n80, "part_5_premiers": _r(par_f.head(5).sum() / total * 100, 1) if total else None,
                  "fournisseurs": fournisseurs}

    # Inflation par famille : évolution du prix de chaque article (premier → dernier prix du jour), pondérée par les qtés
    lignes = _lignes(schema, 1, [13, 16, 17], du, au, co_no)
    fl = lignes[lignes["do_type"].isin([16, 17]) & lignes["ar_ref"].notna() & (lignes["dl_qte"] > 0) & (lignes["dl_prixunitaire"] > 0)]
    familles_inf, global_inf = [], None
    if not fl.empty:
        jour = fl.groupby(["famille", "ar_ref", "d"]).agg(qte=("dl_qte", "sum"), montant=("dl_montantht", "sum")).reset_index()
        jour["prix"] = jour["montant"] / jour["qte"]
        jour = jour.sort_values("d")
        par_art = jour.groupby(["famille", "ar_ref"]).agg(qte=("qte", "sum"), premier=("prix", "first"),
                                                            dernier=("prix", "last"), dates=("d", "nunique")).reset_index()
        par_art = par_art[(par_art["dates"] >= 2) & (par_art["premier"] > 0)]
        par_art["evol"] = (par_art["dernier"] - par_art["premier"]) / par_art["premier"] * 100
        if not par_art.empty:
            g = par_art.groupby("famille").apply(lambda x: pd.Series({
                "articles": len(x), "qte": x["qte"].sum(), "evol": float((x["evol"] * x["qte"]).sum() / x["qte"].sum())}),
                include_groups=False).reset_index()
            achats_fam = fl.groupby("famille")["dl_montantht"].sum()
            g["achats_ht"] = g["famille"].map(achats_fam).fillna(0.0)
            g = g[g["achats_ht"] >= float(fl["dl_montantht"].sum()) * PART_MIN_FAMILLE / 100].sort_values("achats_ht", ascending=False)
            familles_inf = [{"famille": r.famille, "articles": int(r.articles), "achats_ht": _r(r.achats_ht),
                             "evolution_pct": _r(r.evol, 2)} for r in g.head(TOP).itertuples()]
            global_inf = {"evolution_pct": _r(float((par_art["evol"] * par_art["qte"]).sum() / par_art["qte"].sum()), 2),
                          "articles": int(len(par_art))}

    # Fiabilité des délais : lignes de factures et de BL livrées après la commande (délai = date BL − date BC)
    dl = lignes[lignes["datebc"].notna() & lignes["datebl"].notna()].copy()
    delais = []
    if not dl.empty:
        dl["jours"] = (pd.to_datetime(dl["datebl"]) - pd.to_datetime(dl["datebc"])).dt.days
        dl = dl[dl["jours"] > 0]
        if not dl.empty:
            dl["median"] = dl.groupby("do_tiers")["jours"].transform("median")
            dl["regulier"] = (dl["jours"] - dl["median"]).abs() <= TOLERANCE_DELAI
            g = dl.groupby("do_tiers").agg(lignes=("jours", "size"), commandes=("piecebc", "nunique"), moyen=("jours", "mean"), ecart=("jours", "std"),
                                           median=("jours", "median"), mini=("jours", "min"), maxi=("jours", "max"),
                                           regularite=("regulier", "mean")).reset_index()
            g["regularite"] *= 100
            g = g.sort_values(["regularite", "moyen"], ascending=[False, True])
            delais = [{"code": r.do_tiers, "nom": (intitules.get(r.do_tiers) or r.do_tiers).strip(), "lignes": int(r.lignes), "commandes": int(r.commandes),
                       "delai_moyen": _r(r.moyen, 1), "ecart_type": _r(r.ecart, 1) if r.lignes > 1 else None,
                       "delai_median": _r(r.median, 1), "delai_min": int(r.mini), "delai_max": int(r.maxi),
                       "regularite_pct": _r(r.regularite, 1)} for r in g.itertuples()]

    # Achats et ventes par famille : achats HT (factures d'achat) face aux ventes HT et à leur coût (factures de vente)
    ach = lignes[lignes["do_type"].isin([16, 17])].groupby("famille")["dl_montantht"].sum()
    lv = _lignes(schema, 0, [6, 7], du, au, [])
    lv = lv.assign(cout=lv["dl_qtebl"] * _cout(lv)) if not lv.empty else lv
    ven = lv.groupby("famille")["dl_montantht"].sum() if not lv.empty else pd.Series(dtype=float)
    cout = lv.groupby("famille")["cout"].sum() if not lv.empty else pd.Series(dtype=float)
    fam = pd.DataFrame({"achats_ht": ach, "ventes_ht": ven, "cout_ventes": cout}).fillna(0.0)
    fam = fam.loc[fam[["achats_ht", "ventes_ht"]].max(axis=1).sort_values(ascending=False).index]
    achats_ventes = [{"famille": nom, "achats_ht": _r(r.achats_ht), "ventes_ht": _r(r.ventes_ht), "cout_ventes": _r(r.cout_ventes),
                      "ecart_stock": _r(r.achats_ht - r.cout_ventes)} for nom, r in fam.head(TOP).iterrows()]

    return {"periode": {"du": du, "au": au}, "dependance": dependance,
            "inflation": {"global": global_inf, "familles": familles_inf},
            "delais": {"tolerance_jours": TOLERANCE_DELAI, "fournisseurs": delais[:15]},
            "achats_ventes": achats_ventes}


VUES = {"tdb_plus": tdb_plus, "ruptures_a": ruptures_a, "analyse_ventes": analyse_ventes, "analyse_achats": analyse_achats}
RESERVEES_DIRECTEUR = {"ruptures_a", "analyse_achats"}
