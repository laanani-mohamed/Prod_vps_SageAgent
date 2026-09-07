"""
bi/transactions/schemas.py — Modèles Pydantic pour le module Transactions.
"""
from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator
import re


# ---------------------------------------------------------------------------
# Sous-modèles de la requête
# ---------------------------------------------------------------------------

class PeriodModel(BaseModel):
    mode: str = Field("none", description="'none' | 'snapshot' | 'range'")
    snapshot_datetime: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class SourceModel(BaseModel):
    type: str = Field("db_latest", description="'db_latest' | 'archive'")
    period: PeriodModel = Field(default_factory=PeriodModel)


class TransactionsFilters(BaseModel):
    do_domaine: List[int] = Field(default_factory=list, description="0=Vente, 1=Achat, 3=Ticket")
    do_type: List[int] = Field(default_factory=list, description="Type de document (ex: 6=Facture, 3=BL, 1=BC)")
    ar_ref: List[str] = Field(default_factory=list, description="Références article (AR_Ref)")
    client_refs: List[str] = Field(default_factory=list, description="Numéros de tiers (CT_Num)")
    collaborateur_ids: List[int] = Field(default_factory=list, description="Numéros de collaborateurs (CO_No)")


class OutputModel(BaseModel):
    format: str = Field("table", description="'table' | 'scalar'")
    limit: int = Field(100000000, ge=1)


# ---------------------------------------------------------------------------
# Requête principale
# ---------------------------------------------------------------------------

class TransactionsRequest(BaseModel):
    client_schema: str = Field(..., description="Schéma PostgreSQL du client (ex: 'client_01')")
    source: SourceModel = Field(default_factory=SourceModel)
    filters: TransactionsFilters = Field(default_factory=TransactionsFilters)
    metrics: List[str] = Field(
        default=["nb_documents"],
        description="'ca_ht' | 'ca_ttc' | 'ca_ht_net' | 'quantite_vendue' | 'prix_unitaire_moyen' | 'montant_regle' | 'marge_brute' | 'nb_documents'"
    )
    group_by: Optional[List[str]] = Field(None, description="Colonnes pour regrouper les résultats")
    output: OutputModel = Field(default_factory=OutputModel)

    @field_validator("client_schema")
    @classmethod
    def validate_client_schema(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", str(v)):
            raise ValueError("Nom de schéma invalide (risque d'injection SQL).")
        return str(v)


# ---------------------------------------------------------------------------
# Réponse
# ---------------------------------------------------------------------------

class TransactionsResponse(BaseModel):
    endpoint: str
    client_schema: str
    source: str
    message: Optional[str] = None
    data: List[dict]
