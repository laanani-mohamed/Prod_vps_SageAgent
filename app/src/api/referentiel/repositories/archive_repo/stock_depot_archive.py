"""
bi/referentiel/repositories/archive_repo/stock_depot_archive.py
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot, load_archive_file


class ArchiveStockDepotRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        df, ts = require_snapshot(archive_dir, "F_ARTSTOCK", req)

        df_art = load_archive_file(archive_dir, "F_ARTICLE", ts)
        df_depot = load_archive_file(archive_dir, "F_DEPOT", ts)
        df_fam = load_archive_file(archive_dir, "F_FAMILLE", ts)
        df_unite = load_archive_file(archive_dir, "P_UNITE", ts)

        if df_art is not None:
            df = df.join(df_art, on="ar_ref", how="left")
        if df_depot is not None:
            df = df.join(df_depot, on="de_no", how="left")
        if df_fam is not None:
            df = df.join(df_fam.select(["fa_codefamille", "fa_intitule"]), on="fa_codefamille", how="left")
        if df_unite is not None:
            df = df.join(df_unite.rename({"cbindice": "ar_uniteven"}), on="ar_uniteven", how="left")

        if req.ar_ref:
            df = df.filter(pl.col("ar_ref").is_in(req.ar_ref))
        if req.de_no:
            df = df.filter(pl.col("de_no").cast(pl.Int64).is_in(req.de_no))
        if req.fa_codefamille:
            df = df.filter(pl.col("fa_codefamille").is_in(req.fa_codefamille))
        if req.ar_suivistock:
            df = df.filter(pl.col("ar_suivistock").cast(pl.Int64).is_in(req.ar_suivistock))
        if req.ar_sommeil is not None:
            df = df.filter(pl.col("ar_sommeil").cast(pl.Utf8) == str(req.ar_sommeil))
        if req.qte_min is not None:
            df = df.filter(pl.col("as_qtesto").cast(pl.Float64) >= req.qte_min)
        if req.qte_max is not None:
            df = df.filter(pl.col("as_qtesto").cast(pl.Float64) <= req.qte_max)
        if req.only_rupture:
            df = df.filter(pl.col("as_qtesto").cast(pl.Float64) <= 0)

        df = df.sort(["fa_codefamille", "ar_ref", "de_no"])
        data = df.to_dicts()
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
