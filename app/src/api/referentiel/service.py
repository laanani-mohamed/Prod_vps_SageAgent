"""
bi/referentiel/service.py — Couche service pour le module Référentiel.

Architecture :
  - get_specific()       : NOUVEAU (Intent-driven, Use Cases)
"""
from __future__ import annotations
import logging
from typing import Any, Callable

from api.referentiel.schemas import ReferentielResponse

# Use Cases
from api.referentiel.use_cases import (
    comptes_tiers_uc,
    collaborateur_uc,
    article_detail_uc,
    famille_uc,
    lot_serie_uc,
    doc_entete_uc,
    doc_ligne_uc,
    stock_depot_uc,
    reglement_uc,
)

logger = logging.getLogger("api.referentiel.service")

# ===========================================================================
# ROUTEUR DES NOUVEAUX ENDPOINTS (V2)
# ===========================================================================

RESOURCE_HANDLERS: dict[str, Callable[[Any], ReferentielResponse]] = {
    "/api/referentiel/comptes-tiers": comptes_tiers_uc.execute,
    "/api/referentiel/collaborateurs": collaborateur_uc.execute,
    "/api/referentiel/articles/detail": article_detail_uc.execute,
    "/api/referentiel/familles": famille_uc.execute,
    "/api/referentiel/lots-series": lot_serie_uc.execute,
    "/api/referentiel/documents-entete": doc_entete_uc.execute,
    "/api/referentiel/documents-ligne": doc_ligne_uc.execute,
    "/api/referentiel/stock-depot": stock_depot_uc.execute,
    "/api/referentiel/reglements": reglement_uc.execute,
}

def get_specific(req: Any, endpoint: str) -> ReferentielResponse:
    """Route vers le bon Use Case pour les requêtes spécifiques v2."""
    handler = RESOURCE_HANDLERS.get(endpoint)
    if not handler:
        raise ValueError(f"Endpoint spécifique non géré : {endpoint}")
    
    # --- DEBUT SOLUTION FILTRES INDEPENDANTS ---
    if hasattr(req, "model_fields_set") and hasattr(req, "model_fields"):
        system_fields = {
            "client_schema", "source_type", "snapshot_datetime", "limit",
            "with_stock", "with_lots", "with_articles_count", "with_articles_names", "with_entete",
            "montant_regle_unpaid", "only_active", "only_rupture"
        }
        for field, field_info in req.model_fields.items():
            if field not in system_fields and field not in req.model_fields_set:
                anno_str = str(field_info.annotation).lower()
                if "list" in anno_str:
                    setattr(req, field, [])
                else:
                    setattr(req, field, None)
    # --- FIN SOLUTION ---

    logger.info(f"[Referentiel] endpoint={endpoint} | schema={req.client_schema} | source={req.source_type}")
    return handler(req)
