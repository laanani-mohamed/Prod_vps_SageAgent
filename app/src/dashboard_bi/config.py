"""
Dash/config.py
Configuration globale de l'application Streamlit SAGEIA ERP.
- Couleurs par module (identique au HTML original)
- Constantes métier (types de documents)
- URL API
"""

import os

# ---------------------------------------------------------------------------
# URL de base de l'API FastAPI
# ---------------------------------------------------------------------------
API_BASE_URL: str = os.environ.get("API_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Mode source forcé pour toute la V1 : archive uniquement
# ---------------------------------------------------------------------------
SOURCE_TYPE: str = "db_latest"

# ---------------------------------------------------------------------------
# Couleurs thème (identique au HTML Tailwind)
# ---------------------------------------------------------------------------
COLORS: dict = {
    "dashboard": "#14b8a6",   # teal
    "base":      "#f59e0b",   # amber
    "ventes":    "#10b981",   # emerald
    "achats":    "#0ea5e9",   # sky
    "stock":     "#f97316",   # orange
    "reglement": "#8b5cf6",   # violet
    "rapports":  "#ef4444",   # red
    "agent":     "#6366f1",   # indigo
    "sidebar":   "#0f172a",   # slate-950
}

# ---------------------------------------------------------------------------
# Types de documents de vente (DO_Domaine = 0)
# ---------------------------------------------------------------------------
DOC_TYPES_VENTE: dict = {
    0: "Devis",
    1: "Bon de commande",
    2: "Préparation livraison",
    3: "Bon de livraison",
    4: "Bon de retour",
    5: "Bon d'avoir",
    6: "Facture",
    7: "Facture comptabilisée",
}

# ---------------------------------------------------------------------------
# Types de documents d'achat (DO_Domaine = 1)
# ---------------------------------------------------------------------------
DOC_TYPES_ACHAT: dict = {
    10: "Demande d'achat",
    11: "Préparation de commande",
    12: "Bon de commande",
    13: "Bon de livraison",
    14: "Bon de retour",
    15: "Bon d'avoir",
    16: "Facture",
    17: "Facture comptabilisée",
}

# ---------------------------------------------------------------------------
# Types de documents de stock (DO_Domaine = 2)
# ---------------------------------------------------------------------------
DOC_TYPES_STOCK: dict = {
    20: "Mouvement d'entrée",
    21: "Mouvement de sortie",
    22: "Mouvement de dépôt à dépôt",
    23: "Transfert",
}

# ---------------------------------------------------------------------------
# Types de tiers (CT_Type dans F_COMPTET)
# ---------------------------------------------------------------------------
TYPES_TIERS: dict = {
    0: "Client",
    1: "Fournisseur",
    2: "Salarié",
    3: "Autre",
}

# ---------------------------------------------------------------------------
# Limites de pagination par défaut
# ---------------------------------------------------------------------------
DEFAULT_PAGE_LIMIT: int = 500
