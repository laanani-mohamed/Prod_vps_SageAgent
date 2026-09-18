"""
auth.py — Gate d'accès simple par mot de passe partagé (pas de multi-utilisateur,
pas de JWT : outil de debug interne, protection minimale mais suffisante).
"""
import streamlit as st

from ops_config import OPS_DASHBOARD_PASSWORD


def is_authenticated() -> bool:
    return st.session_state.get("ops_authenticated", False)


def render_login_gate() -> None:
    st.markdown("## 🔒 SageAgent — Observabilité ETL")

    if not OPS_DASHBOARD_PASSWORD:
        st.error(
            "OPS_DASHBOARD_PASSWORD n'est pas défini dans /opt/SageAgent/app/.env — "
            "ajoutez cette variable avant de pouvoir accéder à cette page."
        )
        st.stop()

    with st.form("ops_login_form"):
        password = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter", type="primary")

    if submit:
        if password == OPS_DASHBOARD_PASSWORD:
            st.session_state.ops_authenticated = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")

    st.stop()


def require_auth() -> None:
    if not is_authenticated():
        render_login_gate()


def logout_button() -> None:
    with st.sidebar:
        if st.button("Se déconnecter"):
            st.session_state.clear()
            st.rerun()
