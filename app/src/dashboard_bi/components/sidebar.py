"""
Dash/components/sidebar.py
"""
import streamlit as st
from components.styles_sidebar import apply_sidebar_css

def render_sidebar():
    """Rendu de la sidebar globale."""
    apply_sidebar_css()
    with st.sidebar:
        st.title("ITBORD")
        st.divider()
