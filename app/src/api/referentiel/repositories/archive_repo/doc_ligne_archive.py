"""
bi/referentiel/repositories/archive_repo/doc_ligne_archive.py
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot, load_archive_file


class ArchiveDocLigneRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        df, ts = require_snapshot(archive_dir, "F_DOCLIGNE", req)
        
        HARD_LIMIT = min(req.limit * 4, 2000)

        # Filtres réducteurs immédiats
        if req.do_domaine:
            df = df.filter(pl.col("do_domaine").cast(pl.Int64).is_in(req.do_domaine))
        if req.do_type:
            df = df.filter(pl.col("do_type").cast(pl.Int64).is_in(req.do_type))
        if req.do_piece:
            df = df.filter(pl.col("do_piece").is_in(req.do_piece))
        if req.ar_ref:
            df = df.filter(pl.col("ar_ref").is_in(req.ar_ref))
        if req.ct_num:
            df = df.filter(pl.col("ct_num").is_in(req.ct_num))
        if req.co_no:
            df = df.filter(pl.col("co_no").cast(pl.Int64).is_in(req.co_no))
        if req.do_date:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) == req.do_date)
        if req.date_from:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) >= req.date_from)
        if req.date_to:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) <= req.date_to)
        if req.dl_design:
            df = df.filter(pl.col("dl_design").cast(pl.Utf8).str.to_lowercase().str.contains(req.dl_design.lower()))
        if req.pf_num:
            df = df.filter(pl.col("pf_num").cast(pl.Utf8) == req.pf_num)
        if req.dl_nonlivre is not None:
            df = df.filter(pl.col("dl_nonlivre").cast(pl.Utf8) == str(req.dl_nonlivre))
        if req.dl_valorise is not None:
            df = df.filter(pl.col("dl_valorise").cast(pl.Utf8) == str(req.dl_valorise))

        df_tiers = load_archive_file(archive_dir, "F_COMPTET", ts)
        df_art = load_archive_file(archive_dir, "F_ARTICLE", ts)
        df_col = load_archive_file(archive_dir, "F_COLLABORATEUR", ts)

        if df_tiers is not None:
            df = df.join(df_tiers.select(["ct_num", "ct_intitule"]), on="ct_num", how="left")
        if df_art is not None:
            df = df.join(df_art.select(["ar_ref", "ar_design"]).rename({"ar_design": "ar_design_catalogue"}), on="ar_ref", how="left")
        if df_col is not None:
            df = df.join(df_col.select(["co_no", "co_nom"]), on="co_no", how="left")

        if req.with_entete:
            df_entete = load_archive_file(archive_dir, "F_DOCENTETE", ts)
            if df_entete is not None:
                pieces = df.select("do_piece").unique().to_series().to_list()
                df_entete = df_entete.filter(pl.col("do_piece").is_in(pieces))
                df_entete = df_entete.select([
                    "do_piece", "do_domaine", "do_totalht", "do_totalttc", "do_montantregle"
                ])
                df = df.join(
                    df_entete.drop("do_domaine"),
                    on="do_piece",
                    how="left"
                )

        if req.dl_qte_min is not None:
            df = df.filter(pl.col("dl_qte").cast(pl.Float64) >= req.dl_qte_min)
        if req.dl_montantht_min is not None:
            df = df.filter(pl.col("dl_montantht").cast(pl.Float64) >= req.dl_montantht_min)

        df = df.sort(["do_piece", "dl_ligne"])
        data = df.to_dicts()
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
