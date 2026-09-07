"""
api/bi/service.py — Couche service pour le module BI.

Point d'entrée unique appelé par le router.
Délègue chaque endpoint au Use Case correspondant.

Architecture miroir du module stock :
  Router → Service (dispatcher) → Use Case → Business Logic + Repository
"""
from __future__ import annotations
import logging

from api.bi.schemas import (
    DashboardRequest, DashboardResponse,
    ObjectifsResponse,
    RapportCARequest, TopClientsRequest, TopArticlesRequest,
    RapportResponse, KpiAnalytiqueResponse,
    RapportVisiteClientRequest,
)
from api.bi.use_cases import (
    dashboard_uc,
    objectifs_uc,
    analytique_uc,
    rapport_ca_uc,
    top_clients_uc,
    top_articles_uc,
    balance_uc,
    rapport_visite_uc,
)

logger = logging.getLogger("api.bi.service")


def get_dashboard(req: DashboardRequest) -> DashboardResponse:
    """KPIs du tableau de bord (CA, Achats, Stock, Encours)."""
    logger.info("[BI] dashboard | schema=%s | source=%s", req.client_schema, req.source_type)
    return dashboard_uc.execute(req)


def get_objectifs(client_schema: str) -> ObjectifsResponse:
    """Axes stratégiques calculés dynamiquement depuis les archives."""
    logger.info("[BI] objectifs | schema=%s", client_schema)
    return objectifs_uc.execute(client_schema)


def get_analytique(client_schema: str, date_from: str, date_to: str) -> KpiAnalytiqueResponse:
    """KPIs analytiques avancés (Marge, DSO, Litige, Retour, Conversion, Top Clients)."""
    logger.info("[BI] analytique | schema=%s | %s → %s", client_schema, date_from, date_to)
    return analytique_uc.execute(client_schema, date_from, date_to)


def get_rapport_ca(req: RapportCARequest) -> RapportResponse:
    """Rapport Chiffre d'Affaires groupé par mois, client ou commercial."""
    logger.info("[BI] rapport/ca | schema=%s | group_by=%s", req.client_schema, req.group_by)
    return rapport_ca_uc.execute(req)


def get_top_clients(req: TopClientsRequest) -> RapportResponse:
    """Top N clients par CA sur la période."""
    logger.info("[BI] top-clients | schema=%s | limit=%s", req.client_schema, req.limit)
    return top_clients_uc.execute(req)


def get_top_articles(req: TopArticlesRequest) -> RapportResponse:
    """Top N articles vendus sur la période."""
    logger.info("[BI] top-articles | schema=%s | limit=%s", req.client_schema, req.limit)
    return top_articles_uc.execute(req)


def get_balance_client(req: BalanceClientRequest) -> RapportResponse:
    """Rapport Balance Client."""
    logger.info("[BI] rapport/balance | schema=%s", req.client_schema)
    return balance_uc.execute(req)


def get_rapport_visite(req: RapportVisiteClientRequest) -> RapportResponse:
    """Rapport Client Avant Visite (7 sections)."""
    logger.info("[BI] rapport/visite-client | schema=%s | tiers=%s", req.client_schema, req.do_tiers)
    return rapport_visite_uc.execute(req)
