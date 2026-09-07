"""
bi/referentiel/repositories/factory_repo.py

Factory pour résoudre l'implémentation du repository (PostgreSQL vs Archive)
en fonction de la ressource demandée et de la source.
"""
from api.referentiel.repositories.base_repo import BaseReferentielRepository

# Imports PG
from api.referentiel.repositories.pg_repo.comptes_tiers_repo import PgComptesTiersRepository
from api.referentiel.repositories.pg_repo.collaborateur_repo import PgCollaborateurRepository
from api.referentiel.repositories.pg_repo.article_detail_repo import PgArticleDetailRepository
from api.referentiel.repositories.pg_repo.famille_repo import PgFamilleRepository
from api.referentiel.repositories.pg_repo.lot_serie_repo import PgLotSerieRepository
from api.referentiel.repositories.pg_repo.doc_entete_repo import PgDocEnteteRepository
from api.referentiel.repositories.pg_repo.doc_ligne_repo import PgDocLigneRepository
from api.referentiel.repositories.pg_repo.stock_depot_repo import PgStockDepotRepository
from api.referentiel.repositories.pg_repo.reglement_repo import PgReglementRepository

# Imports Archive
from api.referentiel.repositories.archive_repo.comptes_tiers_archive import ArchiveComptesTiersRepository
from api.referentiel.repositories.archive_repo.collaborateur_archive import ArchiveCollaborateurRepository
from api.referentiel.repositories.archive_repo.article_detail_archive import ArchiveArticleDetailRepository
from api.referentiel.repositories.archive_repo.famille_archive import ArchiveFamilleRepository
from api.referentiel.repositories.archive_repo.lot_serie_archive import ArchiveLotSerieRepository
from api.referentiel.repositories.archive_repo.doc_entete_archive import ArchiveDocEnteteRepository
from api.referentiel.repositories.archive_repo.doc_ligne_archive import ArchiveDocLigneRepository
from api.referentiel.repositories.archive_repo.stock_depot_archive import ArchiveStockDepotRepository
from api.referentiel.repositories.archive_repo.reglement_archive import ArchiveReglementRepository


RESOURCE_MAP = {
    "comptes_tiers": {
        "db_latest": PgComptesTiersRepository,
        "archive": ArchiveComptesTiersRepository,
    },
    "collaborateur": {
        "db_latest": PgCollaborateurRepository,
        "archive": ArchiveCollaborateurRepository,
    },
    "article_detail": {
        "db_latest": PgArticleDetailRepository,
        "archive": ArchiveArticleDetailRepository,
    },
    "famille": {
        "db_latest": PgFamilleRepository,
        "archive": ArchiveFamilleRepository,
    },
    "lot_serie": {
        "db_latest": PgLotSerieRepository,
        "archive": ArchiveLotSerieRepository,
    },
    "doc_entete": {
        "db_latest": PgDocEnteteRepository,
        "archive": ArchiveDocEnteteRepository,
    },
    "doc_ligne": {
        "db_latest": PgDocLigneRepository,
        "archive": ArchiveDocLigneRepository,
    },
    "stock_depot": {
        "db_latest": PgStockDepotRepository,
        "archive": ArchiveStockDepotRepository,
    },
    "reglement": {
        "db_latest": PgReglementRepository,
        "archive": ArchiveReglementRepository,
    },
}

def get_repo(resource: str, source_type: str) -> BaseReferentielRepository:
    """
    Retourne l'instance du repository appropriée.

    Args:
        resource    : Nom de la ressource (ex: "comptes_tiers")
        source_type : "db_latest" ou "archive"

    Raises:
        ValueError si ressource ou type non supporté
    """
    source_map = RESOURCE_MAP.get(resource)
    if not source_map:
        raise ValueError(f"Ressource inconnue pour la factory : {resource}")

    repo_class = source_map.get(source_type)
    if not repo_class:
        raise ValueError(f"Type de source non supporté : {source_type}")

    return repo_class()
