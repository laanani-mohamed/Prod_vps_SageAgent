"""
reporting/generate.py — Génère les rapports clients, sans Streamlit, et les dépose dans
storage_srv/rapport/<CLIENT>/<YYYY-MM-DD>/<nom>.pdf | <nom>.xlsx | <nom>.json
(le .json porte le détail : filtres appliqués, période, date de génération, nombre de lignes...).

Les rapports à générer pour chaque client sont déclarés dans config/rapports_config.py
(liste des rapports et de leurs filtres en tête de ce fichier), avec leurs destinataires
éventuels : les rapports sont alors envoyés par email (reporting/envoi.py, compte Gmail).

Les données passent par la même couche service que l'API (sans le contrôle JWT) : le client
est un client connu de data_Client/reference/auth.json, le script tourne sur le serveur.

Exécution (génère tous les rapports de config/rapports_config.py) :
    /opt/SageAgent/app/.venv/bin/python /opt/SageAgent/app/src/reporting/generate.py
Code de sortie 1 si au moins un rapport a échoué (détail dans la sortie).
"""
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta

SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(SRC_ROOT)
for path in [SRC_ROOT, PROJECT_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)

from fastapi.encoders import jsonable_encoder  # noqa: E402

from api.db import init_db_pool, close_db_pool  # noqa: E402
from api.bi import service as bi_service  # noqa: E402
from api.bi.schemas import (  # noqa: E402
    BalanceClientRequest, RapportCARequest, RapportConsommationRequest,
    RapportVisiteClientRequest, ValeurStockRequest,
)
from api.referentiel import service as referentiel_service  # noqa: E402
from api.referentiel.schemas import ComptesTiersRequest  # noqa: E402
from api.stock import service as stock_service  # noqa: E402
from api.stock.schemas import StockInsightRequest  # noqa: E402
from config.etl_config import REPORT_BASE_PATH  # noqa: E402
from config.rapports_config import RAPPORTS_CLIENTS  # noqa: E402
from reporting import rapports  # noqa: E402
from reporting.envoi import adresse_valide, envoyer_rapports  # noqa: E402
from reporting.exports import (  # noqa: E402
    export_df_to_excel, export_df_to_pdf, export_sections_to_excel, export_visite_to_pdf,
)

logger = logging.getLogger("reporting.generate")

AUTH_JSON_PATH = os.path.join(os.path.dirname(PROJECT_ROOT), "data_Client", "reference", "auth.json")

GROUP_BY = ("client", "region", "commercial")

# Périodes relatives (calculées le jour de la génération) — utilisables dans config/rapports_config.py
PERIODES = {
    "annee_en_cours":   lambda t: (t.replace(month=1, day=1), t),
    "mois_en_cours":    lambda t: (t.replace(day=1), t),
    "mois_precedent":   lambda t: ((t.replace(day=1) - timedelta(days=1)).replace(day=1), t.replace(day=1) - timedelta(days=1)),
    "annee_precedente": lambda t: (date(t.year - 1, 1, 1), date(t.year - 1, 12, 31)),
}


# ---------------------------------------------------------------------------
# Lecture / contrôle des filtres
# ---------------------------------------------------------------------------
def _choix(f: dict, cle: str, valeurs: tuple, defaut: str) -> str:
    valeur = f.get(cle, defaut)
    if valeur not in valeurs:
        raise ValueError(f"{cle} = {valeur!r} invalide (possibles : {', '.join(valeurs)})")
    return valeur


def _entier(f: dict, cle: str, defaut=None):
    valeur = f.get(cle, defaut)
    if valeur is not None and (not isinstance(valeur, int) or isinstance(valeur, bool)):
        raise ValueError(f"{cle} = {valeur!r} doit être un nombre entier")
    return valeur


def _liste(f: dict, cle: str):
    valeur = f.get(cle)
    if valeur is not None and (not isinstance(valeur, list) or not all(isinstance(v, str) for v in valeur)):
        raise ValueError(f"{cle} doit être une liste de textes, ex : [\"SIEGE\"]")
    return valeur


def _dates(f: dict, n: str = ""):
    """(date_from, date_to) explicites `date_from{n}` / `date_to{n}` (AAAA-MM-JJ), ou None si absentes."""
    debut, fin = f.get(f"date_from{n}"), f.get(f"date_to{n}")
    if debut is None and fin is None:
        return None
    if debut is None or fin is None:
        raise ValueError(f"date_from{n} et date_to{n} doivent être renseignées ensemble")
    debut, fin = date.fromisoformat(debut), date.fromisoformat(fin)
    if debut > fin:
        raise ValueError(f"date_from{n} ({debut}) est après date_to{n} ({fin})")
    return debut, fin


