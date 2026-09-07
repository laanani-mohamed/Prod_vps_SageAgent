"""
api/bi/use_cases/analytique_uc.py

Use Case : GET /api/bi/dashboard/analytique
Orchestre : PgBIAnalytiqueRepository (db_latest) → business_logic analytique → réponse Pydantic.
"""
from __future__ import annotations
import logging
from datetime import date as _date

import polars as pl

from api.bi.schemas import KpiAnalytiqueResponse
from api.bi.repositories.pg_repo.bi_analytique_repo import PgBIAnalytiqueRepository
from api.bi.business_logic.analytique_calculations import (
    prepare_docentete_analytique,
    prepare_docligne_analytique,
    join_article_to_docligne,
    add_cout_cascade,
    calc_dso,
    calc_taux_impayes,
    calc_taux_retour,
    calc_taux_conversion,
    calc_marge_brute,
    calc_top_clients,
    calc_top_fournisseurs,
    calc_top_familles,
    calc_top_articles_par_famille,
)

logger = logging.getLogger("api.bi.use_cases.analytique")


def execute(client_schema: str, date_from: str, date_to: str) -> KpiAnalytiqueResponse:
    result = KpiAnalytiqueResponse(
        client_schema=client_schema,
        periode_from=date_from,
        periode_to=date_to,
    )

    try:
        # Calcul de la durée de la période
        try:
            d_from = _date.fromisoformat(date_from)
            d_to   = _date.fromisoformat(date_to)
            nb_jours = max((d_to - d_from).days, 1)
        except Exception:
            nb_jours = 365
        result.nb_jours_periode = nb_jours

        # Créer une requête pour le repo
        class _Req:
            def __init__(self):
                self.client_schema = client_schema
                self.date_from = None   # Le repo retourne tout, le filtre est fait en Polars
                self.date_to   = None
                self.source_type = "db_latest"

        req = _Req()
        repo = PgBIAnalytiqueRepository()

        # ====================================================================
        # F_DOCENTETE : DSO, Taux Impayés, Taux Retour, Taux Conversion
        # ====================================================================
        df_enc_all = None
        df_e = None

        rows_e = repo.fetch(req)
        if rows_e:
            df_e_raw = pl.from_dicts(rows_e, infer_schema_length=500)
            df_e = prepare_docentete_analytique(df_e_raw)

            # Filtre période YTD
            df_ytd = df_e.filter(
                (pl.col("do_date_str") >= date_from) &
                (pl.col("do_date_str") <= date_to)
            )

            df_fac = df_ytd.filter((pl.col("do_domaine") == 0) & (pl.col("do_type").is_in([6, 7])))
            df_br  = df_ytd.filter((pl.col("do_domaine") == 0) & (pl.col("do_type") == 4))

            # Encours all-time (pour DSO et top clients)
            df_enc_all = df_e.filter(
                (pl.col("do_domaine") == 0) & (pl.col("do_type").is_in([6, 7]))
            ).with_columns(
                (pl.col("do_totalttc_f") - pl.col("do_montantregle_f")).alias("reste")
            ).filter(pl.col("reste") > 0)

            # DSO
            ca_ttc, encours_ttc, dso = calc_dso(df_fac, df_enc_all, nb_jours)
            result.ca_ttc_ytd  = ca_ttc
            result.encours_ttc = encours_ttc
            result.dso_jours   = dso

            # Taux impayés
            df_all_fac = df_e.filter((pl.col("do_domaine") == 0) & (pl.col("do_type").is_in([6, 7])))
            nb_total, nb_impayes, taux_impayes = calc_taux_impayes(df_all_fac)
            result.nb_factures_total    = nb_total
            result.nb_factures_impayees = nb_impayes
            result.taux_impayes         = taux_impayes

            # Taux de retour
            nb_br, nb_fac, taux_retour = calc_taux_retour(df_br, df_fac)
            result.nb_bon_retour = nb_br
            result.nb_fac        = nb_fac
            result.taux_retour   = taux_retour

            # Taux de conversion Devis → Facture
            df_devis = df_ytd.filter((pl.col("do_domaine") == 0) & (pl.col("do_type") == 0))
            nb_devis, nb_conv, taux_conv = calc_taux_conversion(df_devis, df_fac)
            result.nb_devis          = nb_devis
            result.nb_bc_issus_devis = nb_conv
            result.taux_conversion   = taux_conv

        # ====================================================================
        # F_DOCLIGNE : Marge, Top Clients, Top Familles, Top Articles
        # ====================================================================
        rows_dl = repo.fetch_docligne(req)
        if rows_dl:
            df_dl_raw = pl.from_dicts(rows_dl, infer_schema_length=500)
            df_dl = prepare_docligne_analytique(df_dl_raw)
            df_dl = add_cout_cascade(df_dl)

            # Filtre période YTD sur les lignes
            df_dl_ytd = df_dl.filter(
                (pl.col("do_date_str") >= date_from) &
                (pl.col("do_date_str") <= date_to)
            )
            df_lig_vte = df_dl_ytd.filter(
                (pl.col("do_domaine") == 0) & (pl.col("do_type").is_in([6, 7]))
            )

            # Marge Brute
            marge, taux_marge = calc_marge_brute(df_lig_vte)
            result.marge_brute = marge
            result.taux_marge  = taux_marge

            # Tiers pour top clients / fournisseurs
            df_ct = None
            try:
                rows_ct = repo.fetch_comptet(req)
                if rows_ct:
                    df_ct = pl.from_dicts(rows_ct, infer_schema_length=500)
            except Exception as exc:
                logger.warning("[BI/analytique] fetch_comptet : %s", exc)

            # Top Clients
            if df_enc_all is not None:
                result.top_clients = calc_top_clients(df_lig_vte, df_enc_all, df_ct)

            # Top Fournisseurs
            if df_e is not None:
                result.top_fournisseurs = calc_top_fournisseurs(df_e, df_ct)

            # Familles pour top familles / top articles
            df_fam_ref = None
            try:
                rows_fam = repo.fetch_famille(req)
                if rows_fam:
                    df_fam_ref = pl.from_dicts(rows_fam, infer_schema_length=500)
            except Exception as exc:
                logger.warning("[BI/analytique] fetch_famille : %s", exc)

            result.top_familles = calc_top_familles(df_lig_vte, df_fam_ref)

            fa_codes = [r["fa_codefamille"] for r in result.top_familles]
            result.top_articles_par_famille = calc_top_articles_par_famille(df_lig_vte, fa_codes)

    except Exception as exc:
        logger.warning("[BI/analytique] Erreur calcul KPIs analytiques : %s", exc)

    return result
