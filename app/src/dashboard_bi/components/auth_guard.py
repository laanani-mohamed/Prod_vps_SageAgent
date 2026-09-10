import streamlit as st
from core.exceptions import AuthError
from services.base import check_api_health


def require_api_health():
    """
    Vérifie que l'API backend est joignable.
    Si non, affiche un message et arrête l'exécution de la page via st.stop().
    """
    if not check_api_health():
        st.error("API injoignable.")
        st.stop()


def require_auth():
    """
    Vérifie que l'utilisateur est authentifié.
    Si non, affiche un message et arrête l'exécution de la page via st.stop().
    """
    if "access_token" not in st.session_state:
        st.warning("🔒 Vous devez vous connecter pour accéder à cette page.")
        st.info("Retournez à la page principale pour vous authentifier.")
        st.stop()
    
    # Vérification que le schéma est bien défini
    if not st.session_state.get("client_schema"):
        st.error("❌ Aucun schéma client associé à votre compte. Contactez un administrateur.")
        st.stop()


def handle_auth_error(e: Exception):
    """
    À appeler dans les blocs except des pages Streamlit.
    Si l'exception est une AuthError (session expirée), déconnecte proprement
    l'utilisateur et le redirige vers la page de login.
    Sinon, re-lève l'exception pour qu'elle soit gérée par Streamlit.
    """
    if isinstance(e, AuthError):
        st.error("🔒 Votre session a expiré. Vous allez être redirigé vers la connexion.")
        st.session_state.clear()
        st.rerun()
    else:
        raise e