def _periode_nommee(f: dict) -> tuple:
    return PERIODES[_choix(f, "periode", tuple(PERIODES), "annee_en_cours")](date.today())


def _un_an_avant(d: date) -> date:
    """Même jour un an plus tôt (29 février → 28 février)."""
    return d.replace(year=d.year - 1, day=28) if (d.month, d.day) == (2, 29) else d.replace(year=d.year - 1)


def _donnees(response) -> list:
    """Lignes de la réponse, sérialisées comme la réponse HTTP de l'API (dates ISO, décimaux → float)."""
    return jsonable_encoder(response)["data"]


# ---------------------------------------------------------------------------
# Un générateur par rapport : (schéma, filtres) → (Rapport, filtres appliqués)
# ---------------------------------------------------------------------------
def _chiffre_affaire(schema: str, f: dict):
    group_by = _choix(f, "group_by", GROUP_BY, "client")
    debut, fin = _dates(f) or _periode_nommee(f)
    req = RapportCARequest(client_schema=schema, group_by=group_by, date_from=debut.isoformat(), date_to=fin.isoformat())
    rows = _donnees(bi_service.get_rapport_ca(req))
    return (rapports.rapport_ca(rows, group_by, debut.isoformat(), fin.isoformat()),
            {**f, "group_by": group_by, "date_from": debut.isoformat(), "date_to": fin.isoformat()})


def _comparaison_ca(schema: str, f: dict):
    group_by = _choix(f, "group_by", GROUP_BY, "client")
    p2 = _dates(f, "_2") or _periode_nommee(f)
    p1 = _dates(f, "_1") or (_un_an_avant(p2[0]), _un_an_avant(p2[1]))
    p1, p2 = tuple(d.isoformat() for d in p1), tuple(d.isoformat() for d in p2)

    def _ca(periode):
        req = RapportCARequest(client_schema=schema, group_by=group_by, date_from=periode[0], date_to=periode[1])
        return _donnees(bi_service.get_rapport_ca(req))

    return (rapports.rapport_comparaison_ca(_ca(p1), _ca(p2), group_by, p1, p2),
            {**f, "group_by": group_by, "date_from_1": p1[0], "date_to_1": p1[1], "date_from_2": p2[0], "date_to_2": p2[1]})


def _balance(schema: str, f: dict):
    commercial = _entier(f, "commercial")
    rows = _donnees(bi_service.get_balance_client(BalanceClientRequest(client_schema=schema)))
    return rapports.rapport_balance(rows, commercial), dict(f)


def _balance_agee(schema: str, f: dict):
    commercial = _entier(f, "commercial")
    rows = _donnees(bi_service.get_balance_agee(BalanceClientRequest(client_schema=schema)))
    return rapports.rapport_balance_agee(rows, commercial), dict(f)


def _valeur_stock(schema: str, f: dict):
    depots, familles, articles = _liste(f, "depots"), _liste(f, "familles"), _liste(f, "articles")
    rows = _donnees(bi_service.get_valeur_stock(ValeurStockRequest(client_schema=schema)))
    return rapports.rapport_valeur_stock(rows, depots, familles, articles), dict(f)


def _visite_client(schema: str, f: dict):
    code = f.get("client")
    if not isinstance(code, str) or not code:
        raise ValueError("visite_client : le filtre 'client' (code client Sage, ex : \"C0015\") est obligatoire")
    tiers = _donnees(referentiel_service.get_specific(
        ComptesTiersRequest(client_schema=schema, ct_num=[code]), endpoint="/api/referentiel/comptes-tiers",
    ))
    if not tiers:
        raise ValueError(f"visite_client : client Sage '{code}' introuvable")
    data = _donnees(bi_service.get_rapport_visite(RapportVisiteClientRequest(client_schema=schema, do_tiers=code)))
    return rapports.rapport_visite_client(data[0] if data else {}, code, tiers[0].get("ct_intitule", "")), dict(f)


