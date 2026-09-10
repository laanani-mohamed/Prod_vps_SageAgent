"""
bi/transactions/service.py — Couche service pour /bi/transactions.
"""
from __future__ import annotations
import os
import glob
import logging
import psycopg2
import polars as pl
from datetime import datetime
from typing import Optional, Sequence

from api.db import get_db_connection
from config.etl_config import ARCHIVE_BASE_PATH
from api.transactions.schemas import TransactionsRequest, TransactionsResponse
from api.transactions.query_builder import build_transactions_query
from map_data.reference.columns_order_number import COLUMNS_ORDER

logger = logging.getLogger("api.transactions.service")


def get_transactions(req: TransactionsRequest, endpoint: str) -> TransactionsResponse:
    if req.source.type == "db_latest":
        return _from_db(req, endpoint)
    elif req.source.type == "archive":
        return _from_archive(req, endpoint)
    else:
        raise ValueError(f"source.type inconnu : {req.source.type}")


# ---------------------------------------------------------------------------
# Mode DB Latest
# ---------------------------------------------------------------------------

def _from_db(req: TransactionsRequest, endpoint: str) -> TransactionsResponse:
    schema = req.client_schema
    sql, params, col_aliases = build_transactions_query(req, schema)

    logger.info(f"[DB] Requête transactions pour {schema} | métriques={req.metrics}")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

            data = [dict(zip(col_aliases, row)) for row in rows]
            message, data = _empty_result_message(data)

            return TransactionsResponse(
                endpoint=endpoint,
                client_schema=schema,
                source="db_latest",
                message=message,
                data=data,
            )

    except psycopg2.Error as e:
        logger.error(f"[DB] Erreur PostgreSQL lors de la requête transactions : {e}")
        raise


# ---------------------------------------------------------------------------
# Mode Archive
# ---------------------------------------------------------------------------

def _from_archive(req: TransactionsRequest, endpoint: str) -> TransactionsResponse:
    schema = req.client_schema
    archive_dir = os.path.join(ARCHIVE_BASE_PATH, schema)

    if not os.path.isdir(archive_dir):
        raise FileNotFoundError(f"Pas d'archives trouvées pour le client : {schema}")

    target_dt = _resolve_target_datetime(req)
    timestamp = _find_closest_snapshot(archive_dir, "F_DOCENTETE", target_dt)
    if not timestamp:
        raise FileNotFoundError(f"Aucun snapshot F_DOCENTETE trouvé dans {archive_dir}")

    df_entete = _load_archive_file(archive_dir, "F_DOCENTETE", timestamp)
    if df_entete is None:
        raise FileNotFoundError(f"Fichier entête introuvable pour {timestamp}")

    # Vérification du besoin des lignes
    need_ligne = False
    m = req.metrics
    ligne_metrics = {"ca_ht", "ca_ttc", "ca_ht_net", "quantite_vendue", "quantite_recue", "prix_unitaire_moyen", "marge_brute"}
    if any(metric in m for metric in ligne_metrics) or req.filters.product_refs or (req.group_by and "ar_ref" in req.group_by):
        need_ligne = True

    df_ligne = None
    if need_ligne:
        df_ligne = _load_archive_file(archive_dir, "F_DOCLIGNE", timestamp)

    # Base DataFrame
    df = df_entete
    if df_ligne is not None:
        df = df.join(df_ligne, on=["do_piece", "do_domaine"], how="inner")

    # Filtres
    f = req.filters
    if f.do_domaine:
        df = df.filter(pl.col("do_domaine").cast(pl.Int64).is_in(f.do_domaine))
    if f.do_type:
        df = df.filter(pl.col("do_type").cast(pl.Int64).is_in(f.do_type))
    if f.client_refs and "do_tiers" in df.columns:
        df = df.filter(pl.col("do_tiers").cast(pl.Utf8).is_in(f.client_refs))
    if f.collaborateur_ids and "co_no" in df.columns:
        df = df.filter(pl.col("co_no").cast(pl.Int64).is_in(f.collaborateur_ids))
    if f.product_refs and "ar_ref" in df.columns:
        df = df.filter(pl.col("ar_ref").cast(pl.Utf8).is_in(f.product_refs))

    period = req.source.period
    if "do_date" in df.columns:
        # Cast do_date if necessary, assuming format YYYY-MM-DD
        if period.start_date:
            df = df.filter(pl.col("do_date") >= period.start_date)
        if period.end_date:
            df = df.filter(pl.col("do_date") <= period.end_date)

    # Calcul des métriques & Group By
    agg_exprs = _build_agg_exprs(m, df.columns)
    if req.group_by:
        valid_group = [g.lower() for g in req.group_by if g.lower() in df.columns]
        if valid_group:
            if agg_exprs:
                df = df.group_by(valid_group).agg(agg_exprs)
            else:
                # Group by simple sans agrégation mathématique définie => retourne le premier
                df = df.group_by(valid_group).first()
    else:
        # Agrégation globale (une seule ligne retournée)
        if agg_exprs:
            df = df.select(agg_exprs)

    # no limit
    data = df.to_dicts()
    message, data = _empty_result_message(data)

    return TransactionsResponse(
        endpoint=endpoint,
        client_schema=schema,
        source=f"archive:{timestamp}",
        message=message,
        data=data,
    )


# ---------------------------------------------------------------------------
# Helpers communs (agrégation, résultat vide)
# ---------------------------------------------------------------------------

