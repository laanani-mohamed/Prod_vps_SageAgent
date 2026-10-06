import streamlit as st

from components.styles_initiale import apply_table_scrollbar_css

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
            # color: black !important
        }

        /* --- Cartes des statistiques client / fournisseur : copie des cartes « Indicateurs
           Analytiques » kc1 → kc4 du Tableau de Bord (styles_initiale.py), dans le même ordre.
           Clés "tstat-kcN-..." (uniques par carte), ciblées par préfixe de classe. --- */
        div[class*="st-key-tstat-kc1-"], div[class*="st-key-tstat-kc2-"],
        div[class*="st-key-tstat-kc3-"], div[class*="st-key-tstat-kc4-"] {
            border: none !important;
            border-radius: 20px !important;
        }
        div[class*="st-key-tstat-kc1-"] {
            background: linear-gradient(135deg, #577399, #bdd5ea) !important;
            box-shadow: 0 4px 20px rgba(131, 56, 236, 0.2) !important;
        }
        div[class*="st-key-tstat-kc2-"] {
            background: linear-gradient(135deg, #bdd5ea, #bdd5ea) !important;
            box-shadow: 0 4px 20px rgba(0, 95, 115, 0.2) !important;
        }
        div[class*="st-key-tstat-kc3-"] {
            background: linear-gradient(135deg, #bdd5ea 30%, #fe5f55) !important;
            box-shadow: 0 4px 20px rgba(226, 149, 120, 0.2) !important;
        }
        div[class*="st-key-tstat-kc4-"] {
            background: linear-gradient(135deg, #fe5f55, #fe5f55) !important;
            box-shadow: 0 4px 20px rgba(251, 86, 7, 0.2) !important;
        }
        div[class*="st-key-tstat-kc1-"] [data-testid="stMetric"] *,
        div[class*="st-key-tstat-kc2-"] [data-testid="stMetric"] *,
        div[class*="st-key-tstat-kc3-"] [data-testid="stMetric"] *,
        div[class*="st-key-tstat-kc4-"] [data-testid="stMetric"] * {
            color: white !important;
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
