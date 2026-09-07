"""
Dash/app.py
Point d'entrée principal de l'application Streamlit SAGEIA ERP.
Lance avec : streamlit run Dash/app.py
"""

import sys
import os
import streamlit as st
import httpx

# Injecter Dash/ dans sys.path pour les imports absolus (core, services, components)
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
if DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, DASHBOARD_DIR)

# ---------------------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SAGE-BI ERP",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Styles CSS Personnalisés
# ---------------------------------------------------------------------------
from components.styles_initiale import apply_custom_css
apply_custom_css()

# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------
if "access_token" not in st.session_state:
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>🔒 Connexion SAGE-BI ERP</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.container(border=True):
            with st.form("login_form"):
                st.markdown("### Identifiants")
                username = st.text_input("Nom d'utilisateur", placeholder="ex: admin")
                password = st.text_input("Mot de passe", type="password", placeholder="Votre mot de passe")
                submit = st.form_submit_button("Se Connecter", use_container_width=True)
                
                if submit:
                    if not username or not password:
                        st.warning("Veuillez saisir vos identifiants.")
                    else:
                        import httpx
                        from config import API_BASE_URL
                        try:
                            # OAuth2PasswordRequestForm expects 'application/x-www-form-urlencoded' data
                            resp = httpx.post(
                                f"{API_BASE_URL}/api/auth/token",
                                data={"username": username, "password": password},
                                timeout=10.0
                            )
                            if resp.status_code == 200:
                                token = resp.json()["access_token"]
                                st.session_state.access_token  = token
                                st.session_state.refresh_token = resp.json().get("refresh_token", "")
                                
                                # Décodage du payload JWT (partie du milieu)
                                import base64
                                import json
                                try:
                                    payload_part = token.split(".")[1]
                                    # Ajout du padding base64 manquant si nécessaire
                                    payload_part += "=" * ((4 - len(payload_part) % 4) % 4)
                                    decoded_payload = base64.urlsafe_b64decode(payload_part).decode("utf-8")
                                    payload = json.loads(decoded_payload)
                                    
                                    schemas = payload.get("schemas", [])
                                    if schemas:
                                        # Assigner le premier schéma de la liste
                                        st.session_state.client_schema = schemas[0]
                                    else:
                                        st.warning("Aucun schéma client assigné à cet utilisateur.")
                                except Exception as e:
                                    st.error(f"Erreur lors de la lecture du token: {e}")
                                
                                st.rerun()
                            elif resp.status_code == 401:
                                st.error("Identifiants incorrects.")
                            else:
                                st.error(f"Erreur API ({resp.status_code}): {resp.text}")
                        except Exception as e:
                            st.error(f"Impossible de joindre le serveur API: {e}")
else:
    # ---------------------------------------------------------------------------
    # Sidebar
    # ---------------------------------------------------------------------------
    from components.sidebar import render_sidebar
    render_sidebar()
    
    # Bouton de déconnexion en bas de la sidebar
    with st.sidebar:
        if st.button("Se déconnecter", type="primary"):
            # Révoquer le token côté serveur (invalidation Redis)
            token   = st.session_state.get("access_token", "")
            refresh = st.session_state.get("refresh_token", "")
            if token and refresh:
                try:
                    from config import API_BASE_URL
                    httpx.post(
                        f"{API_BASE_URL}/api/auth/logout",
                        json={"refresh_token": refresh},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=3.0
                    )
                except Exception:
                    pass  # On déconnecte quand même côté client
            st.session_state.clear()
            st.rerun()

    # ---------------------------------------------------------------------------
    # Définition des pages
    # ---------------------------------------------------------------------------
    pages = {
        "Global": [
            st.Page("pages/1_Tableau_de_Bord.py", title="Tableau de Bord"),
        ],
        "Fichier de Base": [
            st.Page("pages/2_Fichier_de_Base.py", title="Fichier de Base"),
        ],
        "Transactions": [
            st.Page("pages/3_Gestion_Ventes.py",  title="Gestion Ventes"),
            st.Page("pages/4_Gestion_Achats.py",  title="Gestion Achats"),
        ],
        "Stock": [
            st.Page("pages/5_Mouvements_Stock.py", title="Stock & Mouvements"),
        ],
        "Finance": [
            st.Page("pages/6_Reglements.py", title="Règlements"),
            st.Page("pages/7_Rapports.py",   title="Rapports BI"),
        ],
        "Agent BI": [
            st.Page("pages/8_Agent_BI.py", title="Agent Conversationnel"),
        ],
    }

    pg = st.navigation(pages)
    pg.run()
