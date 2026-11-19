"""
api/common/prechauffage.py — Garde le cache (api/common/cache.py) à jour et déjà rempli.

Toutes les minutes, pour chaque client utilisé (auth.users actifs) déjà passé par l'ETL :
  signature = (dernière ingestion ETL réussie, date du jour)
  si elle a changé : cache du client vidé (nouvelles données, ou nouvelle journée), puis pages par
  défaut du front rendues une fois avec un jeton directeur interne. Leurs calculs sont ainsi en cache
  avant le premier clic. Passer par les pages du front donne exactement les clés de cache des vrais
  utilisateurs (profil directeur ; un collaborateur, filtré sur son co_no, calcule au premier clic).
"""
import logging
import os
import threading
import time
from datetime import date

import httpx

from api.auth.schemas import UserInDB
from api.auth.service import create_access_token
from api.common import cache
from api.db import get_db_connection

logger = logging.getLogger("api.prechauffage")

FRONT_URL = os.getenv("FRONT_URL", "http://127.0.0.1:8504")
INTERVALLE = 60   # secondes entre deux vérifications
PAGES = [
    "/", "/fichier-de-base/articles", "/fichier-de-base/clients", "/fichier-de-base/fournisseurs",
    "/fichier-de-base/depots", "/fichier-de-base/familles", "/ventes", "/achats",
    "/stock/etat", "/stock/entrants", "/stock/sortants", "/stock/alertes", "/stock/plan",
    "/reglements/encaissements", "/reglements/decaissements", *[f"/rapports/{n}" for n in range(1, 10)],
]

# Clients des comptes actifs et date de leur dernière ingestion ETL réussie (NULL : jamais)
_SQL = """
    SELECT s.schema, MAX(e.created_at)
    FROM (SELECT DISTINCT unnest(allowed_schemas) AS schema FROM auth.users WHERE is_active) s
    LEFT JOIN etl_events.pipeline_events e
           ON lower(e.client) = lower(s.schema) AND e.event_type = 'PipelineCompleted'
    GROUP BY s.schema
"""

_faits: dict = {}   # schema → signature du dernier préchauffage
_arret = threading.Event()


def _rendre(schema: str) -> bool:
    """Rend les PAGES du front pour `schema`. False si le front est injoignable (à réessayer)."""
    jeton = create_access_token(UserInDB(id=0, username="prechauffage", hashed_password="", is_active=True,
                                         allowed_schemas=[schema], roles=["directeur"]))
    debut = time.monotonic()
    with httpx.Client(base_url=FRONT_URL, cookies={"access": jeton}, timeout=180) as client:
        for page in PAGES:
            if _arret.is_set():
                return False
            try:
                r = client.get(page)
            except httpx.TransportError as exc:
                logger.warning("[Préchauffage] front injoignable (%s) : %s", FRONT_URL, exc)
                return False
            if r.status_code != 200:
                logger.warning("[Préchauffage] %s %s → HTTP %s", schema, page, r.status_code)
    logger.info("[Préchauffage] %s : %d pages en %.1f s (%d entrées en cache)",
                schema, len(PAGES), time.monotonic() - debut, cache.taille())
    return True


def _passage() -> None:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(_SQL)
        clients = cur.fetchall()
    for schema, etl in clients:
        signature = (etl, date.today())
        if etl is None or _faits.get(schema) == signature:   # jamais ingéré : rien à préchauffer
            continue
        if schema in _faits:   # nouvel ETL ou nouvelle journée : les anciens résultats sont périmés
            cache.vider(schema)
        _faits[schema] = signature
        if not _rendre(schema):
            del _faits[schema]   # réessayé au prochain passage (sans revider le cache)
            return


def _boucle() -> None:
    while not _arret.is_set():
        try:
            _passage()
        except Exception:
            logger.exception("[Préchauffage] passage en échec")
        _arret.wait(INTERVALLE)


def demarrer() -> None:
    threading.Thread(target=_boucle, name="prechauffage", daemon=True).start()


def arreter() -> None:
    _arret.set()