def _produits_dormants(schema: str, f: dict):
    mois = _entier(f, "mois", 6)
    req = StockInsightRequest(client_schema=schema, insight_type="dormant", dormant_days=mois * 30, limit=100000000)
    rows = _donnees(stock_service.get_specific(req, endpoint="/api/stock/insights"))
    return rapports.rapport_dormants(rows, mois), {**f, "mois": mois}


def _lots_peremption(schema: str, f: dict):
    jours = _entier(f, "jours", 60)
    req = StockInsightRequest(client_schema=schema, insight_type="expiration", expiry_days=jours, limit=100000000)
    rows = _donnees(stock_service.get_specific(req, endpoint="/api/stock/insights"))
    return rapports.rapport_peremption(rows, jours), {**f, "jours": jours}


def _consommation(schema: str, f: dict):
    data = _donnees(bi_service.get_rapport_consommation(RapportConsommationRequest(client_schema=schema)))
    return rapports.rapport_consommation(data[0] if data else {}), dict(f)


# nom du rapport → (générateur, filtres acceptés)
RAPPORTS = {
    "chiffre_affaire":   (_chiffre_affaire, {"group_by", "periode", "date_from", "date_to"}),
    "comparaison_ca":    (_comparaison_ca, {"group_by", "periode", "date_from_1", "date_to_1", "date_from_2", "date_to_2"}),
    "balance":           (_balance, {"commercial"}),
    "balance_agee":      (_balance_agee, {"commercial"}),
    "valeur_stock":      (_valeur_stock, {"depots", "familles", "articles"}),
    "visite_client":     (_visite_client, {"client"}),
    "produits_dormants": (_produits_dormants, {"mois"}),
    "lots_peremption":   (_lots_peremption, {"jours"}),
    "consommation":      (_consommation, set()),
}


# ---------------------------------------------------------------------------
# Dépôt des fichiers
# ---------------------------------------------------------------------------
def _client_schema(client: str) -> tuple:
    """(nom du dossier client, schéma PostgreSQL) depuis auth.json, sans tenir compte de la casse."""
    with open(AUTH_JSON_PATH, "r", encoding="utf-8") as fh:
        registry = json.load(fh)
    for key, entry in registry.items():
        if key.lower() == client.lower():
            return key, entry["shema"]
    raise ValueError(f"Client '{client}' absent de {AUTH_JSON_PATH}")


def _nom_libre(dossier: str, nom: str) -> str:
    """`nom`, puis `nom_2`, `nom_3`... si un rapport du même nom a déjà été déposé ce jour-là."""
    candidat, n = nom, 1
    while os.path.exists(os.path.join(dossier, f"{candidat}.pdf")):
        n += 1
        candidat = f"{nom}_{n}"
    return candidat


def _derniere_maj_text(last_update: str) -> str:
    """Même ligne que le PDF du dashboard : 'Derniere mise a jour: JJ/MM/AAAA HH:MM' (vide si inconnue)."""
    if not last_update:
        return ""
    return f"Derniere mise a jour: {datetime.fromisoformat(last_update).strftime('%d/%m/%Y %H:%M')}"


def _fichiers(rapport: rapports.Rapport, derniere_maj: str) -> tuple:
    """(PDF, Excel) avec les mêmes fonctions d'export que les boutons de l'onglet du dashboard."""
    if rapport.pdf_par_section:
        pdf = export_visite_to_pdf(rapport.sections, rapport.titre, rapport.sous_titre, derniere_maj=derniere_maj)
    else:
        pdf = export_df_to_pdf(rapport.sections[0][1], rapport.titre, rapport.sous_titre, derniere_maj=derniere_maj)

    if len(rapport.sections) == 1 or rapport.nb_lignes == 0:
        # Plusieurs sections toutes vides : une feuille vide plutôt qu'un classeur sans feuille (invalide)
        excel = export_df_to_excel(rapport.sections[0][1])
    else:
        excel = export_sections_to_excel(rapport.sections)
    return pdf, excel


