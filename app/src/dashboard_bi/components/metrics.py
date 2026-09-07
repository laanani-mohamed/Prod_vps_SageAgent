"""
Dash/components/metrics.py
Composant : 4 cartes KPI du tableau de bord — 100% natif Streamlit.
"""
import streamlit as st

def render_kpi_cards(
    ca: float,
    achats: float,
    valeur_stock: float,
    encours_clients: float,
    nb_clients: int = 0,
) -> None:
    """Affiche les KPI sous forme de composants st.metric natifs de Streamlit."""
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        with st.container(border=True):
            st.metric(
                label="Chiffre d'Affaires",
                value=f"{ca:,.0f} DH",
                help="Somme des montants HT des factures de vente sur la période."
            )

    with col2:
        with st.container(border=True):
            st.metric(
                label="Total Achats",
                value=f"{achats:,.0f} DH",
                help="Somme des montants HT des factures d'achat sur la période."
            )

    with col3:
        with st.container(border=True):
            st.metric(
                label="Valeur Stock",
                value=f"{valeur_stock:,.0f} DH",
                help="Valorisation du stock au prix d'achat (Qté × Prix achat)."
            )

    with col4:
        with st.container(border=True):
            st.metric(
                label="Encours Clients",
                value=f"{encours_clients:,.0f} DH",
                help="Total des factures non entièrement réglées (TTC − Montant réglé)."
            )

    with col5:
        with st.container(border=True):
            st.metric(
                label="Clients Actifs",
                value=f"{nb_clients}",
        )
