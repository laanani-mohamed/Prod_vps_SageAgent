"""
api/bi/schemas.py — Modèles Pydantic pour le module BI (Dashboard, Rapports).
"""
from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator
import re


# ---------------------------------------------------------------------------
# Requête commune
# ---------------------------------------------------------------------------

class BaseBIRequest(BaseModel):
    client_schema: str = Field(..., description="Schéma PostgreSQL du client")
    source_type: str = Field("db_latest", description="'db_latest' ou 'archive'")
    snapshot_datetime: Optional[str] = Field(
        None,
        description="Pour source_type='archive' : datetime ISO du snapshot (ex: '2026-01-15T08:00:00')"
    )

    @field_validator("client_schema")
    @classmethod
    def validate_client_schema(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", str(v)):
            raise ValueError("Nom de schéma invalide (risque d'injection SQL).")
        return str(v)


# ---------------------------------------------------------------------------
# Dashboard KPI
# ---------------------------------------------------------------------------

class DashboardRequest(BaseBIRequest):
    date_from: Optional[str] = Field(None, description="Date début YYYY-MM-DD")
    date_to: Optional[str] = Field(None, description="Date fin YYYY-MM-DD")


class LastUpdateResponse(BaseModel):
    client_schema: str
    last_update: Optional[str] = Field(
        None, description="Horodatage ISO de la dernière ingestion réussie (PipelineCompleted), ou None si aucune"
    )


class KPIData(BaseModel):
    chiffre_affaires: float = 0.0
    ca_n_minus_1: float = 0.0
    ca_evolution_pct: float = 0.0
    total_achats: float = 0.0
    valeur_stock: float = 0.0
    encours_clients: float = 0.0
    dettes_fournisseurs: float = 0.0
    nb_clients_actifs: int = 0
    ca_evolution_monthly: List[dict] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    client_schema: str
    source: str
    date_from: Optional[str]
    date_to: Optional[str]
    kpis: KPIData
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Objectifs stratégiques (statique + calculé)
# ---------------------------------------------------------------------------

class ObjectifItem(BaseModel):
    axe: str
    objectif: str
    realise: str
    pct_atteinte: Optional[float] = None
    seuil_alerte: str
    statut: str  # "ok" | "warning" | "danger"


class ObjectifsResponse(BaseModel):
    client_schema: str
    objectifs: List[ObjectifItem]


# ---------------------------------------------------------------------------
# Rapports BI
# ---------------------------------------------------------------------------

class RapportCARequest(BaseBIRequest):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    group_by: str = Field("mois", description="'mois' | 'client' | 'famille' | 'commercial' | 'region'")
    limit: int = Field(100000000, ge=1)


class BalanceClientRequest(BaseBIRequest):
    # Pas de date spécifique car le filtre de date est géré automatiquement (jusqu'à la date du jour)
    pass


class RapportVisiteClientRequest(BaseBIRequest):
    do_tiers: str = Field(..., description="Code client (do_tiers / ct_num)")
    date_from: Optional[str] = Field(None, description="Date début (YYYY-MM-DD) — défaut : J-180")
    date_to:   Optional[str] = Field(None, description="Date fin (YYYY-MM-DD) — défaut : aujourd'hui")


class ValeurStockRequest(BaseBIRequest):
    """Rapport Valeur du Stock (DL_CMUP × qté f_artstock)."""
    pass


class RapportConsommationRequest(BaseBIRequest):
    """Consommation des articles par famille/produit — fenêtre 6 mois glissants."""
    date_from: Optional[str] = Field(None, description="Calculé automatiquement (J-180) si absent")
    date_to:   Optional[str] = Field(None, description="Calculé automatiquement (aujourd'hui) si absent")


class TopClientsRequest(BaseBIRequest):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = Field(100000000, ge=1)


class TopArticlesRequest(BaseBIRequest):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = Field(100000000, ge=1)
    fa_codefamille: List[str] = Field(default_factory=list)


class RapportResponse(BaseModel):
    endpoint: str
    client_schema: str
    source: str
    total_rows: int
    data: List[dict]
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# KPIs Analytiques (DSO, Taux Litige, Taux Retour, Taux Conversion)
# ---------------------------------------------------------------------------

class KpiAnalytiqueResponse(BaseModel):
    client_schema: str
    periode_from: str
    periode_to: str
    # Marge
    marge_brute: float = 0.0
    taux_marge: float = 0.0          # %
    # DSO
    dso_jours: float = 0.0           # Nombre de jours moyen de paiement
    ca_ttc_ytd: float = 0.0          # CA TTC base du DSO
    encours_ttc: float = 0.0         # Encours TTC base du DSO
    nb_jours_periode: int = 0
    # Taux de litige
    nb_factures_total: int = 0
    nb_factures_impayees: int = 0
    taux_impayes: float = 0.0         # %
    # Taux de retour
    nb_bon_livraison: int = 0
    nb_bon_retour: int = 0
    taux_retour: float = 0.0         # %
    # Nombre de factures YTD (do_type=6)
    nb_fac: int = 0
    # Taux de conversion Devis → BC
    nb_devis: int = 0
    nb_bc_issus_devis: int = 0
    taux_conversion: float = 0.0     # %
    # Top 10 clients / fournisseurs
    top_clients: List[dict] = Field(default_factory=list)
    top_fournisseurs: List[dict] = Field(default_factory=list)
    # Top Familles (CA HT, toutes familles avec CA > 0)
    top_familles: List[dict] = Field(default_factory=list)
    # Top Articles par famille {fa_codefamille: [list of articles]}
    top_articles_par_famille: dict = Field(default_factory=dict)
