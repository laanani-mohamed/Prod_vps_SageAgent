"""
api/bi/vues.py — Données prêtes à afficher pour les pages du front Next.js (src/front).

Les pages Streamlit chargeaient des listes complètes, puis filtraient, comptaient et totalisaient en
pandas : ces calculs sont faits ici. Les données passent par les services existants (mêmes requêtes
SQL ; le périmètre co_no d'un collaborateur est imposé par secured_handle avant l'appel).
Chaque vue : (schéma, filtres, co_no) → dict JSON ; les listes sont paginées (TAILLE_PAGE lignes).
"""
from __future__ import annotations
import re
from datetime import date, datetime

import pandas as pd
from fastapi.encoders import jsonable_encoder

from api.bi.repositories.pg_repo.sql_helpers import validate_schema
from api.bi import vues_analyse
from api.common.cache import memo
from api.db import get_db_connection
from api.referentiel import service as referentiel
from api.referentiel.schemas import (
    ArticleDetailRequest, ComptesTiersRequest, DocEnteteRequest, DocLigneRequest,
    FamilleRequest, ReglementRequest, StockDepotRequest,
)
from api.stock import service as stock
from api.stock.schemas import CheckAvailabilityRequest, StockInsightRequest

TAILLE_PAGE = 50

TYPES_DOCUMENT = {
    0: {0: "Devis", 1: "Bon de commande", 2: "Préparation livraison", 3: "Bon de livraison",
        4: "Bon de retour", 5: "Bon d'avoir", 6: "Facture", 7: "Facture comptabilisée"},
    1: {10: "Demande d'achat", 11: "Préparation de commande", 12: "Bon de commande", 13: "Bon de livraison",
        14: "Bon de retour", 15: "Bon d'avoir", 16: "Facture", 17: "Facture comptabilisée"},
    2: {20: "Mouvement d'entrée", 21: "Mouvement de sortie", 22: "Mouvement de dépôt à dépôt", 23: "Transfert"},
}
FACTURES = {0: [6, 7], 1: [16, 17]}
TYPES_REGLEMENT = {0: "Règlement", 1: "Acompte", 2: "Fond de caisse", 3: "Remise en banque", 4: "Sortie de caisse",
                   5: "Entrée en caisse", 6: "Remise à 0", 7: "Contrôle de caisse", 8: "Bon d'achat"}
SUIVI_STOCK = {0: "Aucun", 1: "Sérialisé", 2: "CMUP", 3: "FIFO", 4: "LIFO", 5: "Par lot"}
ALERTES = {"rupture": "rupture", "dormant": "dormant", "jamais_vendu": "jamais_vendu", "peremption": "expiration"}


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def _df(reponse) -> pd.DataFrame:
    """Lignes d'une réponse de service, sérialisées comme la réponse HTTP (dates ISO, décimaux → float)."""
    return pd.DataFrame(jsonable_encoder(reponse)["data"])


def _ref(req, endpoint: str) -> pd.DataFrame:
    """Table du référentiel pour `req` (en cache jusqu'au prochain ETL ; copie, car les vues modifient leurs colonnes)."""
    return memo(req.client_schema, f"ref|{endpoint}|{req.model_dump_json()}",
                lambda: _df(referentiel.get_specific(req, endpoint=f"/api/referentiel/{endpoint}"))).copy()


def _num(df: pd.DataFrame, *colonnes) -> pd.DataFrame:
    for c in colonnes:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def _contient(df: pd.DataFrame, colonne: str, texte) -> pd.DataFrame:
    """Lignes dont `colonne` contient `texte` (sans tenir compte de la casse) ; texte vide = toutes."""
    if not texte or df.empty:
        return df
    return df[df[colonne].astype(str).str.contains(str(texte).strip(), case=False, na=False, regex=False)]


def _page(df: pd.DataFrame, page, colonnes: list, taille=None) -> dict:
    """{total, page, taille_page, lignes} : la page `page` (1 = première) de `df`, NaN → null ;
    `taille` : lignes par page (TAILLE_PAGE par défaut, 200 au plus)."""
    page, taille = max(1, int(page or 1)), min(200, max(1, int(taille or TAILLE_PAGE)))
    if df.empty:
        return {"total": 0, "page": 1, "taille_page": taille, "lignes": []}
    morceau = df.iloc[(page - 1) * taille: page * taille][colonnes]
    return {"total": len(df), "page": page, "taille_page": taille,
            "lignes": morceau.astype(object).where(morceau.notna(), None).to_dict("records")}


