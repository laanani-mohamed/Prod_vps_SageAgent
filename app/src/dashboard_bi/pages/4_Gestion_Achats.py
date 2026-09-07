"""
Dash/pages/4_Gestion_Achats.py
Page 4 — Gestion des Achats
"""
import os
import streamlit as st
import pandas as pd
from components.styles_initiale import apply_custom_css
from components.data_tables import show_df
from components.auth_guard import require_auth, handle_auth_error

apply_custom_css()
require_auth()

from services.documents_service import get_documents_ligne, get_formatted_documents
from services.base import check_api_health

st.header("Gestion des Achats")

if not check_api_health():
    st.error("API injoignable.")
    st.stop()

# ---------------------------------------------------------------------------
# Filtres globaux dans la barre latérale
# ---------------------------------------------------------------------------
with st.sidebar:
    client_schema = st.session_state.get("client_schema", "")

with st.expander("🔍 Filtres de recherche", expanded=True):
    @st.cache_data(ttl=300, show_spinner=False)
    def fetch_filter_options(schema):
        if not schema:
            return ["Tout"], ["Tout"], ["Tout"]
        try:
            from services.documents_service import get_documents_entete
            import pandas as pd
            docs = get_documents_entete(schema, domaine=[1])
            if not docs:
                return ["Tout"], ["Tout"], ["Tout"]
            df = pd.DataFrame(docs)
            pieces = ["Tout"] + sorted([str(x) for x in df["do_piece"].dropna().unique() if str(x).strip()]) if "do_piece" in df.columns else ["Tout"]
            tiers = ["Tout"] + sorted([str(x) for x in df["do_tiers"].dropna().unique() if str(x).strip()]) if "do_tiers" in df.columns else ["Tout"]
            intitules = ["Tout"] + sorted([str(x) for x in df["ct_intitule"].dropna().unique() if str(x).strip()]) if "ct_intitule" in df.columns else ["Tout"]
            return pieces, tiers, intitules
        except:
            return ["Tout"], ["Tout"], ["Tout"]

    pieces_opts, tiers_opts, intitule_opts = fetch_filter_options(client_schema)

    col1, col2, col3 = st.columns(3)
    with col1:
        search_piece = st.selectbox("Recherche N° Pièce", options=pieces_opts, help="Numéro exact du document", key="piece_achats")
    with col2:
        search_tiers = st.selectbox("Recherche Code Fournisseur", options=tiers_opts, help="Filtre sur le code fournisseur", key="tiers_achats")
    with col3:
        search_intitule = st.selectbox("Recherche Intitulé Fourn.", options=intitule_opts, help="Filtre sur le nom du fournisseur", key="intitule_achats")

    col4, col5, col6 = st.columns([1, 1, 2])
    with col4:
        date_from = st.date_input("Date début", value=None, key="df_achats")
    with col5:
        date_to = st.date_input("Date fin", value=None, key="dt_achats")
    with col6:
        st.write("") # Espacement pour aligner verticalement
        st.write("")
        unpaid_only = st.checkbox("Non réglés uniquement (Reste > 0)", key="unpaid_achats")
        
    st.button(
        "▶ Appliquer les filtres",
        type="primary",
        use_container_width=True,
        key="btn_achats",
        disabled=st.session_state.get("loading_achats", False)
    )

# ---------------------------------------------------------------------------
# Définition des Onglets par type de document d'achat (domaine = 1)
# ---------------------------------------------------------------------------
tab_general, tab_da, tab_prep, tab_bc, tab_bl, tab_retour, tab_avoir, tab_fact, tab_fact_c, tab_arch = st.tabs([
    "Général",
    "Demande d'achat", 
    "Préparation de commande", 
    "Bon de commande",
    "Bon de livraison", 
    "Bon de retour", 
    "Bon d'avoir",
    "Facture",
    "Facture comptabilisée",
    "Archive"
])

tab_configs = [
    (tab_general, [10, 11, 12, 13, 14, 15, 16, 17, 18], "general"),
    (tab_da, [10], "demande_achat"),
    (tab_prep, [11], "prep_commande"),
    (tab_bc, [12], "bon_commande"),
    (tab_bl, [13], "bon_livraison"),
    (tab_retour, [14], "bon_retour"),
    (tab_avoir, [15], "bon_avoir"),
    (tab_fact, [16], "facture"),
    (tab_fact_c, [17], "facture_comptab"),
    (tab_arch, [18], "archive"),
]

for tab, do_types, key_prefix in tab_configs:
    with tab:
        try:
            with st.spinner("Chargement des documents..."):
                st.session_state["loading_achats"] = True
                df_docs = get_formatted_documents(
                    client_schema=client_schema,
                    domaine=1, # 1 = Achats
                    category=key_prefix,
                    search_piece="" if search_piece == "Tout" else search_piece,
                    search_tiers="" if search_tiers == "Tout" else search_tiers,
                    search_intitule="" if search_intitule == "Tout" else search_intitule,
                    date_from=date_from.strftime("%Y-%m-%d") if date_from else None,
                    date_to=date_to.strftime("%Y-%m-%d") if date_to else None,
                    unpaid_only=unpaid_only
                )
        except Exception as e:
            handle_auth_error(e)
            df_docs = pd.DataFrame()
        finally:
            st.session_state["loading_achats"] = False
            
        if not df_docs.empty:
            st.markdown("*Cliquez sur une ligne pour afficher les détails du document.*")
            
            selection = show_df(
                df_docs,
                on_select="rerun",
                selection_mode="single-row",
                key_suffix=f"sel_ach_{key_prefix}"
            )
            
            sel_rows = selection.get("selection", {}).get("rows", [])
            if sel_rows:
                idx = sel_rows[0]
                piece_no = df_docs.iloc[idx]["N PIECE"]
                fourn_name = df_docs.iloc[idx]["FOURNISSEUR INTITULE"]
                
                st.divider()
                st.subheader(f"🔍 Détails de la Pièce : {piece_no}")
                st.markdown(f"**Fournisseur :** {fourn_name}")
                
                with st.spinner("Chargement des lignes du document..."):
                    lignes = get_documents_ligne(client_schema, piece_no)
                    
                if lignes:
                    df_l = pd.DataFrame(lignes)
                    cols_l = {
                        "ar_ref": "Réf. Article",
                        "dl_design": "Désignation",
                        "dl_qte": "Qté",
                        "dl_prixru": "PU HT",
                        "dl_montantht": "Montant HT",
                        "dl_montantttc": "Montant TTC"
                    }
                    df_l_show = df_l[[c for c in cols_l.keys() if c in df_l.columns]].rename(columns=cols_l)
                    show_df(df_l_show, key_suffix=f"lignes_ach_{key_prefix}")
                else:
                    st.warning("Aucune ligne trouvée pour ce document.")
        else:
            st.info("Aucun document trouvé.")
