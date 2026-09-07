"""
bi/referentiel/repositories/archive_repo/collaborateur_archive.py
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot


class ArchiveCollaborateurRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        df, ts = require_snapshot(archive_dir, "F_COLLABORATEUR", req)

        if req.co_no:
            df = df.filter(pl.col("co_no").cast(pl.Int64).is_in(req.co_no))
        if req.co_vendeur is not None:
            df = df.filter(pl.col("co_vendeur").cast(pl.Utf8) == str(req.co_vendeur))
        if req.co_acheteur is not None:
            df = df.filter(pl.col("co_acheteur").cast(pl.Utf8) == str(req.co_acheteur))
        if req.co_nom:
            df = df.filter(pl.col("co_nom").cast(pl.Utf8).str.to_lowercase().str.contains(req.co_nom.lower()))
        if req.co_prenom:
            df = df.filter(pl.col("co_prenom").cast(pl.Utf8).str.to_lowercase().str.contains(req.co_prenom.lower()))
        if req.co_fonction:
            df = df.filter(pl.col("co_fonction").cast(pl.Utf8).str.to_lowercase().str.contains(req.co_fonction.lower()))
        if req.co_matricule:
            df = df.filter(pl.col("co_matricule").cast(pl.Utf8).str.to_lowercase().str.contains(req.co_matricule.lower()))
        
        df = df.sort("co_nom")
        data = df.to_dicts()
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
