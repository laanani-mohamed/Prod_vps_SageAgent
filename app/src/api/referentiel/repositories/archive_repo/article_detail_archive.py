"""
bi/referentiel/repositories/archive_repo/article_detail_archive.py
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot, load_archive_file


class ArchiveArticleDetailRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        df, ts = require_snapshot(archive_dir, "F_ARTICLE", req)

        df_fam = load_archive_file(archive_dir, "F_FAMILLE", ts)
        df_uni = load_archive_file(archive_dir, "P_UNITE", ts)
        
        if df_fam is not None:
            df = df.join(df_fam.select(["fa_codefamille", "fa_intitule", "fa_type", "fa_suivistock", "fa_central"]), on="fa_codefamille", how="left")
        if df_uni is not None:
            df = df.join(df_uni.rename({"cbindice": "ar_uniteven"}), on="ar_uniteven", how="left")

        # Filtres article
        if req.ar_ref:
            df = df.filter(pl.col("ar_ref").cast(pl.Utf8).str.to_lowercase().str.contains(req.ar_ref.lower()))
        if req.ar_ref_exact:
            df = df.filter(pl.col("ar_ref").is_in(req.ar_ref_exact))
        if req.ar_design:
            mask = pl.lit(False)
            for term in req.ar_design:
                mask = mask | pl.col("ar_design").cast(pl.Utf8).str.to_lowercase().str.contains(term.lower())
            df = df.filter(mask)
        if req.ar_code_barre:
            df = df.filter(pl.col("ar_codebarre").cast(pl.Utf8) == req.ar_code_barre)
        if req.fa_codefamille:
            df = df.filter(pl.col("fa_codefamille").is_in(req.fa_codefamille))
        if req.ar_nature:
            df = df.filter(pl.col("ar_nature").cast(pl.Int64).is_in(req.ar_nature))
        if req.ar_type:
            df = df.filter(pl.col("ar_type").cast(pl.Int64).is_in(req.ar_type))
        if req.ar_suivistock:
            df = df.filter(pl.col("ar_suivistock").cast(pl.Int64).is_in(req.ar_suivistock))
        if req.ar_sommeil is not None:
            df = df.filter(pl.col("ar_sommeil").cast(pl.Utf8) == str(req.ar_sommeil))

        # Enrichissement stock
        if req.with_stock:
            df_stk = load_archive_file(archive_dir, "F_ARTSTOCK", ts)
            if df_stk is not None:
                if req.depot_ids:
                    df_stk = df_stk.filter(pl.col("de_no").cast(pl.Int64).is_in(req.depot_ids))
                df_stk = df_stk.group_by("ar_ref").agg(pl.col("as_qtesto").cast(pl.Float64).sum().alias("qte_stock_totale"))
                df = df.join(df_stk, on="ar_ref", how="left")

        # Enrichissement lots
        if req.with_lots:
            df_lots = load_archive_file(archive_dir, "F_LOTSERIE", ts)
            if df_lots is not None:
                df_lots_active = df_lots.filter(pl.col("ls_lotepuise").cast(pl.Utf8) == "0")
                df_lots_expired = df_lots.filter(pl.col("ls_lotepuise").cast(pl.Utf8) == "1")
                agg_active = df_lots_active.group_by("ar_ref").agg(pl.len().alias("lots_actifs"))
                agg_expired = df_lots_expired.group_by("ar_ref").agg(pl.len().alias("lots_perimes"))
                agg_peremt = df_lots_active.group_by("ar_ref").agg(pl.col("ls_peremption").min().alias("prochaine_peremption"))
                df = df.join(agg_active, on="ar_ref", how="left")
                df = df.join(agg_expired, on="ar_ref", how="left")
                df = df.join(agg_peremt, on="ar_ref", how="left")

        df = df.sort(["fa_codefamille", "ar_ref"])
        data = df.to_dicts()
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