def _build_agg_exprs(metrics: Sequence[str], df_columns: Sequence[str]) -> list:
    """Construit les expressions d'agrégation polars pour les métriques demandées,
    communes au group-by et à l'agrégation globale."""
    agg_exprs = []
    if "ca_ht" in metrics and "dl_montantht" in df_columns:
        agg_exprs.append(pl.col("dl_montantht").cast(pl.Float64).sum().alias("ca_ht"))
    if "ca_ttc" in metrics and "dl_montantttc" in df_columns:
        agg_exprs.append(pl.col("dl_montantttc").cast(pl.Float64).sum().alias("ca_ttc"))
    if "quantite_vendue" in metrics and "dl_qte" in df_columns:
        agg_exprs.append(pl.col("dl_qte").cast(pl.Float64).sum().alias("quantite"))
    if "prix_unitaire_moyen" in metrics and "dl_prixunitaire" in df_columns:
        agg_exprs.append(pl.col("dl_prixunitaire").cast(pl.Float64).mean().alias("prix_unitaire_moyen"))
    if "nb_documents" in metrics and "do_piece" in df_columns:
        agg_exprs.append(pl.col("do_piece").n_unique().alias("nb_documents"))

    # Marge brute : SUM((PU - CMUP) * QTE)
    if "marge_brute" in metrics and "dl_prixunitaire" in df_columns and "dl_cmup" in df_columns and "dl_qte" in df_columns:
        agg_exprs.append(
            ((pl.col("dl_prixunitaire").cast(pl.Float64) - pl.col("dl_cmup").cast(pl.Float64).fill_null(0.0)) * pl.col("dl_qte").cast(pl.Float64))
            .sum().alias("marge_brute")
        )
    return agg_exprs


def _empty_result_message(data: list) -> tuple[Optional[str], list]:
    """Détecte un résultat vide (aucune ligne, ou une ligne nb_documents=0/tout null)
    et renvoie (message, data) — data devient [] si le résultat est considéré vide."""
    if not data or (len(data) == 1 and (data[0].get("nb_documents") == 0 or all(v is None for k, v in data[0].items() if k != "nb_documents"))):
        return "transaction introuvable", []
    return None, data


# ---------------------------------------------------------------------------
# Helpers Archive (identiques à stock)
# ---------------------------------------------------------------------------

def _resolve_target_datetime(req: TransactionsRequest) -> Optional[datetime]:
    period = req.source.period
    if period.mode == "snapshot" and period.snapshot_datetime:
        return datetime.fromisoformat(period.snapshot_datetime)
    if period.mode == "range" and period.end_date:
        return datetime.fromisoformat(period.end_date)
    return None

def _find_closest_snapshot(archive_dir: str, table: str, target_dt: Optional[datetime]) -> Optional[str]:
    pattern = os.path.join(archive_dir, f"{table}_*.txt")
    files = glob.glob(pattern)
    if not files: return None

    dated = []
    for filepath in files:
        basename = os.path.basename(filepath)
        try:
            ts_str = basename.replace(f"{table}_", "").replace(".txt", "")
            dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            dated.append((ts_str, dt))
        except ValueError:
            continue

    if not dated: return None
    if target_dt is None: return max(dated, key=lambda x: x[1])[0]

    same_minute = [(ts, dt) for ts, dt in dated if dt.replace(second=0, microsecond=0) == target_dt.replace(second=0, microsecond=0)]
    if same_minute: return min(same_minute, key=lambda x: abs((x[1] - target_dt).total_seconds()))[0]

    same_hour = [(ts, dt) for ts, dt in dated if dt.replace(minute=0, second=0, microsecond=0) == target_dt.replace(minute=0, second=0, microsecond=0)]
    if same_hour: return min(same_hour, key=lambda x: abs((x[1] - target_dt).total_seconds()))[0]

    before = [(ts, dt) for ts, dt in dated if dt <= target_dt]
    if before: return max(before, key=lambda x: x[1])[0]

    return min(dated, key=lambda x: x[1])[0]

def _load_archive_file(archive_dir: str, table: str, timestamp: str) -> Optional[pl.DataFrame]:
    filepath = os.path.join(archive_dir, f"{table}_{timestamp}.txt")
    if not os.path.exists(filepath): return None

    columns = COLUMNS_ORDER.get(table.upper())
    # Attention: pour F_DOCENTETE et F_DOCLIGNE il n'y a peut être pas de config dans columns_order.py.
    # On va les définir si manquant.
    if not columns:
        if table.upper() == "F_DOCENTETE":
            columns = ["do_domaine", "do_type", "do_piece", "do_date", "do_ref", "do_tiers", "co_no", "do_totalht", "do_totalhtnet", "do_totalttc", "do_montantregle"]
        elif table.upper() == "F_DOCLIGNE":
            columns = ["do_domaine", "do_type", "ct_num", "do_piece", "dl_piecebc", "dl_piecebl", "do_date", "dl_datebc", "dl_datebl", "dl_ligne", "do_ref", "ar_ref", "dl_design", "dl_qte", "dl_qtebc", "dl_qtebl", "dl_prixunitaire", "co_no", "dl_prixru", "dl_cmup", "dl_puttc", "dl_no", "dl_valorise", "dl_nonlivre", "dl_montantht", "dl_montantttc", "pf_num", "dl_datede", "dl_qtede"]
        else:
            return None

    try:
        with open(filepath, "rb") as f:
            content = f.read()
            if content.startswith(b"\xef\xbb\xbf"): content = content[3:]
        
        df = pl.read_csv(
            content, separator="\t", has_header=False, new_columns=columns,
            quote_char=None, truncate_ragged_lines=True, infer_schema_length=0,
            null_values=["", "NULL"], encoding="utf8-lossy",
        )
        # Nettoyage espace autour des noms de colonnes/donnees
        return df
    except Exception as e:
        logger.error(f"[Archive] Erreur lecture {filepath} : {e}")
        return None
