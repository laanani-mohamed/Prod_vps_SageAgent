"""
Dash/pages/6_Reglements.py
Page 6 — Règlements (Encaissements Clients & Décaissements Fournisseurs)
"""
import os
import datetime
import streamlit as st
import pandas as pd
from components.styles_initiale import apply_custom_css
from components.data_tables import show_df
from components.auth_guard import require_auth, handle_auth_error, require_api_health

apply_custom_css()
require_auth()

from services.documents_service import get_documents_ligne
from services.reglements_service import get_formatted_reglements

st.header("Règlements & Flux Financiers")

require_api_health()

# ---------------------------------------------------------------------------
# Filtres globaux dans la barre latérale
# ---------------------------------------------------------------------------
with st.sidebar:
    client_schema = st.session_state.get("client_schema", "")
    
with st.expander("🔍 Filtres de recherche", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        search_piece = st.text_input("Recherche N° Pièce", help="Numéro de pièce associé au règlement", key="piece_reglements")
    with col2:
        search_tiers = st.text_input("Recherche Code Tiers", help="Filtre sur le code client ou fournisseur", key="tiers_reglements")
    with col3:
        search_intitule = st.text_input("Recherche Raison Sociale", help="Filtre sur la raison sociale", key="intitule_reglements")
        
    col4, col5 = st.columns(2)
    _today = datetime.date.today()
    _oldest = datetime.date(2000, 1, 1)
    with col4:
        date_from = st.date_input("Date début", value=_oldest, key="df_reglements")
    with col5:
        date_to = st.date_input("Date fin", value=_today, key="dt_reglements")
        
    rg_typereg = None

    st.button(
        "▶ Appliquer les filtres",
        type="primary",
        use_container_width=True,
        key="btn_reglements",
        disabled=st.session_state.get("loading_reglements", False)
    )

_date_from_str = str(date_from) if date_from else None
_date_to_str = str(date_to) if date_to else None

# ---------------------------------------------------------------------------
# Onglets principaux
# ---------------------------------------------------------------------------
tab_client, tab_fourn = st.tabs([
    "Encaissements Clients (Ventes)",
    "Décaissements Fournisseurs (Achats)"
])

tab_configs = [
    (tab_client, 0, "client", "CODE CLIENT", "RAISON SOCIALE", [6]),
    (tab_fourn, 1, "fournisseur", "CODE FOURNISSEUR", "RAISON SOCIALE", [16]),
]

for tab, domaine, key_prefix, code_col, intitule_col, do_type in tab_configs:
    with tab:
        st.subheader("Historique des Règlements" if domaine == 0 else "Historique des Décaissements")
        with st.spinner("Chargement des règlements..."):
            df_reg = get_formatted_reglements(
                client_schema=client_schema,
                domaine=domaine,
                search_piece=search_piece,
                search_tiers=search_tiers,
                search_intitule=search_intitule,
                date_from=_date_from_str,
                date_to=_date_to_str,
                rg_typereg=rg_typereg,
                do_type=do_type
            )
            
        if not df_reg.empty:
            st.markdown("*💡 Cliquez sur un règlement pour voir les lignes du document associé.*")
            
            selection = show_df(
                df_reg,
                on_select="rerun",
                selection_mode="single-row",
                key_suffix=f"sel_reg_{key_prefix}"
            )
            
            sel_rows = selection.get("selection", {}).get("rows", [])
            if sel_rows:
                idx = sel_rows[0]
                piece_no = df_reg.iloc[idx]["N PIECE"]
                tiers_name = df_reg.iloc[idx][intitule_col]
                reg_montant = df_reg.iloc[idx]["MONTANT"]
                
                st.divider()
                st.subheader(f"🔍 Détail du Document Associé : {piece_no}")
                st.markdown(f"**Tiers :** {tiers_name} | **Montant Réglé :** {reg_montant:,.2f} DH")
                
                if piece_no and piece_no != "-":
                    with st.spinner("Chargement des lignes du document..."):
                        lignes = get_documents_ligne(client_schema, piece_no)
                        
                    if lignes:
                        df_l = pd.DataFrame(lignes)
                        cols_l = {
                            "ar_ref": "Réf. Article",
                            "dl_design": "Désignation",
                            "dl_qte": "Qté",
                            "dl_prixunitaire": "PU HT",
                            "dl_montantht": "Montant HT",
                            "dl_montantttc": "Montant TTC"
                        }
                        df_l_show = df_l[[c for c in cols_l.keys() if c in df_l.columns]].rename(columns=cols_l)
                        show_df(df_l_show, key_suffix=f"reg_lignes_{key_prefix}")
                    else:
                        st.warning("Aucune ligne trouvée pour ce document ou document introuvable.")
                else:
                    st.warning("Aucun numéro de pièce valide n'est associé à ce règlement.")
        else:
            st.info("Aucun règlement trouvé.")
