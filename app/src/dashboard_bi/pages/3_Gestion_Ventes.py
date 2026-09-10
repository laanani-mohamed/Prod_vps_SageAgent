"""
Dash/pages/3_Gestion_Ventes.py
Page 3 — Gestion des Ventes
"""
import streamlit as st
from components.styles_initiale import apply_custom_css
from components.auth_guard import require_auth, require_api_health
from components.gestion_documents import render_gestion_documents_page

apply_custom_css()
require_auth()

st.header("Gestion des Ventes")

require_api_health()

with st.sidebar:
    client_schema = st.session_state.get("client_schema", "")

render_gestion_documents_page(
    domaine=0,
    key_ns="ventes",
    code_label="Recherche Code Client",
    intitule_label="Recherche Intitulé Client",
    tiers_logical="client",
    tiers_col="CLIENT INTITULE",
    detail_title="Détails de la Pièce",
    detail_label="Client",
    tab_labels=[
        "Général", "Devis", "Bon de commande", "Préparation de livraison",
        "Bon de livraison", "Bon de retour", "Bon d'avoir",
        "Facture", "Facture comptabilisée", "Archive",
    ],
    tab_configs=[
        "general", "devis", "bon_commande", "prep_livraison",
        "bon_livraison", "bon_retour", "bon_avoir",
        "facture", "facture_comptab", "archive",
    ],
    client_schema=client_schema,
)
