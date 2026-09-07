"""
bi/stock/schemas.py — Modèles Pydantic pour les endpoints de Stock.
"""
from __future__ import annotations
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# ===========================================================================
# MODÈLE DE REPONSE COMMUNE
# ===========================================================================

class StockResponse(BaseModel):
    """Enveloppe standard de réponse pour le module Stock."""
    endpoint: str
    client_schema: str
    source: str
    total_rows: int
    columns: List[str]
    data: List[dict[str, Any]]
    metadata: Optional[dict] = None
    warnings: List[str] = Field(default_factory=list)


# ===========================================================================
# BASE COMMUNE
# ===========================================================================

class BaseStockRequest(BaseModel):
    """Socle commun à toutes les requêtes spécifiques du module Stock."""
    client_schema: str = Field(..., description="Schéma PostgreSQL du client (ex: 'client_01')")
    source_type: str = Field(
        "db_latest",
        description="Source de données : 'db_latest' (PostgreSQL courant) | 'archive' (snapshot horodaté)"
    )
    snapshot_datetime: Optional[str] = Field(
        None,
        description="Pour source_type='archive' : datetime ISO du snapshot cible (ex: '2026-01-15T08:00:00')"
    )
    ar_sommeil: Optional[int] = Field(0, description="0=Actifs, 1=En sommeil, None=Tous")
    limit: int = Field(100000000, ge=1, description="Nombre max de lignes retournées")

    @field_validator("client_schema")
    @classmethod
    def validate_client_schema(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", str(v)):
            raise ValueError("Nom de schéma invalide (risque d'injection SQL).")
        return str(v)



# ===========================================================================
# SCHÉMAS DE REQUÊTE SPÉCIFIQUES
# ===========================================================================

class CheckAvailabilityRequest(BaseStockRequest):
    """Requête pour vérifier le stock et la disponibilité d'un article."""
    ar_ref: List[str] = Field(default_factory=list, description="Références article exactes")
    search_terms: Optional[List[str]] = Field(None, description="Mots-clés de recherche dans la désignation (OR)")
    fa_codefamille: List[str] = Field(default_factory=list, description="Codes famille article")
    depot_ids: List[int] = Field(default_factory=list, description="Filtrer par dépôt(s)")
    with_financials: bool = Field(False, description="Inclure prix achat et marge")
    by_depot: bool = Field(False, description="Ventiler par dépôt")


class ArticleDetailsRequest(BaseStockRequest):
    """Requête pour obtenir la fiche technique détaillée d'un article."""
    ar_ref: List[str] = Field(default_factory=list, description="Référence(s) article")
    ar_design: Optional[str] = Field(None, description="Recherche textuelle dans la désignation")
    fa_codefamille: List[str] = Field(default_factory=list, description="Codes famille article")
    depot_ids: List[int] = Field(default_factory=list, description="Filtrer par dépôt(s)")

    @model_validator(mode="after")
    def validate_has_identifier(self):
        if not self.ar_ref and not self.ar_design:
            raise ValueError("Au moins 'ar_ref' (liste) ou 'ar_design' (texte) doit être fourni.")
        return self


class CatalogSearchRequest(BaseStockRequest):
    """Requête pour la recherche catalogue par attributs techniques."""
    ar_ref: List[str] = Field(default_factory=list, description="Références article exactes")
    fa_codefamille: List[str] = Field(default_factory=list, description="Codes famille article")
    depot_ids: List[int] = Field(default_factory=list, description="Filtrer par dépôt(s)")
    ar_nature: List[int] = Field(default_factory=list, description="0=Composant, 1=Pièce, 2=Produit fini, 3=Semi-fini")
    ar_type: List[int] = Field(default_factory=list, description="0=Standard, 1=Gamme, 2=Prestation, 3=Location")
    ar_suivistock: List[int] = Field(default_factory=list, description="0=Aucun, 1=Sérialisé, 2=CMUP, 3=FIFO, 4=LIFO, 5=Lot")
    only_available: bool = Field(False, description="Si True, retourne uniquement les articles avec qte > 0")
    sort_by: Optional[str] = Field(None, description="Tri : 'stock' | 'price' | 'name'")


class StockInsightRequest(BaseStockRequest):
    """Requête pour identifier les anomalies de stock."""
    insight_type: Literal["rupture", "stock_bas", "dormant", "sommeil", "expiration", "jamais_vendu"] = Field(..., description="Type d'anomalie à détecter")
    threshold: Optional[float] = Field(None, description="Seuil de quantité pour 'stock_bas'")
    expiry_days: Optional[int] = Field(None, description="Nombre de jours avant péremption pour 'expiration'")
    dormant_days: Optional[int] = Field(90, description="Délai d'inactivité en jours")
    fa_codefamille: List[str] = Field(default_factory=list, description="Codes famille article")
    depot_ids: List[int] = Field(default_factory=list, description="Filtrer par dépôt(s)")

    @model_validator(mode="after")
    def validate_insight_params(self):
        if self.insight_type == "stock_bas" and self.threshold is None:
            raise ValueError("Pour insight_type='stock_bas', vous devez spécifier 'threshold'.")
        if self.insight_type == "expiration" and self.expiry_days is None:
            raise ValueError("Pour insight_type='expiration', vous devez spécifier 'expiry_days'.")
        return self


class StockSnapshotRequest(BaseStockRequest):
    """Requête pour obtenir l'état du stock à une date passée."""
    ar_ref: List[str] = Field(default_factory=list, description="Références article exactes")
    fa_codefamille: List[str] = Field(default_factory=list, description="Codes famille article")
    by_depot: bool = Field(False, description="Ventiler par dépôt")

    @model_validator(mode="after")
    def validate_snapshot_source(self):
        if self.source_type != "archive":
            raise ValueError("L'endpoint snapshot nécessite source_type='archive'.")
        if not self.snapshot_datetime:
            raise ValueError("L'endpoint snapshot nécessite 'snapshot_datetime'.")
        return self


class StockCompareTimeRequest(BaseStockRequest):
    """Requête pour comparer l'évolution du stock entre deux dates."""
    date_from: str = Field(..., description="Date de début comparaison (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Date de fin (YYYY-MM-DD). Défaut = base live")
    ar_ref: List[str] = Field(default_factory=list, description="Références article exactes")
    fa_codefamille: List[str] = Field(default_factory=list, description="Codes famille article")

    @model_validator(mode="after")
    def validate_compare_source(self):
        if self.source_type != "archive":
            raise ValueError("L'endpoint compare nécessite source_type='archive'.")
        return self

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def validate_date_format(cls, v):
        if v is None:
            return v
        v = str(v).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            return v
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ][\d:]+$", v)
        if m:
            return m.group(1)
        raise ValueError(
            f"Date invalide : '{v}'. Format attendu: YYYY-MM-DD (ex: '2026-03-01')."
        )

# Aliases pour rétro-compatibilité
CheckAvailabilityInput = CheckAvailabilityRequest
GetArticleDetailsInput = ArticleDetailsRequest
CatalogSearchInput = CatalogSearchRequest
StockInsightInput = StockInsightRequest
StockSnapshotInput = StockSnapshotRequest
StockCompareTimeInput = StockCompareTimeRequest

