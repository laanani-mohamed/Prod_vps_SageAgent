import streamlit as st

def apply_sidebar_css():
    """Applique le style de la sidebar séparément."""
    st.markdown("""
        <style>
        /* 1. Sidebar Vibrant Color */
        [data-testid="stSidebar"] {
            background: linear-gradient(135deg, #577399 50%, #bdd5ea) !important;
            border-radius: 20px !important;
        }
        
        /* Make all text in the sidebar white */
        [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] li,
        [data-testid="stSidebar"] a {
            color: white !important;
        }
        
        /* Style text inputs / selectbox in sidebar to remain readable */
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] div[data-baseweb="select"] > div {
            color: white !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
            border: 1px solid rgba(255, 255, 255, 0.3) !important;
        }
        </style>
    """, unsafe_allow_html=True)
