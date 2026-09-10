"""
Dash/pages/4_Gestion_Achats.py
Page 4 — Gestion des Achats
"""
import streamlit as st
from components.styles_initiale import apply_custom_css
from components.auth_guard import require_auth, require_api_health
from components.gestion_documents import render_gestion_documents_page

apply_custom_css()
require_auth()

st.header("Gestion des Achats")

require_api_health()

with st.sidebar:
    client_schema = st.session_state.get("client_schema", "")

render_gestion_documents_page(
    domaine=1,
    key_ns="achats",
    code_label="Recherche Code Fournisseur",
    intitule_label="Recherche Intitulé Fourn.",
    tiers_logical="fournisseur",
    tiers_col="FOURNISSEUR INTITULE",
    detail_title="🔍 Détails de la Pièce",
    detail_label="Fournisseur",
    tab_labels=[
        "Général", "Demande d'achat", "Préparation de commande", "Bon de commande",
        "Bon de livraison", "Bon de retour", "Bon d'avoir",
        "Facture", "Facture comptabilisée", "Archive",
    ],
    tab_configs=[
        "general", "demande_achat", "prep_commande", "bon_commande",
        "bon_livraison", "bon_retour", "bon_avoir",
        "facture", "facture_comptab", "archive",
    ],
    client_schema=client_schema,
)
