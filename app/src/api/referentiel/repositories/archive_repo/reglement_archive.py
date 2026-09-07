"""
bi/referentiel/repositories/archive_repo/reglement_archive.py
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot, load_archive_file


class ArchiveReglementRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        df, ts = require_snapshot(archive_dir, "F_REGLECH", req)

        df_doc = load_archive_file(archive_dir, "F_DOCENTETE", ts)
        df_tiers = load_archive_file(archive_dir, "F_COMPTET", ts)

        if df_doc is not None:
            # On joint sur do_piece pour récupérer la date du document (do_date) et le code tiers (do_tiers)
            df = df.join(
                df_doc.select(["do_piece", "do_date", "do_tiers"]),
                on="do_piece",
                how="left"
            )

        if df_tiers is not None:
            df = df.join(
                df_tiers.select(["ct_num", "ct_intitule", "ct_identifiant"]),
                left_on="do_tiers",
                right_on="ct_num",
                how="left"
            )

        # Filtres
        if req.do_domaine:
            df = df.filter(pl.col("do_domaine").cast(pl.Int64).is_in(req.do_domaine))
        if req.do_type:
            df = df.filter(pl.col("do_type").cast(pl.Int64).is_in(req.do_type))
        if req.do_piece:
            df = df.filter(pl.col("do_piece").is_in(req.do_piece))
        if req.rg_typereg:
            df = df.filter(pl.col("rg_typereg").cast(pl.Int64).is_in(req.rg_typereg))
        if req.date_from and "do_date" in df.columns:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) >= req.date_from)
        if req.date_to and "do_date" in df.columns:
            df = df.filter(pl.col("do_date").cast(pl.Utf8) <= req.date_to)

        # Trier par date de document descendante
        if "do_date" in df.columns:
            df = df.sort("do_date", descending=True)

        # no limit
        data = df.to_dicts()
        if data:
            data[0]["__source_timestamp__"] = ts
        return data
