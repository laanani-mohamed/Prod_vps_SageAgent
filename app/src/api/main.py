"""
api/main.py — Point d'entrée de l'API BI FastAPI.
Lancement :
./venv/bin/uvicorn api.main:app --app-dir src --reload --host 0.0.0.0 --port 8000

Docs Swagger disponibles sur :
  http://localhost:8000/docs

"""
import sys
import os
import logging

# Ajout dynamique de la racine du projet et du dossier src au PYTHONPATH
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(SRC_ROOT)

for path in [SRC_ROOT, PROJECT_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.stock.router import router as stock_router
from api.transactions.router import router as transactions_router
from api.referentiel.router import router as referentiel_router
from api.bi.router import router as bi_router
from api.auth.router import router as auth_router
from api.auth.config import auth_settings
from api.auth.dependencies import get_current_user
from api.auth.schemas import TokenData

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from api.auth.audit import start_audit_worker, stop_audit_worker
from api.rate_limiter import limiter
from api.db import init_db_pool, close_db_pool



# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("api.api")

# ---------------------------------------------------------------------------
# Application FastAPI
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_pool()
    start_audit_worker()
    yield
    stop_audit_worker()
    close_db_pool()

app = FastAPI(
    title="BI API — Sage ERP",
    description=(
        "API BI conversationnelle connectée aux données Sage ERP.\n\n"
        "Le LLM produit un JSON structuré. L'orchestrateur appelle "
        "l'endpoint correspondant pour retourner les données."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=auth_settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Enregistrement des routeurs (Dashboard)
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(stock_router)
app.include_router(transactions_router)
app.include_router(referentiel_router)
app.include_router(bi_router)

# ---------------------------------------------------------------------------
# Enregistrement de la sous-application Telegram (Sans Sécurité JWT)
# ---------------------------------------------------------------------------
telegram_app = FastAPI(title="BI API — Telegram Agent")

# On simule un utilisateur "telegram_agent" avec tous les droits
async def get_telegram_user(request: Request) -> TokenData:
    # Optionnel: on pourrait vérifier un secret_token dans les headers ici pour sécuriser l'agent
    return TokenData(username="telegram_agent", role="admin", allowed_schemas=["ALL"])

telegram_app.dependency_overrides[get_current_user] = get_telegram_user

# On attache le rate limiter à la sous-application pour éviter les erreurs AttributeError
telegram_app.state.limiter = limiter
telegram_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# On inclut exactement les mêmes routeurs dans l'app Telegram
telegram_app.include_router(stock_router)
telegram_app.include_router(transactions_router)
telegram_app.include_router(referentiel_router)
telegram_app.include_router(bi_router)

app.mount("/telegram", telegram_app)


@app.get("/", tags=["Racine"])
def root():
    return {
        "api": "BI Sage ERP",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": [
            "--- Auth ---",
            "POST /api/auth/token",
            "POST /api/auth/refresh",
            "POST /api/auth/logout",
            "--- Stock ---",
            "POST /api/stock/availability",
            "POST /api/stock/details",
            "POST /api/stock/catalog",
            "POST /api/stock/insights",
            "POST /api/stock/snapshot",
            "POST /api/stock/compare",
            "--- Transactions ---",
            "POST /api/transactions/ventes",
            "POST /api/transactions/achats",
            "POST /api/transactions/documents",
            "--- Analytics (CA / Marge / Devis) ---",
            "POST /api/analytics/ca       → ca_global | ca_by_client | ca_by_article | ca_by_vendeur | ca_evolution",
            "POST /api/analytics/marge    → marge_globale | marge_by_article | marge_by_client | marge_by_vendeur",
            "POST /api/analytics/devis    → taux_transformation | devis_en_cours",
            "--- Recouvrement ---",
            "POST /api/recouvrement/encours     → encours_client | encours_global",
            "POST /api/recouvrement/reglements  → reglements_recus | taux_recouvrement",
            "POST /api/recouvrement/factures    → factures_impayees | factures_partielles",
            "--- Performance ---",
            "POST /api/performance/vendeurs  → ranking_vendeurs | perf_vendeur_detail",
            "POST /api/performance/clients   → top_clients | client_recurrence | clients_inactifs",
            "POST /api/performance/articles  → top_articles | articles_jamais_vendus",
            "POST /api/performance/achats    → perf_fournisseurs | comparaison_achat_vente",
            "--- Référentiel ---",
            "POST /api/referentiel/comptes-tiers     → ComptesTiersRequest (10 filtres, 20 colonnes)",
            "POST /api/referentiel/collaborateurs    → CollaborateurRequest (vendeur, acheteur, matricule ILIKE)",
            "POST /api/referentiel/articles/detail   → ArticleDetailRequest (with_stock, with_lots)",
            "POST /api/referentiel/familles           → FamilleRequest (with_articles_count)",
            "POST /api/referentiel/lots-series        → LotSerieRequest (péremption, only_active)",
            "POST /api/referentiel/documents-entete   → DocEnteteRequest (reste_a_payer calculé)",
            "POST /api/referentiel/documents-ligne    → DocLigneRequest (with_entete, RAM-safe)",
            "POST /api/referentiel/stock-depot        → StockDepotRequest (valeur_stock calculée)",
            "GET  /api/referentiel/types-tiers        → Dictionnaire CT_Type",
            "GET  /api/referentiel/types-documents    → Dictionnaire DO_Type",
            "--- BI Dashboard & Rapports ---",
            "POST /api/bi/dashboard                   → KPIs globaux",
            "GET  /api/bi/dashboard/objectifs         → Axes stratégiques",
            "GET  /api/bi/dashboard/analytique        → KPIs analytiques (Marge, DSO, Retour)",
            "POST /api/bi/rapport/ca                  → Rapport CA",
            "POST /api/bi/rapport/balance             → Balance Client",
            "POST /api/bi/top-clients                 → Top Clients",
            "POST /api/bi/top-articles                → Top Articles",
            "--- IA (LangGraph StateGraph) ---",
            "POST /ai/ask         → Point d'entrée principal BI (LangGraph)",
            "POST /ai/ask/stream  → Streaming SSE (events en temps réel)",
            "POST /ai/ask/resume  → Reprise HITL (approve/reject)",
        ]
    }

@app.get("/health", tags=["Racine"])
def health():
    return {"status": "ok"}




