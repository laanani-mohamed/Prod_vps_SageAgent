"""
bi/referentiel/repositories/archive_repo/famille_archive.py
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot, load_archive_file


class ArchiveFamilleRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        df, ts = require_snapshot(archive_dir, "F_FAMILLE", req)

        df_unite = load_archive_file(archive_dir, "P_UNITE", ts)
        if df_unite is not None:
            df = df.join(df_unite.rename({"cbindice": "fa_uniteven"}), on="fa_uniteven", how="left")

        if req.fa_codefamille:
            df = df.filter(pl.col("fa_codefamille").is_in(req.fa_codefamille))
        if req.fa_intitule:
            df = df.filter(pl.col("fa_intitule").cast(pl.Utf8).str.to_lowercase().str.contains(req.fa_intitule.lower()))
        if req.fa_type:
            df = df.filter(pl.col("fa_type").cast(pl.Int64).is_in(req.fa_type))
        if req.fa_central:
            df = df.filter(pl.col("fa_central").cast(pl.Utf8) == req.fa_central)
        if req.fa_suivistock:
            df = df.filter(pl.col("fa_suivistock").cast(pl.Int64).is_in(req.fa_suivistock))

        if req.with_articles_count:
            df_art = load_archive_file(archive_dir, "F_ARTICLE", ts)
            if df_art is not None:
                df_art = df_art.filter(pl.col("ar_sommeil").cast(pl.Utf8) == "0")
                agg = df_art.group_by("fa_codefamille").agg(pl.len().alias("nb_articles"))
                df = df.join(agg, on="fa_codefamille", how="left")

        df = df.sort("fa_codefamille")
        data = df.to_dicts()
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
