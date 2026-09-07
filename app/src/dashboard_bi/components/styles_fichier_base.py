import streamlit as st

def apply_fichier_base_css():
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
            background: linear-gradient(135deg, #bdd5ea, #577399) !important;
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
            background: linear-gradient(135deg, #bdd5ea, #577399) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(252, 122, 30, 0.2) !important;
        }
        /* KPI 5: #577399 */
        div.st-key-kc1 {
            background: linear-gradient(135deg, #577399, #bdd5ea) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(242, 76, 0, 0.2) !important;
        }
        /* KPI 6: #bdd5ea */
        div.st-key-kc2 {
            background: linear-gradient(135deg, #bdd5ea, #577399) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(242, 76, 0, 0.2) !important;
        }
        /* KPI 7: #577399 */
        div.st-key-kc3 {
            background: linear-gradient(135deg, #577399, #bdd5ea) !important;
            border: none !important;
            border-radius: 20px !important;
            box-shadow: 0 4px 20px rgba(242, 76, 0, 0.2) !important;
        }
        
        /* Rendre l'écriture noire pour tous les KPIs */
        div.st-key-kpi3 [data-testid="stMetric"] *,
        div.st-key-kpi4 [data-testid="stMetric"] *,
        div.st-key-kc3 [data-testid="stMetric"] * {
            color: white !important;
        }
        
        /* Rendre l'écriture noire pour tous les KPIs */
        div.st-key-kpi1 [data-testid="stMetric"] *,
        div.st-key-kpi2 [data-testid="stMetric"] *,
        div.st-key-kc1 [data-testid="stMetric"] *{
            color: black !important;
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
