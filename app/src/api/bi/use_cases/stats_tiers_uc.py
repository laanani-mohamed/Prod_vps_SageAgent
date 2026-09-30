"""
api/bi/use_cases/stats_tiers_uc.py

Use Case : POST /api/bi/stats-tiers
Statistiques d'un client (ct_type=0) ou d'un fournisseur (ct_type=1) sur une période,
comparée à la même période un an plus tôt.
Orchestre : repository PG → business_logic (Polars) → réponse Pydantic.
"""
from __future__ import annotations
import logging

from api.bi.schemas import StatsTiersRequest, RapportResponse
from api.bi.repositories.pg_repo.bi_stats_tiers_repo import (
    PgBIStatsTiersRepository, TYPES_FACTURE, TYPE_DEVIS_VENTE, TYPE_BL_ACHAT, TYPE_RETOUR_ACHAT,
)
from api.bi.business_logic.stats_tiers_calculations import stats_client, stats_fournisseur, un_an_avant

logger = logging.getLogger("api.bi.use_cases.stats_tiers")


def execute(req: StatsTiersRequest) -> RapportResponse:
    repo = PgBIStatsTiersRepository()
    factures = TYPES_FACTURE[req.ct_type]
    from_n1, to_n1 = un_an_avant(req.date_from), un_an_avant(req.date_to)

    ent_n1 = repo.fetch_entetes(req, factures, from_n1, to_n1)
    solde = repo.fetch_solde(req)

    if req.ct_type == 0:
        ent = repo.fetch_entetes(req, factures + [TYPE_DEVIS_VENTE], req.date_from, req.date_to)
        lignes = repo.fetch_lignes(req, factures)
        data = stats_client(ent, ent_n1, lignes, solde, req.date_from, req.date_to)
    else:
        ent = repo.fetch_entetes(req, factures + [TYPE_RETOUR_ACHAT], req.date_from, req.date_to)
        # BL inclus uniquement pour les délais de livraison (prix et montants : factures seules)
        lignes = repo.fetch_lignes(req, factures + [TYPE_BL_ACHAT])
        refs = sorted({l["ar_ref"] for l in lignes if l.get("ar_ref") and l["do_type"] in factures})
        data = stats_fournisseur(
            ent, ent_n1, lignes, solde,
            repo.fetch_achats_par_fournisseur(req), repo.fetch_prix_fournisseurs(req, refs),
            req.ct_num, req.date_from, req.date_to,
        )

    data["periode"] = {"date_from": req.date_from, "date_to": req.date_to, "date_from_n1": from_n1, "date_to_n1": to_n1}
    return RapportResponse(
        endpoint="/api/bi/stats-tiers",
        client_schema=req.client_schema,
        source="db_latest",
        total_rows=1,
        data=[data],
    )
