import streamlit as st

# Streamlit impose `* { scrollbar-width: thin; scrollbar-color: transparent }` : barres quasi invisibles.
# .dvn-scroller est le conteneur scrollable réel de st.dataframe (glide-data-grid).
TABLE_SCROLLBAR_CSS = """
    <style>
    div[data-testid="stDataFrame"] .dvn-scroller {
        scrollbar-width: auto;
        scrollbar-color: #94a3b8 #f1f5f9;
    }
    /* Safari (pas de support scrollbar-color) */
    div[data-testid="stDataFrame"] .dvn-scroller::-webkit-scrollbar { width: 14px; height: 14px; }
    div[data-testid="stDataFrame"] .dvn-scroller::-webkit-scrollbar-track { background: #f1f5f9; }
    div[data-testid="stDataFrame"] .dvn-scroller::-webkit-scrollbar-thumb {
        background: #94a3b8; border-radius: 8px; border: 3px solid #f1f5f9;
    }
    </style>
"""


def apply_table_scrollbar_css():
    st.markdown(TABLE_SCROLLBAR_CSS, unsafe_allow_html=True)


def apply_custom_css():
    """Applique le style vibrant pour le sidebar et les KPIs (inspiré du design UI fourni)."""
    st.markdown("""
        <style>
        /* 2. KPI Cards Colors using Native Streamlit keys */
        
        /* KPI 1: #577399 */
        div.st-key-kpi1 {
            background: linear-gradient(135deg, #577399, #bdd5ea) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(72, 86, 150, 0.2) !important;
        }
        /* KPI 2: #bdd5ea */
        div.st-key-kpi2 {
            background: linear-gradient(135deg, #bdd5ea 30%, #fe5f55) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(231, 231, 231, 0.4) !important;
        }
        /* KPI 3: #577399 */
        div.st-key-kpi3 {
            background: linear-gradient(135deg, #577399, #bdd5ea) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(249, 199, 132, 0.2) !important;
        }
        /* KPI 4: #bdd5ea */
        div.st-key-kpi4 {
            background: linear-gradient(135deg, #bdd5ea, #bdd5ea) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(252, 122, 30, 0.2) !important;
        }
        /* KPI 5: #577399 */
        div.st-key-kpi5 {
            background: linear-gradient(135deg, #577399, #bdd5ea) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(242, 76, 0, 0.2) !important;
        }
        /* KPI 6: #bdd5ea */
        div.st-key-kpi6 {
            background: linear-gradient(135deg, #bdd5ea 30%, #fe5f55) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(242, 76, 0, 0.2) !important;
        }
        /* KPI 7: #bdd5ea */
        div.st-key-kpi7 {
            background: linear-gradient(135deg, #bdd5ea, #fe5f55) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(242, 76, 0, 0.2) !important;
        }
        
        /* Force text inside the metrics to be white by default */
        div.st-key-kpi1 [data-testid="stMetric"] *,
        div.st-key-kpi2 [data-testid="stMetric"] *,
        div.st-key-kpi4 [data-testid="stMetric"] *,
        div.st-key-kpi5 [data-testid="stMetric"] *,
        div.st-key-kpi6 [data-testid="stMetric"] *{
            color: white !important;
        }
        
        /* Exception: For KPI 2 (Light Grey) and KPI 3 (Light Orange), dark text is more readable */
        div.st-key-kpi3 [data-testid="stMetric"],
        div.st-key-kpi4 [data-testid="stMetric"] *,
        div.st-key-kpi7 [data-testid="stMetric"] * {
            color: #333333 !important;
        }
        
        /* --- Analytique Cards (kc1 to kc4) --- */
        div.st-key-kc1 {
            background: linear-gradient(135deg, #577399, #bdd5ea) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(131, 56, 236, 0.2) !important;
        }
        div.st-key-kc2 {
            background: linear-gradient(135deg, #bdd5ea, #bdd5ea) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(0, 95, 115, 0.2) !important;
        }
        div.st-key-kc3 {
            background: linear-gradient(135deg, #bdd5ea 30%, #fe5f55) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(226, 149, 120, 0.2) !important;
        }
        div.st-key-kc4 {
            background: linear-gradient(135deg, #fe5f55, #fe5f55) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(251, 86, 7, 0.2) !important;
        }
        
        div.st-key-kc1 [data-testid="stMetric"] *,
        div.st-key-kc2 [data-testid="stMetric"] *,
        div.st-key-kc3 [data-testid="stMetric"] *,
        div.st-key-kc4 [data-testid="stMetric"] * {
            color: white !important;
        }
        
        /* Ensure st.caption and markdown text inside these are readable */
        div.st-key-kc1 [data-testid="stMarkdownContainer"] p,
        div.st-key-kc2 [data-testid="stMarkdownContainer"] p,
        div.st-key-kc3 [data-testid="stMarkdownContainer"] p,
        div.st-key-kc4 [data-testid="stMarkdownContainer"] p {
            color: rgba(255, 255, 255, 0.9) !important;
        }

        /* Style the progress bar line (from km1) so it stands out */
        div.st-key-kpi1 [data-testid="stProgress"] > div {
            background-color: rgba(255, 255, 255, 0.3) !important;
        }
        div.st-key-kpi1 [data-testid="stProgress"] > div > div {
            background-color: white !important;
        }

        </style>
    """, unsafe_allow_html=True)
    apply_table_scrollbar_css()