def _commercial(df: pd.DataFrame) -> pd.Series:
    """Commercial porté par l'entête : co_no 0 ou vide → « Non identifié », sinon « nom prénom »."""
    co = pd.to_numeric(df["co_no"], errors="coerce").fillna(0).astype(int)
    prenom = df["co_prenom"] if "co_prenom" in df.columns else ""
    nom = (df["co_nom"].fillna("").astype(str).str.strip() + " "
           + pd.Series(prenom, index=df.index).fillna("").astype(str).str.strip()).str.strip()
    return nom.mask(nom == "", "Commercial " + co.astype(str)).where(co != 0, "Non identifié")


def _ice(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.replace(r"^\s*ICE\s*:?\s*", "", regex=True, case=False)


def _noms_depots(schema: str) -> dict:
    """{numéro de dépôt (texte) : intitulé} — tiers des documents de stock (domaine 2)."""
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT de_no, de_intitule FROM {validate_schema(schema)}.f_depot")
        return {str(no): nom for no, nom in cur.fetchall()}


def _statut(df: pd.DataFrame) -> pd.Series:
    regle = pd.to_numeric(df["do_montantregle"], errors="coerce").fillna(0)
    return (pd.Series("Non réglée", index=df.index)
            .mask(regle > 0.005, "Partiellement réglée").mask(df["reste_a_payer"] <= 0.005, "Réglée"))


# ---------------------------------------------------------------------------
# Règlements (encaissements / décaissements)
# ---------------------------------------------------------------------------
def reglements(schema: str, f: dict, co_no: list) -> dict:
    """KPIs et lignes des règlements d'un domaine (0 clients, 1 fournisseurs), du plus récent au plus ancien."""
    req = ReglementRequest(client_schema=schema, do_domaine=[int(f.get("domaine", 0))],
                           do_piece=[f["piece"]] if f.get("piece") else [],
                           date_from=f.get("date_from"), date_to=f.get("date_to"), co_no=co_no)
    df = _contient(_contient(_ref(req, "reglements"), "do_tiers", f.get("tiers")), "ct_intitule", f.get("intitule"))
    if df.empty:
        return {"kpis": {"nombre": 0, "montant": 0.0, "tiers": 0, "dernier": None}, **_page(df, 1, [])}
    df = _num(df, "rc_montant").sort_values(["do_date", "rg_no"], ascending=False)
    df["date"] = df["do_date"].astype(str).str[:10]
    df["type"] = pd.to_numeric(df["rg_typereg"], errors="coerce").map(TYPES_REGLEMENT).fillna("Autre")
    df["ice"] = _ice(df["ct_identifiant"])
    return {
        "kpis": {"nombre": len(df), "montant": float(df["rc_montant"].sum()),
                 "tiers": int(df["do_tiers"].nunique()), "dernier": df["date"].max()},
        **_page(df, f.get("page"), ["rg_no", "do_piece", "do_domaine", "do_type", "date", "do_tiers",
                                    "ct_intitule", "ice", "type", "rc_montant"], f.get("taille")),
    }


# ---------------------------------------------------------------------------
# Documents (ventes, achats, mouvements de stock)
# ---------------------------------------------------------------------------
def documents(schema: str, f: dict, co_no: list) -> dict:
    """Documents d'un domaine (0 ventes, 1 achats, 2 stock) sur la période : KPIs des factures,
    nombre de documents par type et lignes du type choisi (du plus récent au plus ancien)."""
    domaine = int(f.get("domaine", 0))
    noms = TYPES_DOCUMENT[domaine]
    types = [int(f["type"])] if domaine == 2 else list(noms)
    df = _ref(DocEnteteRequest(client_schema=schema, do_domaine=[domaine], do_type=types,
                               date_from=f.get("date_from"), date_to=f.get("date_to"), co_no=co_no), "documents-entete")
    if domaine == 2 and not df.empty:   # le tiers d'un mouvement de stock est le dépôt
        df["ct_intitule"] = df["do_tiers"].astype(str).map(_noms_depots(schema))
    for colonne, texte in [("do_piece", f.get("piece")), ("do_tiers", f.get("tiers")), ("ct_intitule", f.get("intitule"))]:
        df = _contient(df, colonne, texte)
    if not df.empty:
        df = _num(df, "do_totalht", "do_totalttc", "reste_a_payer")
        if f.get("non_regles"):
            df = df[df["reste_a_payer"] > 0.005]

    factures = df[df["do_type"].isin(FACTURES.get(domaine, types))] if not df.empty else df
    somme = (lambda c: float(factures[c].sum())) if not factures.empty else (lambda c: 0.0)
    nb_type = df["do_type"].value_counts() if not df.empty else pd.Series(dtype=int)
    choisi = int(f.get("type") or (FACTURES[domaine][0] if domaine in FACTURES else types[0]))

    lignes = df[df["do_type"] == choisi].sort_values(["do_date", "do_piece"], ascending=False) if not df.empty else df
    if not lignes.empty:
        lignes = lignes.assign(date=lignes["do_date"].astype(str).str[:10], commercial=_commercial(lignes),
                               tva=lignes["do_totalttc"] - lignes["do_totalht"],
                               statut=_statut(lignes) if choisi in FACTURES.get(domaine, []) else None)
    return {
        "kpis": {"nombre": len(factures), "ht": somme("do_totalht"), "ttc": somme("do_totalttc"), "reste": somme("reste_a_payer")},
        "types": [{"type": t, "nom": nom, "nombre": int(nb_type.get(t, 0))} for t, nom in noms.items() if t in types],
        "type": choisi,
        **_page(lignes, f.get("page"), ["do_piece", "do_type", "date", "commercial", "do_tiers", "ct_intitule",
                                        "do_totalht", "tva", "do_totalttc", "reste_a_payer", "statut"], f.get("taille")),
    }


def document(schema: str, f: dict, co_no: list) -> dict:
    """Un document, par sa clé unique (domaine, type, pièce) : entête et lignes."""
    domaine, type_ = int(f["domaine"]), int(f["type"])
    cle = {"do_domaine": [domaine], "do_type": [type_], "do_piece": [str(f["piece"])]}
    ent = _ref(DocEnteteRequest(client_schema=schema, co_no=co_no, **cle), "documents-entete")
    if ent.empty:
        raise FileNotFoundError(f"Document {f['piece']} introuvable")
    ent = _num(ent, "do_totalht", "do_totalttc", "reste_a_payer")
    if domaine == 2:
        ent["ct_intitule"] = ent["do_tiers"].astype(str).map(_noms_depots(schema))
    e = ent.iloc[0]
    lignes = _ref(DocLigneRequest(client_schema=schema, co_no=co_no, **cle), "documents-ligne")
    if not lignes.empty:
        lignes = _num(lignes, "dl_qte", "dl_prixunitaire", "dl_montantht", "dl_montantttc")
    return {
        "entete": {"piece": e["do_piece"], "type": TYPES_DOCUMENT[domaine].get(type_, str(type_)),
                   "date": str(e["do_date"])[:10], "tiers": e["do_tiers"], "intitule": e["ct_intitule"],
                   "commercial": _commercial(ent).iloc[0], "ht": float(e["do_totalht"]),
                   "tva": float(e["do_totalttc"] - e["do_totalht"]), "ttc": float(e["do_totalttc"]),
                   "reste": float(e["reste_a_payer"]),
                   "statut": _statut(ent).iloc[0] if type_ in FACTURES.get(domaine, []) else None},
        **_page(lignes, f.get("page"), ["ar_ref", "dl_design", "dl_qte", "dl_prixunitaire", "dl_montantht", "dl_montantttc"]),
    }


# ---------------------------------------------------------------------------
# Fichier de base
# ---------------------------------------------------------------------------
def compteurs(schema: str, f: dict, co_no: list) -> dict:
    """Nombre d'articles, de clients, de fournisseurs, de dépôts et de familles (bandeau du Fichier de base),
    comptés comme les listes : articles en sommeil compris."""
    s = validate_schema(schema)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT (SELECT count(*) FROM {s}.f_article),
                               (SELECT count(*) FROM {s}.f_comptet WHERE ct_type = 0),
                               (SELECT count(*) FROM {s}.f_comptet WHERE ct_type = 1),
                               (SELECT count(*) FROM {s}.f_depot), (SELECT count(*) FROM {s}.f_famille)""")
        articles, clients, fournisseurs, depots, familles = cur.fetchone()
    return {"articles": articles, "clients": clients, "fournisseurs": fournisseurs, "depots": depots, "familles": familles}


def articles(schema: str, f: dict, co_no: list) -> dict:
    """Articles avec stock, filtrés par famille(s) (`famille`, ou `familles` séparées par des virgules),
    désignation et référence."""
    familles = [c for c in str(f.get("familles") or f.get("famille") or "").split(",") if c]
    req = ArticleDetailRequest(client_schema=schema, with_stock=True, fa_codefamille=familles)
    df = _contient(_contient(_ref(req, "articles/detail"), "ar_design", f.get("design")), "ar_ref", f.get("ref"))
    return _page(df, f.get("page"), ["ar_ref", "ar_design", "fa_codefamille", "fa_intitule", "ar_prixach", "ar_prixven", "qte_stock_totale"], f.get("taille"))


def article(schema: str, f: dict, co_no: list) -> dict:
    """Statistiques de vente d'un article sur la période (factures 6 et 7, CA HT = Σ dl_montantht),
    ses 5 premiers clients et son stock par dépôt (non renvoyé pour la vue d'un commercial)."""
    ref = str(f["ref"])
    art = _ref(ArticleDetailRequest(client_schema=schema, ar_ref_exact=[ref], with_stock=True, ar_sommeil=None), "articles/detail")
    if art.empty:
        raise FileNotFoundError(f"Article {ref} introuvable")
    a = _num(art, "ar_prixach", "ar_prixven", "qte_stock_totale").iloc[0]
    lignes = _ref(DocLigneRequest(client_schema=schema, ar_ref=[ref], do_domaine=[0], do_type=[6, 7], with_entete=True,
                                  date_from=f.get("date_from"), date_to=f.get("date_to"), co_no=co_no), "documents-ligne")
    if lignes.empty:
        lignes = pd.DataFrame(columns=["dl_qte", "dl_montantht", "ct_intitule", "ct_num"])
    lignes = _num(lignes, "dl_qte", "dl_montantht")
    qte, ca = float(lignes["dl_qte"].sum()), float(lignes["dl_montantht"].sum())
    cout = qte * float(a["ar_prixach"])
    clients = (lignes.assign(client=lignes["ct_intitule"].fillna(lignes["ct_num"]).fillna("Client inconnu"))
               .groupby("client").agg(qte=("dl_qte", "sum"), ca=("dl_montantht", "sum"))
               .sort_values("ca", ascending=False).head(5).reset_index())
    depots = None
    if not co_no:
        dispo = jsonable_encoder(stock.get_specific(CheckAvailabilityRequest(client_schema=schema, ar_ref=[ref]),
                                                    endpoint="/api/stock/availability"))["data"]
        depots = [{"depot": d, "qte": q} for d, q in sorted((dispo[0].get("qte_par_depot") or {}).items(), key=lambda x: -x[1])] if dispo else []
    return {
        "article": {"ref": ref, "design": a["ar_design"], "famille": a["fa_codefamille"], "famille_nom": a["fa_intitule"],
                    "prix_achat": float(a["ar_prixach"]), "prix_vente": float(a["ar_prixven"]), "stock": float(a["qte_stock_totale"])},
        "kpis": {"quantite_vendue": qte, "ca_ht": ca, "cout_achat": cout, "marge_brute": ca - cout,
                 "taux_marge_pct": (ca - cout) / ca * 100 if ca > 0 else None,
                 "rentabilite_pct": (ca - cout) / cout * 100 if cout > 0 else None},
        "top_clients": clients.to_dict("records"),
        "depots": depots,
    }


def tiers(schema: str, f: dict, co_no: list) -> dict:
    """Comptes clients (ct_type 0) ou fournisseurs (1), filtrés par nom et par code."""
    df = _ref(ComptesTiersRequest(client_schema=schema, ct_type=[int(f.get("ct_type", 0))]), "comptes-tiers")
    df = _contient(_contient(df, "ct_intitule", f.get("nom")), "ct_num", f.get("ref"))
    if not df.empty:
        df = df.sort_values("ct_num").assign(ice=_ice(df["ct_identifiant"]))
    return _page(df, f.get("page"), ["ct_num", "ct_intitule", "ice", "ct_ville"], f.get("taille"))


def clients(schema: str, f: dict, co_no: list) -> dict:
    """Tous les comptes clients (code, intitulé) : liste de choix du bon de commande."""
    df = _ref(ComptesTiersRequest(client_schema=schema, ct_type=[0]), "comptes-tiers")
    if df.empty:
        return {"clients": []}
    df = df.sort_values("ct_num")[["ct_num", "ct_intitule"]]
    return {"clients": df.astype(object).where(df.notna(), None).to_dict("records")}


TAUX_TVA = 20.0


def bon_commande(schema: str, ct_num: str, lignes: list[dict], remise_globale: float, derniere_maj: str | None) -> tuple[str, bytes]:
    """PDF d'un bon de commande client (page 9 de Streamlit) : (nom du fichier, contenu).
    Prix de vente, désignation et famille relus dans Sage ; quantités et remises (%) de la saisie ;
    totaux HT, TVA et TTC après remise globale. Rien n'est écrit en base."""
    from reporting.exports import export_df_to_pdf   # import local, comme reporting.generate dans service.py

    tiers = _ref(ComptesTiersRequest(client_schema=schema, ct_type=[0]), "comptes-tiers")
    client = tiers[tiers["ct_num"] == ct_num] if not tiers.empty else tiers
    if client.empty:
        raise ValueError(f"Client {ct_num} introuvable")
    refs = [l["ar_ref"] for l in lignes]
    art = _ref(ArticleDetailRequest(client_schema=schema, ar_ref_exact=refs, ar_sommeil=None), "articles/detail")
    art = _num(art, "ar_prixven").drop_duplicates("ar_ref").set_index("ar_ref") if not art.empty else art
    manquants = [r for r in refs if r not in art.index]
    if manquants:
        raise ValueError(f"Article(s) introuvable(s) : {', '.join(manquants)}")

    df = pd.DataFrame([{
        "Réf. Famille": art.at[l["ar_ref"], "fa_codefamille"], "Réf. Article": l["ar_ref"],
        "Désignation": art.at[l["ar_ref"], "ar_design"], "Qté": l["qte"], "PU HT": art.at[l["ar_ref"], "ar_prixven"],
        "Remise %": l["remise_pct"],
        "Total HT": art.at[l["ar_ref"], "ar_prixven"] * l["qte"] * (1 - l["remise_pct"] / 100),
    } for l in lignes])
    brut = float(df["Total HT"].sum())
    ht = brut * (1 - remise_globale / 100)
    ttc = ht * (1 + TAUX_TVA / 100)
    recap = [[""] * 7]   # ligne vide : détache le récapitulatif des produits
    if remise_globale > 0:
        recap.append(["", "", "Remise globale", "", "", remise_globale, -(brut - ht)])
    recap += [["", "", "TOTAL HT", "", "", "", ht], ["", "", f"TVA {TAUX_TVA:.0f} %", "", "", "", ttc - ht],
              ["", "", "TOTAL TTC", "", "", "", ttc]]
    df = pd.concat([df, pd.DataFrame(recap, columns=df.columns)], ignore_index=True)

    jour = date.today().isoformat()
    maj = f"Derniere mise a jour: {datetime.fromisoformat(derniere_maj).strftime('%d/%m/%Y %H:%M')}" if derniere_maj else ""
    pdf = export_df_to_pdf(df, title=f"Bon de Commande - {client.iloc[0]['ct_intitule'] or ct_num}",
                           subtitle=f"Client {ct_num} - Date {jour}", recap_rows=len(recap), derniere_maj=maj)
    return f"{re.sub(r'[^A-Za-z0-9_-]', '_', ct_num)}_{jour}.pdf", pdf


def depots(schema: str, f: dict, co_no: list) -> dict:
    """Dépôts et nombre d'articles distincts référencés dans chacun."""
    df = _ref(StockDepotRequest(client_schema=schema), "stock-depot")
    if df.empty:   # client sans données : la table n'a même pas de colonnes
        return {"depots": []}
    g = df.groupby(["de_no", "de_intitule"], dropna=False)["ar_ref"].nunique().reset_index(name="articles")
    return {"depots": g.sort_values("de_no").astype(object).where(g.notna(), None).to_dict("records")}


def familles(schema: str, f: dict, co_no: list) -> dict:
    """Familles (filtrées par intitulé et par code) et, si `choix` (codes séparés par des virgules),
    les articles de ces familles du plus gros stock au plus petit."""
    df = _ref(FamilleRequest(client_schema=schema, with_articles_count=True), "familles")
    df = _contient(_contient(df, "fa_intitule", f.get("nom")), "fa_codefamille", f.get("code"))
    if not df.empty:
        df = df.assign(suivi=pd.to_numeric(df["fa_suivistock"], errors="coerce").map(SUIVI_STOCK))
    choix = [c for c in str(f.get("choix") or "").split(",") if c]
    articles_choisis = None
    if choix:
        art = _ref(ArticleDetailRequest(client_schema=schema, fa_codefamille=choix, with_stock=True), "articles/detail")
        if not art.empty:
            art = _num(art, "qte_stock_totale").sort_values("qte_stock_totale", ascending=False)
        articles_choisis = _page(art, f.get("page_articles"), ["ar_ref", "ar_design", "fa_codefamille", "ar_prixach", "ar_prixven", "qte_stock_totale"])
    return {**_page(df, f.get("page"), ["fa_codefamille", "fa_intitule", "suivi", "nb_articles", "u_intitule"], f.get("taille")),
            "choix": choix, "articles": articles_choisis}


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------
def stock_etat(schema: str, f: dict, co_no: list) -> dict:
    """Stock par article et par dépôt (quantité > 0), du plus valorisé au moins valorisé."""
    df = _ref(StockDepotRequest(client_schema=schema), "stock-depot")
    if df.empty:
        return {"kpis": {"articles": 0, "quantite": 0.0, "valeur": 0.0, "depots": 0}, "familles": [], **_page(df, 1, [])}
    df = _num(df, "as_qtesto", "as_montsto")
    nb_depots = int(df["de_no"].nunique())
    df = df[df["as_qtesto"] > 0]
    familles_dispo = (df[["fa_codefamille", "fa_intitule"]].drop_duplicates("fa_codefamille")
                      .sort_values("fa_intitule").rename(columns={"fa_codefamille": "code", "fa_intitule": "nom"}))
    if f.get("famille"):
        df = df[df["fa_codefamille"] == f["famille"]]
    df = _contient(_contient(df, "ar_ref", f.get("ref")), "ar_design", f.get("design")).sort_values("as_montsto", ascending=False)
    return {
        "kpis": {"articles": int(df["ar_ref"].nunique()), "quantite": float(df["as_qtesto"].sum()),
                 "valeur": float(df["as_montsto"].sum()), "depots": nb_depots},
        "familles": familles_dispo.astype(object).where(familles_dispo.notna(), None).to_dict("records"),
        **_page(df, f.get("page"), ["ar_ref", "ar_design", "fa_codefamille", "de_intitule", "as_qtesto", "as_montsto"], f.get("taille")),
    }


def stock_alertes(schema: str, f: dict, co_no: list) -> dict:
    """Les 4 alertes de stock (nombre de lignes de chacune), puis l'alerte choisie : 10 premières familles et lignes."""
    mois, jours = int(f.get("mois") or 6), int(f.get("jours") or 60)
    choisi = f.get("type") or "rupture"
    if choisi not in ALERTES:
        raise ValueError(f"Alerte inconnue '{choisi}' (possibles : {', '.join(ALERTES)})")

    def lire(t):
        req = StockInsightRequest(client_schema=schema, insight_type=ALERTES[t], dormant_days=mois * 30,
                                  expiry_days=jours, limit=100000000)
        return memo(schema, f"insight|{req.model_dump_json()}", lambda: pd.DataFrame(
            jsonable_encoder(stock.get_specific(req, endpoint="/api/stock/insights"))["data"])).copy()

    donnees = {t: lire(t) for t in ALERTES}
    df = donnees[choisi]
    if f.get("famille") and not df.empty:
        df = df[df["fa_codefamille"] == f["famille"]]
    if "valeur_stock" in df.columns:
        df = _num(df, "valeur_stock").sort_values("valeur_stock", ascending=False)
    colonnes = [c for c in df.columns if c not in ("ar_suivistock", "suivi_lot")]
    par_famille = df["fa_codefamille"].value_counts().head(10) if not df.empty else pd.Series(dtype=int)
    return {
        "types": [{"type": t, "nombre": len(d)} for t, d in donnees.items()], "type": choisi, "mois": mois, "jours": jours,
        "par_famille": [{"famille": k, "nombre": int(v)} for k, v in par_famille.items()],
        "colonnes": colonnes, **_page(df, f.get("page"), colonnes, f.get("taille")),
    }


def plan_depots(schema: str, f: dict, co_no: list) -> dict:
    """Plan des dépôts : pour chaque dépôt et pour tout le stock (`tous`, sans regroupement par dépôt) :
    valeur, quantité, articles, ses 6 premières familles (en quantité) et les 5 articles les plus stockés de chacune
    (quantités et valeurs d'un même article additionnées sur ses dépôts)."""
    from api.bi.schemas import ValeurStockRequest
    from api.bi.service import get_valeur_stock   # import local : api.bi.service importe ce module

    nb_depots = len(_noms_depots(schema))
    df = memo(schema, "valeur_stock", lambda: _df(get_valeur_stock(ValeurStockRequest(client_schema=schema)))).copy()
    if df.empty:
        vide = {"valeur": 0.0, "quantite": 0.0, "articles": 0}
        return {"totaux": {"depots": nb_depots, **vide}, "tous": {"no": 0, "nom": "Tous les dépôts", **vide, "nb_familles": 0, "familles": []}, "depots": []}
    df = _num(df, "qte_stock", "valeur_stock")

    def resume(g):
        return {"valeur": float(g["valeur_stock"].sum()), "quantite": float(g["qte_stock"].sum()), "articles": int(g["ar_ref"].nunique())}

    def detail(no, nom, d):
        fams = []
        for (code, intitule), g in d.groupby(["fa_codefamille", "fa_intitule"], dropna=False):
            top = (g.groupby(["ar_ref", "ar_design"], dropna=False)[["qte_stock", "valeur_stock"]].sum()
                   .reset_index().sort_values("qte_stock", ascending=False).head(5))
            fams.append({"code": code, "nom": intitule, **resume(g), "top": top.to_dict("records")})
        fams.sort(key=lambda x: -x["quantite"])
        return {"no": int(no), "nom": nom, **resume(d), "nb_familles": len(fams), "familles": fams[:6]}

    depots = [detail(no, nom, d) for (no, nom), d in df.groupby(["de_no", "de_intitule"], dropna=False)]
    return {"totaux": {"depots": nb_depots, **resume(df)}, "tous": detail(0, "Tous les dépôts", df),
            "depots": sorted(depots, key=lambda x: -x["valeur"])}


VUES = {
    "reglements": reglements, "documents": documents, "document": document,
    "compteurs": compteurs, "articles": articles, "article": article, "tiers": tiers, "clients": clients,
    "depots": depots, "familles": familles,
    "stock_etat": stock_etat, "stock_alertes": stock_alertes, "plan_depots": plan_depots,
    # Refonte : compléments du Tableau de Bord, onglets « Analyse » des Ventes et des Achats (vues_analyse.py)
    **vues_analyse.VUES,
}


def reservee_directeur(nom: str, f: dict) -> bool:
    """Vue sans commercial (stock, achats, fournisseurs) : refusée à un collaborateur."""
    return (nom in {"depots", "stock_etat", "stock_alertes", "plan_depots"} | vues_analyse.RESERVEES_DIRECTEUR
            or (nom in {"documents", "document", "reglements", "recouvrement"} and int(f.get("domaine", 0)) != 0)
            or (nom == "tiers" and int(f.get("ct_type", 0)) != 0))
