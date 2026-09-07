"""
bi/stock/repositories/factory_repo.py
"""
from api.stock.repositories.base_repo import BaseStockRepository

# Imports PG
from api.stock.repositories.pg_repo.stock_availability_repo import PgStockAvailabilityRepository
from api.stock.repositories.pg_repo.stock_details_repo import PgStockDetailsRepository
from api.stock.repositories.pg_repo.stock_catalog_repo import PgStockCatalogRepository
from api.stock.repositories.pg_repo.stock_insight_repo import PgStockInsightRepository
from api.stock.repositories.pg_repo.stock_snapshot_repo import PgStockSnapshotRepository
from api.stock.repositories.pg_repo.stock_compare_repo import PgStockCompareRepository

# Imports Archive
from api.stock.repositories.archive_repo.stock_availability_archive import ArchiveStockAvailabilityRepository
from api.stock.repositories.archive_repo.stock_details_archive import ArchiveStockDetailsRepository
from api.stock.repositories.archive_repo.stock_catalog_archive import ArchiveStockCatalogRepository
from api.stock.repositories.archive_repo.stock_insight_archive import ArchiveStockInsightRepository
from api.stock.repositories.archive_repo.stock_snapshot_archive import ArchiveStockSnapshotRepository
from api.stock.repositories.archive_repo.stock_compare_archive import ArchiveStockCompareRepository


RESOURCE_MAP = {
    "availability": {
        "db_latest": PgStockAvailabilityRepository,
        "archive": ArchiveStockAvailabilityRepository,
    },
    "details": {
        "db_latest": PgStockDetailsRepository,
        "archive": ArchiveStockDetailsRepository,
    },
    "catalog": {
        "db_latest": PgStockCatalogRepository,
        "archive": ArchiveStockCatalogRepository,
    },
    "insight": {
        "db_latest": PgStockInsightRepository,
        "archive": ArchiveStockInsightRepository,
    },
    "snapshot": {
        "db_latest": PgStockSnapshotRepository,
        "archive": ArchiveStockSnapshotRepository,
    },
    "compare": {
        "db_latest": PgStockCompareRepository,
        "archive": ArchiveStockCompareRepository,
    },
}

def get_repo(resource: str, source_type: str) -> BaseStockRepository:
    """
    Retourne l'instance du repository appropriée pour le module Stock.
    """
    source_map = RESOURCE_MAP.get(resource)
    if not source_map:
        raise ValueError(f"Ressource de stock inconnue pour la factory : {resource}")

    repo_class = source_map.get(source_type)
    if not repo_class:
        raise ValueError(f"Type de source non supporté pour la stock factory : {source_type}")

    return repo_class()
