"""
api/bi/repositories/factory_repo.py

Factory de repositories BI — miroir exact de api/stock/repositories/factory_repo.py.

Sélectionne le repository approprié selon le source_type :
  - "db_latest" → Données PostgreSQL en temps réel
  - "archive"   → Données depuis les fichiers snapshot (.txt)

Usage dans les use cases :
    from api.bi.repositories.factory_repo import get_bi_repo
    repo = get_bi_repo("dashboard", req.source_type)
"""
from api.bi.repositories.base_bi_repo import BaseBIRepository

# ── Imports PG ────────────────────────────────────────────────────────────────
from api.bi.repositories.pg_repo.bi_dashboard_repo import PgBIDashboardRepository
from api.bi.repositories.pg_repo.bi_analytique_repo import PgBIAnalytiqueRepository
from api.bi.repositories.pg_repo.bi_rapport_ca_repo import PgBIRapportCARepository
from api.bi.repositories.pg_repo.bi_top_clients_repo import PgBITopClientsRepository
from api.bi.repositories.pg_repo.bi_top_articles_repo import PgBITopArticlesRepository

# ── Imports Archive ───────────────────────────────────────────────────────────
from api.bi.repositories.archive_repo.bi_dashboard_archive import ArchiveBIDashboardRepository
from api.bi.repositories.archive_repo.bi_analytique_archive import ArchiveBIAnalytiqueRepository
from api.bi.repositories.archive_repo.bi_rapport_ca_archive import ArchiveBIRapportCARepository
from api.bi.repositories.archive_repo.bi_top_clients_archive import ArchiveBITopClientsRepository
from api.bi.repositories.archive_repo.bi_top_articles_archive import ArchiveBITopArticlesRepository


RESOURCE_MAP = {
    "dashboard": {
        "db_latest": PgBIDashboardRepository,
        "archive":   ArchiveBIDashboardRepository,
    },
    "analytique": {
        "db_latest": PgBIAnalytiqueRepository,
        "archive":   ArchiveBIAnalytiqueRepository,
    },
    "rapport_ca": {
        "db_latest": PgBIRapportCARepository,
        "archive":   ArchiveBIRapportCARepository,
    },
    "top_clients": {
        "db_latest": PgBITopClientsRepository,
        "archive":   ArchiveBITopClientsRepository,
    },
    "top_articles": {
        "db_latest": PgBITopArticlesRepository,
        "archive":   ArchiveBITopArticlesRepository,
    },
}


def get_bi_repo(resource: str, source_type: str) -> BaseBIRepository:
    """
    Retourne l'instance du repository approprié pour le module BI.

    Args:
        resource    : Identifiant du use case
                      ("dashboard" | "analytique" | "rapport_ca" | "top_clients" | "top_articles")
        source_type : Source de données ("db_latest" | "archive")

    Raises:
        ValueError : Si le resource ou le source_type est inconnu.
    """
    source_map = RESOURCE_MAP.get(resource)
    if not source_map:
        raise ValueError(f"Ressource BI inconnue pour la factory : '{resource}'")

    repo_class = source_map.get(source_type)
    if not repo_class:
        raise ValueError(
            f"Type de source non supporté pour la BI factory : '{source_type}'. "
            f"Valeurs acceptées : {list(source_map.keys())}"
        )

    return repo_class()
