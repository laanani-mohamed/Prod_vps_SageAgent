"""
api/bi/service.py — Couche service pour le module BI.

Point d'entrée unique appelé par le router.
Délègue chaque endpoint au Use Case correspondant.

Architecture miroir du module stock :
  Router → Service (dispatcher) → Use Case → Business Logic + Repository
"""
from __future__ import annotations
import json
import logging

from fastapi import HTTPException, Response

from api.bi.schemas import (
    DashboardRequest, DashboardResponse,
    ObjectifsResponse, LastUpdateResponse,
    RapportCARequest, TopClientsRequest, TopArticlesRequest,
    RapportResponse, KpiAnalytiqueResponse,
    RapportVisiteClientRequest, ValeurStockRequest,
    RapportConsommationRequest, StatsTiersRequest, RapportRequest, VueRequest, BonCommandeRequest,
)
from api.bi import vues
from api.common.cache import memo
from api.bi.use_cases import (
    dashboard_uc,
    objectifs_uc,
    analytique_uc,
    rapport_ca_uc,
    top_clients_uc,
    top_articles_uc,
    balance_uc,
    balance_agee_uc,
    rapport_visite_uc,
    valeur_stock_uc,
    consommation_uc,
    last_update_uc,
    stats_tiers_uc,
)

logger = logging.getLogger("api.bi.service")

_TYPES_EXPORT = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def get_rapport(req: RapportRequest, nom: str, format: str):
    """Rapport `nom` mis en forme par reporting/ (même logique que la tâche planifiée) :
    JSON (titre, sections, totaux, répartition) ou fichier PDF / Excel."""
    from reporting.generate import construire   # import local : reporting.generate importe ce module
    try:
        rapport, filtres = memo(req.client_schema, f"rapport|{nom}|{json.dumps(req.filtres, sort_keys=True, default=str)}|{req.co_no}",
                                lambda: construire(nom, req.client_schema, req.filtres, req.co_no))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if format == "json":
        return {
            "titre": rapport.titre, "sous_titre": rapport.sous_titre, "filtres": filtres,
            "totaux": rapport.totaux, "repartition": rapport.repartition, "options": rapport.options,
            "sections": [
                {"titre": titre, "colonnes": list(df.columns),
                 "lignes": df.astype(object).where(df.notna(), None).values.tolist()}   # NaN → null (JSON)
                for titre, df in rapport.sections
            ],
        }
    contenu = rapport.pdf(get_last_update(req.client_schema).last_update) if format == "pdf" else rapport.excel()
    return Response(contenu, media_type=_TYPES_EXPORT[format],
                    headers={"Content-Disposition": f'attachment; filename="{rapport.nom}.{format}"'})


def get_vue(req: VueRequest, nom: str):
    """Données prêtes à afficher d'une page du front (api/bi/vues.py)."""
    if nom not in vues.VUES:
        raise HTTPException(status_code=404, detail=f"Vue inconnue '{nom}' (disponibles : {', '.join(vues.VUES)})")
    try:
        return vues.VUES[nom](req.client_schema, req.filtres, req.co_no)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Filtre obligatoire manquant : {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def get_bon_commande(req: BonCommandeRequest):
    """PDF d'un bon de commande client (api/bi/vues.bon_commande)."""
    try:
        nom, contenu = vues.bon_commande(req.client_schema, req.ct_num, [l.model_dump() for l in req.lignes],
                                         req.remise_globale, get_last_update(req.client_schema).last_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(contenu, media_type=_TYPES_EXPORT["pdf"], headers={"Content-Disposition": f'attachment; filename="{nom}"'})


def get_dashboard(req: DashboardRequest) -> DashboardResponse:
    """KPIs du tableau de bord (CA, Achats, Stock, Encours)."""
    logger.info("[BI] dashboard | schema=%s | source=%s", req.client_schema, req.source_type)
    return memo(req.client_schema, f"dashboard|{req.model_dump_json()}", lambda: dashboard_uc.execute(req))


def get_last_update(client_schema: str) -> LastUpdateResponse:
    """Horodatage de la dernière ingestion ETL réussie pour ce client."""
    logger.info("[BI] last-update | schema=%s", client_schema)
    return last_update_uc.execute(client_schema)


def get_objectifs(client_schema: str) -> ObjectifsResponse:
    """Axes stratégiques calculés dynamiquement depuis les archives."""
    logger.info("[BI] objectifs | schema=%s", client_schema)
    return objectifs_uc.execute(client_schema)


def get_analytique(client_schema: str, date_from: str, date_to: str, co_no: list = None) -> KpiAnalytiqueResponse:
    """KPIs analytiques avancés (Marge, DSO, Litige, Retour, Conversion, Top Clients)."""
    logger.info("[BI] analytique | schema=%s | %s → %s", client_schema, date_from, date_to)
    return memo(client_schema, f"analytique|{date_from}|{date_to}|{co_no}", lambda: analytique_uc.execute(client_schema, date_from, date_to, co_no))


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


def get_valeur_stock(req: ValeurStockRequest) -> RapportResponse:
    """Rapport Valeur du Stock (Σ AS_MontSto de f_artstock)."""
    logger.info("[BI] rapport/valeur-stock | schema=%s", req.client_schema)
    return valeur_stock_uc.execute(req)


def get_rapport_consommation(req: RapportConsommationRequest) -> RapportResponse:
    """Consommation des articles par famille/produit (6 mois glissants)."""
    logger.info("[BI] rapport/consommation | schema=%s", req.client_schema)
    return consommation_uc.execute(req)


def get_balance_agee(req: BalanceClientRequest) -> RapportResponse:
    """Balance âgée par clients (tranches en jours : Non Échu, 0-30j, 31-60j, 61-90j, +90j)."""
    logger.info("[BI] rapport/balance-agee | schema=%s", req.client_schema)
    return balance_agee_uc.execute(req)


def get_stats_tiers(req: StatsTiersRequest) -> RapportResponse:
    """Statistiques d'un client ou d'un fournisseur sur une période (vs N-1)."""
    logger.info("[BI] stats-tiers | schema=%s | tiers=%s | type=%s", req.client_schema, req.ct_num, req.ct_type)
    return stats_tiers_uc.execute(req)
