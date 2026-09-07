"""
bi/referentiel/repositories/archive_repo/doc_entete_archive.py
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot, load_archive_file


class ArchiveDocEnteteRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        df, ts = require_snapshot(archive_dir, "F_DOCENTETE", req)

        df_tiers = load_archive_file(archive_dir, "F_COMPTET", ts)
        df_col = load_archive_file(archive_dir, "F_COLLABORATEUR", ts)

        if df_tiers is not None:
            df = df.join(df_tiers.select(["ct_num", "ct_intitule"]), left_on="do_tiers", right_on="ct_num", how="left")
        if df_col is not None:
            df = df.join(df_col.select(["co_no", "co_nom", "co_prenom"]), on="co_no", how="left")

        if req.do_domaine:
            df = df.filter(pl.col("do_domaine").cast(pl.Int64).is_in(req.do_domaine))
        if req.do_type:
            df = df.filter(pl.col("do_type").cast(pl.Int64).is_in(req.do_type))
        if req.do_piece:
            df = df.filter(pl.col("do_piece").is_in(req.do_piece))
        if req.do_tiers:
            df = df.filter(pl.col("do_tiers").is_in(req.do_tiers))
        if req.co_no:
            df = df.filter(pl.col("co_no").cast(pl.Int64).is_in(req.co_no))
        if req.do_ref:
            df = df.filter(pl.col("do_ref").cast(pl.Utf8).str.to_lowercase().str.contains(req.do_ref.lower()))
        if req.do_date:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) == req.do_date)
        if req.date_from:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) >= req.date_from)
        if req.date_to:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) <= req.date_to)
        if req.do_totalttc_min is not None:
            df = df.filter(pl.col("do_totalttc").cast(pl.Float64) >= req.do_totalttc_min)
        if req.do_totalttc_max is not None:
            df = df.filter(pl.col("do_totalttc").cast(pl.Float64) <= req.do_totalttc_max)

        df = df.sort("do_date", descending=True)
        data = df.to_dicts()
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
