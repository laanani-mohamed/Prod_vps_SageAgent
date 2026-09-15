"""
Dash/components/sidebar.py
"""
import streamlit as st
from components.styles_sidebar import apply_sidebar_css

def render_sidebar():
    """Rendu de la sidebar globale."""
    apply_sidebar_css()
    with st.sidebar:
        client_schema = st.session_state.get("client_schema", "")
        st.title(f"ITBORD-{client_schema}" if client_schema else "ITBORD")
        st.divider()
