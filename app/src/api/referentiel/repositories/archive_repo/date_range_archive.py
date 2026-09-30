"""
api/referentiel/repositories/archive_repo/date_range_archive.py

MIN/MAX de do_date sur un snapshot d'archive (même contrat que PgDateRangeRepository).
"""
import polars as pl
from api.referentiel.repositories.base_repo import BaseReferentielRepository
from api.referentiel.repositories.archive_repo._loader import get_archive_dir, require_snapshot, load_archive_file

_KEYS = ["do_domaine", "do_type", "do_piece"]


def _keep_in(df: pl.DataFrame, col: str, values: list) -> pl.DataFrame:
    if not values:
        return df
    return df.filter(pl.col(col).cast(pl.Utf8).is_in([str(v) for v in values]))


class ArchiveDateRangeRepository(BaseReferentielRepository):
    def fetch(self, req):
        archive_dir = get_archive_dir(req.client_schema)
        table = req.table or "docentete"

        if table == "reglement":
            df, ts = require_snapshot(archive_dir, "F_REGLECH", req)
            df_ent = load_archive_file(archive_dir, "F_DOCENTETE", ts)
            if df_ent is None:
                return [{"date_min": None, "date_max": None, "__source_timestamp__": ts}]
            df = df.select(_KEYS).join(df_ent.select(_KEYS + ["do_date", "do_tiers"]), on=_KEYS, how="inner")
            df = _keep_in(df, "do_tiers", req.do_tiers)
        else:
            df, ts = require_snapshot(archive_dir, "F_DOCLIGNE" if table == "docligne" else "F_DOCENTETE", req)
            if table == "docligne":
                df = _keep_in(df, "ar_ref", req.ar_ref)
                df = _keep_in(df, "ct_num", req.do_tiers)
            else:
                df = _keep_in(df, "do_tiers", req.do_tiers)

        df = _keep_in(df, "do_domaine", req.do_domaine)
        df = _keep_in(df, "do_type", req.do_type)

        dates = (
            df.select(pl.col("do_date").cast(pl.Utf8).str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("d"))
            .drop_nulls()
        )
        if dates.is_empty():
            date_min = date_max = None
        else:
            date_min, date_max = dates["d"].min(), dates["d"].max()
        return [{"date_min": date_min, "date_max": date_max, "__source_timestamp__": ts}]
