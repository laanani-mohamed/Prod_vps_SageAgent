"""
bi/referentiel/repositories/archive_repo/lot_serie_archive.py
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot, load_archive_file


class ArchiveLotSerieRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        df, ts = require_snapshot(archive_dir, "F_LOTSERIE", req)

        df_art = load_archive_file(archive_dir, "F_ARTICLE", ts)
        df_depot = load_archive_file(archive_dir, "F_DEPOT", ts)

        if df_art is not None:
            df = df.join(df_art.select(["ar_ref", "ar_design", "fa_codefamille"]), on="ar_ref", how="left")
        if df_depot is not None:
            df = df.join(df_depot, on="de_no", how="left")

        if req.only_active:
            df = df.filter(pl.col("ls_lotepuise").cast(pl.Utf8) == "0")
        elif req.ls_lotepuise is not None:
            df = df.filter(pl.col("ls_lotepuise").cast(pl.Utf8) == str(req.ls_lotepuise))
            
        if req.ar_ref:
            df = df.filter(pl.col("ar_ref").is_in(req.ar_ref))
        if req.fa_codefamille:
            df = df.filter(pl.col("fa_codefamille").is_in(req.fa_codefamille))
        if req.ls_noserie:
            df = df.filter(pl.col("ls_noserie").cast(pl.Utf8).str.to_lowercase().str.contains(req.ls_noserie.lower()))
        if req.de_no:
            df = df.filter(pl.col("de_no").cast(pl.Int64).is_in(req.de_no))
        if req.peremption_before:
            df = df.filter(pl.col("ls_peremption").cast(pl.Utf8) <= req.peremption_before)
        if req.peremption_after:
            df = df.filter(pl.col("ls_peremption").cast(pl.Utf8) >= req.peremption_after)
        if req.qte_restant_min is not None:
            df = df.filter(pl.col("ls_qterestant").cast(pl.Float64) >= req.qte_restant_min)

        df = df.sort("ls_peremption")
        data = df.to_dicts()
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
