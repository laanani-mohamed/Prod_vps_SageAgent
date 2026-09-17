"""
Dash/components/sidebar.py
"""
import streamlit as st
from components.styles_sidebar import apply_sidebar_css
from services.bi_service import get_last_update
from core.formatters import format_datetime_minute

def render_sidebar():
    """Rendu de la sidebar globale."""
    apply_sidebar_css()
    with st.sidebar:
        client_schema = st.session_state.get("client_schema", "")
        st.title(f"ITBORD-{client_schema}" if client_schema else "ITBORD")

        if client_schema:
            try:
                last_update = get_last_update(client_schema)
                st.caption(f"Dernière mise à jour : {format_datetime_minute(last_update)}")
            except Exception:
                pass

        st.divider()
