import os
import glob
import logging
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional
import polars as pl

from api.stock.repositories.base_repo import BaseStockRepository
from config.etl_config import ARCHIVE_BASE_PATH
from map_data.reference.columns_order_number import COLUMNS_ORDER

logger = logging.getLogger("api.stock.repositories.archive")

class BaseArchiveStockRepository(BaseStockRepository):
    def _resolve_target_datetime(self, req) -> Optional[datetime]:
        snap = getattr(req, "snapshot_datetime", None)
        if snap:
            try:
                return datetime.fromisoformat(snap)
            except ValueError:
                return None
        
        # Fallback date_from (for comparison)
        date_from = getattr(req, "date_from", None)
        if date_from:
            try:
                return datetime.fromisoformat(f"{date_from}T23:59:59")
            except ValueError:
                return None
        return None

    def _find_closest_snapshot(self, archive_dir: str, table: str, target_dt: Optional[datetime]) -> Optional[str]:
        pattern = os.path.join(archive_dir, f"{table}_*.txt")
        files = glob.glob(pattern)
        if not files:
            return None

        dated: list[tuple[str, datetime]] = []
        for filepath in files:
            basename = os.path.basename(filepath)
            try:
                ts_str = basename.replace(f"{table}_", "").replace(".txt", "")
                dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                dated.append((ts_str, dt))
            except ValueError:
                continue

        if not dated:
            return None

        if target_dt is None:
            best_ts, _ = max(dated, key=lambda x: x[1])
            return best_ts

        same_minute = [
            (ts, dt) for ts, dt in dated
            if (dt.year, dt.month, dt.day, dt.hour, dt.minute)
            == (target_dt.year, target_dt.month, target_dt.day,
                target_dt.hour, target_dt.minute)
        ]
        if same_minute:
            best_ts, _ = min(same_minute, key=lambda x: abs((x[1] - target_dt).total_seconds()))
            return best_ts

        same_hour = [
            (ts, dt) for ts, dt in dated
            if (dt.year, dt.month, dt.day, dt.hour)
            == (target_dt.year, target_dt.month, target_dt.day, target_dt.hour)
        ]
        if same_hour:
            best_ts, _ = min(same_hour, key=lambda x: abs((x[1] - target_dt).total_seconds()))
            return best_ts

        before = [(ts, dt) for ts, dt in dated if dt <= target_dt]
        if before:
            best_ts, _ = max(before, key=lambda x: x[1])
            return best_ts

        best_ts, _ = min(dated, key=lambda x: x[1])
        return best_ts

    def _load_archive_file(self, archive_dir: str, table: str, timestamp: str) -> Optional[pl.DataFrame]:
        filepath = os.path.join(archive_dir, f"{table}_{timestamp}.txt")
        if not os.path.exists(filepath):
            return None

        columns = COLUMNS_ORDER.get(table.upper())
        if not columns:
            return None

        try:
            with open(filepath, "rb") as f:
                content = f.read()
                if content.startswith(b"\xef\xbb\xbf"):
                    content = content[3:]

            df = pl.read_csv(
                content,
                separator="\t",
                has_header=False,
                new_columns=columns,
                quote_char=None,
                truncate_ragged_lines=True,
                infer_schema_length=0,
                null_values=["", "NULL"],
                encoding="utf8-lossy",
            )
            return df
        except Exception as e:
            logger.error(f"[Archive] Erreur lecture {filepath} : {e}")
            return None

    def _apply_filters(self, df: pl.DataFrame, req) -> pl.DataFrame:
        if "ar_sommeil" in df.columns and hasattr(req, "ar_sommeil") and req.ar_sommeil is not None:
            df = df.filter(pl.col("ar_sommeil").cast(pl.Utf8) == str(req.ar_sommeil))

        if getattr(req, "fa_codefamille", None) and "fa_codefamille" in df.columns:
            df = df.filter(pl.col("fa_codefamille").is_in(req.fa_codefamille))

        if getattr(req, "ar_suivistock", None) and "ar_suivistock" in df.columns:
            vals = [str(v) for v in req.ar_suivistock]
            df = df.filter(pl.col("ar_suivistock").cast(pl.Utf8).is_in(vals))

        if getattr(req, "ar_nature", None) and "ar_nature" in df.columns:
            vals = [str(v) for v in req.ar_nature]
            df = df.filter(pl.col("ar_nature").cast(pl.Utf8).is_in(vals))

        if getattr(req, "ar_type", None) and "ar_type" in df.columns:
            vals = [str(v) for v in req.ar_type]
            df = df.filter(pl.col("ar_type").cast(pl.Utf8).is_in(vals))

        # Combiner OR entre refs, design et search_terms
        search_expr = pl.lit(False)
        has_search_cond = False
        
        ar_ref = getattr(req, "ar_ref", None)
        if ar_ref:
            exact_refs  = [r for r in ar_ref if len(r) > 7]
            prefix_refs = [r for r in ar_ref if len(r) <= 7]

            if exact_refs:
                search_expr = search_expr | pl.col("ar_ref").is_in(exact_refs)
                has_search_cond = True
            for prefix in prefix_refs:
                search_expr = search_expr | pl.col("ar_ref").str.starts_with(prefix)
                has_search_cond = True

        ar_design = getattr(req, "ar_design", None)
        if ar_design and "ar_design" in df.columns:
            search_expr = search_expr | pl.col("ar_design").str.contains(f"(?i){ar_design}")
            has_search_cond = True

        search_terms = getattr(req, "search_terms", None) or []
        if search_terms and "ar_design" in df.columns:
            for t in search_terms:
                search_expr = search_expr | pl.col("ar_design").str.contains(f"(?i){t}")
            has_search_cond = True

        if has_search_cond:
            df = df.filter(search_expr)

        return df

    def _load_snapshot_as_df(self, archive_dir: str, timestamp: str, req) -> pl.DataFrame:
        df_stock = self._load_archive_file(archive_dir, "F_ARTSTOCK", timestamp)
        df_article = self._load_archive_file(archive_dir, "F_ARTICLE", timestamp)
        df_depot = self._load_archive_file(archive_dir, "F_DEPOT", timestamp)

        if df_stock is None or df_article is None:
            raise FileNotFoundError(f"Fichiers archive manquants pour {timestamp}")

        # Filtre depot_ids
        depot_ids = getattr(req, "depot_ids", None)
        if depot_ids and "de_no" in df_stock.columns:
            str_ids = [str(d) for d in depot_ids]
            df_stock = df_stock.filter(pl.col("de_no").cast(pl.Utf8).is_in(str_ids))

        df = df_article.join(df_stock, on="ar_ref", how="left")
        if df_depot is not None:
            df = df.join(df_depot, on="de_no", how="left")

        df = self._apply_filters(df, req)
        return df

    def _get_base_df(self, req) -> Tuple[pl.DataFrame, str]:
        schema = req.client_schema
        archive_dir = os.path.join(ARCHIVE_BASE_PATH, schema)

        if not os.path.isdir(archive_dir):
            raise FileNotFoundError(f"Pas d'archives pour le client : {schema}")

        target_dt = self._resolve_target_datetime(req)
        timestamp = self._find_closest_snapshot(archive_dir, "F_ARTSTOCK", target_dt)
        if not timestamp:
            raise FileNotFoundError(f"Aucun snapshot F_ARTSTOCK trouvé dans {archive_dir}")

        df = self._load_snapshot_as_df(archive_dir, timestamp, req)
        return df, timestamp

    def _sort_and_limit(self, df: pl.DataFrame, req) -> Tuple[List[Dict[str, Any]], List[str]]:
        sort_by = getattr(req, "sort_by", None)
        if sort_by == "qty_desc" and "quantite_totale" in df.columns:
            df = df.sort("quantite_totale", descending=True)
        elif sort_by == "qty_asc" and "quantite_totale" in df.columns:
            df = df.sort("quantite_totale", descending=False)
        elif sort_by == "name" and "ar_design" in df.columns:
            df = df.sort("ar_design", descending=False)

        # no limit
        return df.to_dicts(), list(df.columns)