def generate_report(client: str, rapport: str, filtres: dict = None) -> str:
    """Génère `rapport` pour `client`, dépose le PDF, l'Excel et le .json de détail,
    et retourne le chemin du .json."""
    if rapport not in RAPPORTS:
        raise ValueError(f"Rapport inconnu '{rapport}' (disponibles : {', '.join(RAPPORTS)})")
    generateur, filtres_acceptes = RAPPORTS[rapport]
    filtres = filtres or {}
    inconnus = set(filtres) - filtres_acceptes
    if inconnus:
        raise ValueError(
            f"Filtre(s) inconnu(s) pour '{rapport}' : {', '.join(sorted(inconnus))} "
            f"(acceptés : {', '.join(sorted(filtres_acceptes)) or 'aucun'})"
        )
    dossier_client, schema = _client_schema(client)

    init_db_pool()
    result, filtres_appliques = generateur(schema, filtres)
    last_update = bi_service.get_last_update(schema).last_update
    pdf, excel = _fichiers(result, _derniere_maj_text(last_update))

    now = datetime.now()
    dossier = os.path.join(REPORT_BASE_PATH, dossier_client, now.strftime("%Y-%m-%d"))
    os.makedirs(dossier, exist_ok=True)
    base = _nom_libre(dossier, result.nom)

    with open(os.path.join(dossier, f"{base}.pdf"), "wb") as fh:
        fh.write(pdf)
    with open(os.path.join(dossier, f"{base}.xlsx"), "wb") as fh:
        fh.write(excel)

    detail = {
        "rapport": rapport,
        "titre": result.titre,
        "sous_titre": result.sous_titre,
        "client": dossier_client,
        "client_schema": schema,
        "filtres": filtres_appliques,
        "genere_le": now.isoformat(timespec="seconds"),
        "derniere_maj_donnees": last_update,
        "nb_lignes": result.nb_lignes,
        "fichiers": {"pdf": f"{base}.pdf", "excel": f"{base}.xlsx"},
    }
    json_path = os.path.join(dossier, f"{base}.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(detail, fh, indent=4, ensure_ascii=False)
        fh.write("\n")

    logger.info("Rapport '%s' déposé pour %s (%d lignes) : %s", rapport, dossier_client, result.nb_lignes, json_path)
    return json_path


def _config_client(conf: dict) -> tuple:
    """(destinataires, rapports) de la config d'un client, contrôlés : {"destinataires": [...], "rapports": [...]}."""
    if not isinstance(conf, dict):
        raise ValueError('la config du client doit être {"destinataires": [...], "rapports": [...]}')
    inconnues = set(conf) - {"destinataires", "rapports"}
    if inconnues:
        raise ValueError(f"clé(s) inconnue(s) : {', '.join(sorted(inconnues))} (acceptées : destinataires, rapports)")
    destinataires = conf.get("destinataires") or []
    destinataires = [destinataires] if isinstance(destinataires, str) else destinataires
    invalides = [a for a in destinataires if not adresse_valide(a)]
    if invalides:
        raise ValueError(f"adresse(s) email invalide(s) : {', '.join(map(str, invalides))}")
    return destinataires, conf.get("rapports", [])


def generer_selon_config() -> tuple:
    """Génère tous les rapports de config/rapports_config.py, client par client, puis envoie à chaque
    destinataire du client un seul email avec tous ses rapports.
    Un rapport ou un envoi en échec est journalisé sans bloquer les suivants.
    Retourne (chemins des .json déposés, nombre d'échecs)."""
    chemins, echecs = [], 0
    for nom_client, conf in RAPPORTS_CLIENTS.items():
        try:
            destinataires, entrees = _config_client(conf)
        except ValueError as exc:
            echecs += 1
            logger.error("Config du client %s ignorée : %s", nom_client, exc)
            continue

        jsons_client = []
        for entree in entrees:
            try:
                inconnues = set(entree) - {"rapport", "filtres"}
                if inconnues:
                    raise ValueError(f"Clé(s) inconnue(s) : {', '.join(sorted(inconnues))} (acceptées : rapport, filtres)")
                jsons_client.append(generate_report(nom_client, entree["rapport"], entree.get("filtres")))
            except Exception:
                echecs += 1
                logger.exception("Échec du rapport %s pour %s", entree.get("rapport"), nom_client)
        chemins.extend(jsons_client)

        for destinataire in destinataires if jsons_client else []:
            try:
                envoyer_rapports(nom_client, destinataire, jsons_client)
                logger.info("%d rapport(s) %s envoyé(s) à %s", len(jsons_client), nom_client, destinataire)
            except Exception:
                echecs += 1
                logger.exception("Échec de l'envoi des rapports %s à %s", nom_client, destinataire)
    return chemins, echecs


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        chemins, echecs = generer_selon_config()
    finally:
        close_db_pool()
    logger.info("%d rapport(s) déposé(s), %d échec(s)", len(chemins), echecs)
    sys.exit(1 if echecs else 0)


if __name__ == "__main__":
    main()
