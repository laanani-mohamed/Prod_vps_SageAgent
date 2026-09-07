"""
Dash/pages/7_Rapports.py
Page 7 — Rapports BI
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import httpx

from components.styles_initiale import apply_custom_css
from components.auth_guard import require_auth, handle_auth_error
from config import API_BASE_URL, SOURCE_TYPE
from utils.exports import export_df_to_excel, export_df_to_pdf, export_visite_to_pdf
from services.stock_service import get_stock_insights
from services.referentiel_service import get_comptes_tiers

apply_custom_css()
require_auth()

st.title("Rapports BI")

# Obtenir le schéma
client_schema = st.session_state.get("client_schema", "")
token = st.session_state.get("access_token", "")

headers = {"Authorization": f"Bearer {token}"}

# ---------------------------------------------------------------------------
# Helpers API
# ---------------------------------------------------------------------------
def fetch_rapport_ca(group_by: str, date_from: str, date_to: str):
    try:
        resp = httpx.post(
            f"{API_BASE_URL}/api/bi/rapport/ca",
            json={
                "client_schema": client_schema,
                "source_type": SOURCE_TYPE,
                "group_by": group_by,
                "date_from": date_from,
                "date_to": date_to
            },
            headers=headers,
            timeout=15.0
        )
        if resp.status_code == 200:
            return resp.json().get("data", [])
        else:
            st.error(f"Erreur {resp.status_code}: {resp.text}")
            return []
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        return []

@st.cache_data(ttl=600, show_spinner=False)
def fetch_stock_insights(expiry_days: int):
    """Récupère les articles proches de la péremption."""
    if not token:
        return []
    
    payload = {
        "client_schema": client_schema,
        "source_type": "db_latest",
        "insight_type": "expiration",
        "expiry_days": expiry_days
    }
    try:
        r = httpx.post(f"{API_BASE_URL}/api/stock/insights", json=payload, headers=headers, timeout=15.0)
        if r.status_code == 200:
            return r.json().get("data", [])
        st.error(f"Erreur API Stock ({r.status_code}) : {r.text}")
        return []
    except Exception as e:
        st.error(f"Erreur de connexion API Stock : {e}")
        return []

@st.cache_data(ttl=600, show_spinner=False)
def fetch_balance_client():
    """Récupère le rapport Balance Client."""
    if not token:
        return []
    
    payload = {
        "client_schema": client_schema,
        "source_type": "db_latest"
    }
    try:
        r = httpx.post(f"{API_BASE_URL}/api/bi/rapport/balance", json=payload, headers=headers, timeout=15.0)
        if r.status_code == 200:
            return r.json().get("data", [])
        st.error(f"Erreur API BI ({r.status_code}) : {r.text}")
        return []
    except Exception as e:
        st.error(f"Erreur de connexion API BI : {e}")
        return []

@st.cache_data(ttl=600, show_spinner=False)
def fetch_valeur_stock():
    """Récupère la valeur du stock par dépôt/famille/article."""
    if not token:
        return []
    payload = {
        "client_schema": client_schema,
        "source_type": "db_latest"
    }
    try:
        r = httpx.post(f"{API_BASE_URL}/api/bi/rapport/valeur-stock", json=payload, headers=headers, timeout=30.0)
        if r.status_code == 200:
            return r.json().get("data", [])
        st.error(f"Erreur API BI ({r.status_code}) : {r.text}")
        return []
    except Exception as e:
        st.error(f"Erreur de connexion API BI : {e}")
        return []

# ---------------------------------------------------------------------------
# Onglets
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "1. Chiffre d'Affaire",
    "2. Comparaison CA",
    "3. Balance",
    "4. Valeur du Stock",
    "5. Avant Visite Client",
    "6. Produits Dormants",
    "7. Lots en Péremption",

])

# ---------------------------------------------------------------------------
# Tab 1 : Rapport CA
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Chiffre d'Affaire")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        grouping = st.selectbox(
            "Grouper par", 
            options=["client", "region", "commercial"],
            format_func=lambda x: "Client" if x == "client" else ("Région" if x == "region" else "Collaborateur")
        )
    with col2:
        d_from = st.date_input("Date début", value=date.today().replace(month=1, day=1), key="d_from_t1")
    with col3:
        d_to = st.date_input("Date fin", value=date.today(), key="d_to_t1")
        
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
    
    with col_btn1:
        gen_clicked = st.button(
            "Générer le rapport CA",
            type="primary",
            disabled=st.session_state.get("loading_rapports_ca", False)
        )
        
    if gen_clicked:
        try:
            with st.spinner("Génération..."):
                st.session_state["loading_rapports_ca"] = True
                data = fetch_rapport_ca(grouping, d_from.isoformat(), d_to.isoformat())
        except Exception as e:
            handle_auth_error(e)
            data = []
        finally:
            st.session_state["loading_rapports_ca"] = False
            if data:
                df = pd.DataFrame(data)
                
                # Format columns based on grouping — only rename columns that exist
                if grouping == "client":
                    rename_map = {"do_tiers": "Code Client", "ct_intitule": "Nom Client", "ca_ht": "CA HT", "nb_factures": "Nb Factures"}
                elif grouping == "region":
                    rename_map = {"ct_ville": "Région", "ca_ht": "CA HT", "nb_factures": "Nb Factures"}
                elif grouping == "commercial":
                    rename_map = {"co_no": "Code Collab.", "co_fullname": "Collaborateur", "ca_ht": "CA HT", "nb_factures": "Nb Factures"}
                else:
                    rename_map = {}
                rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
                df = df.rename(columns=rename_map)
                
                for col in ["Collaborateur", "Nom Collaborateur"]:
                    if col in df.columns:
                        df[col] = df[col].replace({0: "Non Identifier", "0": "Non Identifier", "": "Non Identifier"})
                        
                st.session_state['df_tab1'] = df
                st.session_state['grouping_tab1'] = grouping
                st.session_state['subtitle_tab1'] = f"Période : {d_from.isoformat()} au {d_to.isoformat()}"
            else:
                st.session_state['df_tab1'] = pd.DataFrame()
                st.info("Aucune donnée trouvée.")

    df_t1 = st.session_state.get('df_tab1')
    if df_t1 is not None and not df_t1.empty:
        grp = st.session_state['grouping_tab1']
        sub = st.session_state['subtitle_tab1']
        
        with col_btn2:
            st.download_button(
                label="Télécharger Excel",
                data=export_df_to_excel(df_t1),
                file_name=f"Rapport_CA_{grp}_{date.today().isoformat()}.xlsx",
                type="primary",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col_btn3:
            g_label = "Client" if grp == "client" else ("Région" if grp == "region" else "Collaborateur")
            st.download_button(
                label="Télécharger PDF",
                data=export_df_to_pdf(df_t1, title=f"Rapport CA par {g_label}", subtitle=sub),
                file_name=f"Rapport_CA_{grp}_{date.today().isoformat()}.pdf",
                type="primary",
                mime="application/pdf"
            )
            
        st.markdown("---")
        total_ca = df_t1["CA HT"].sum() if "CA HT" in df_t1.columns else 0.0
        g_name = "Clients" if grp == "client" else ("Régions" if grp == "region" else "Collaborateurs")
        
        df_t1_sums = pd.DataFrame([{
            f"Nombre de {g_name}": len(df_t1),
            "CA HT Total": total_ca
        }])
        
        st.markdown(f"**Chiffre d'Affaire en Général :**")
        st.dataframe(df_t1_sums.style.format({
            "CA HT Total": "{:,.2f}"
        }))
        
        st.markdown("**Chiffre d'Affaire en Détail :**")
        st.dataframe(df_t1)

# ---------------------------------------------------------------------------
# Tab 2 : Comparaison CA
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("Comparaison Chiffre d'Affaire")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Période 1 (Référence)**")
        d_from_1 = st.date_input("Date début P1", value=date.today().replace(year=date.today().year-1, month=1, day=1), key="d_from_1")
        d_to_1 = st.date_input("Date fin P1", value=date.today().replace(year=date.today().year-1), key="d_to_1")
    with col2:
        st.markdown("**Période 2 (Comparée)**")
        d_from_2 = st.date_input("Date début P2", value=date.today().replace(month=1, day=1), key="d_from_2")
        d_to_2 = st.date_input("Date fin P2", value=date.today(), key="d_to_2")
        
    grouping_cmp = st.selectbox(
        "Grouper la comparaison par", 
        options=["client", "region", "commercial"],
        format_func=lambda x: "Client" if x == "client" else ("Région" if x == "region" else "Collaborateur"),
        key="grouping_cmp"
    )
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
    with col_btn1:
        cmp_clicked = st.button("Comparer", type="primary", key="btn_compare")
        
    if cmp_clicked:
        with st.spinner("Comparaison en cours..."):
            data1 = fetch_rapport_ca(grouping_cmp, d_from_1.isoformat(), d_to_1.isoformat())
            data2 = fetch_rapport_ca(grouping_cmp, d_from_2.isoformat(), d_to_2.isoformat())
            
            df1 = pd.DataFrame(data1)
            df2 = pd.DataFrame(data2)
            
            # Key to join on
            join_keys = []
            if grouping_cmp == "client":
                join_keys = ["do_tiers"]
                col_name_mapping = {"do_tiers": "Code", "ct_intitule": "Nom"}
            elif grouping_cmp == "region":
                join_keys = ["ct_ville"]
                col_name_mapping = {"ct_ville": "Région"}
            elif grouping_cmp == "commercial":
                join_keys = ["co_no"]
                col_name_mapping = {"co_no": "Code", "co_fullname": "Collaborateur"}

            if not df1.empty and not df2.empty:
                join_keys = [k for k in join_keys if k in df1.columns and k in df2.columns]

            if df1.empty: df1 = pd.DataFrame(columns=join_keys + ["ca_ht"])
            if df2.empty: df2 = pd.DataFrame(columns=join_keys + ["ca_ht"])

            df_merged = pd.merge(df1, df2, on=join_keys, how="outer", suffixes=('_p1', '_p2'))
            
            if 'co_fullname_p1' in df_merged.columns and 'co_fullname_p2' in df_merged.columns:
                df_merged['co_fullname'] = df_merged['co_fullname_p2'].fillna(df_merged['co_fullname_p1'])
                df_merged = df_merged.drop(columns=['co_fullname_p1', 'co_fullname_p2'])
                col_name_mapping['co_fullname'] = 'Nom Collaborateur'
                
            if 'ct_intitule_p1' in df_merged.columns and 'ct_intitule_p2' in df_merged.columns:
                df_merged['ct_intitule'] = df_merged['ct_intitule_p2'].fillna(df_merged['ct_intitule_p1'])
                df_merged = df_merged.drop(columns=['ct_intitule_p1', 'ct_intitule_p2'])
                col_name_mapping['ct_intitule'] = 'Nom Client'
                
            df_merged = df_merged.fillna(0)
            df_merged['Ecart (MAD)'] = df_merged['ca_ht_p2'] - df_merged['ca_ht_p1']
            
            def calc_pct(row):
                if row['ca_ht_p1'] == 0 and row['ca_ht_p2'] > 0: return 100.0
                if row['ca_ht_p1'] == 0 and row['ca_ht_p2'] == 0: return 0.0
                return (row['Ecart (MAD)'] / row['ca_ht_p1']) * 100
                
            df_merged['Evolution (%)'] = df_merged.apply(calc_pct, axis=1)
            
            rename_dict = col_name_mapping.copy()
            rename_dict.update({
                "ca_ht_p1": "CA Période 1",
                "ca_ht_p2": "CA Période 2"
            })
            df_show = df_merged.rename(columns=rename_dict)
            
            for col in ["Nom Collaborateur", "Code"]:
                if col in df_show.columns and grouping_cmp == "commercial":
                    df_show[col] = df_show[col].replace({0: "Non Identifier", "0": "Non Identifier", "": "Non Identifier"})
            
            desired_order = []
            if grouping_cmp == "client":
                desired_order = ["Code", "Nom Client", "CA Période 1", "CA Période 2", "Ecart (MAD)", "Evolution (%)"]
            elif grouping_cmp == "commercial":
                desired_order = ["Code", "Nom Collaborateur", "CA Période 1", "CA Période 2", "Ecart (MAD)", "Evolution (%)"]
            elif grouping_cmp == "region":
                desired_order = ["Région", "CA Période 1", "CA Période 2", "Ecart (MAD)", "Evolution (%)"]
            
            final_columns = [c for c in desired_order if c in df_show.columns]
            df_show = df_show[final_columns]
            
            st.session_state['df_tab2'] = df_show
            st.session_state['grouping_tab2'] = grouping_cmp
            st.session_state['subtitle_tab2'] = (
                f"Période 1 : {d_from_1.isoformat()} au {d_to_1.isoformat()}  |  "
                f"Période 2 : {d_from_2.isoformat()} au {d_to_2.isoformat()}"
            )
            
    df_t2 = st.session_state.get('df_tab2')
    if df_t2 is not None and not df_t2.empty:
        grp2 = st.session_state['grouping_tab2']
        sub2 = st.session_state['subtitle_tab2']
        
        with col_btn2:
            st.download_button(
                label="Télécharger Excel",
                data=export_df_to_excel(df_t2),
                file_name=f"Comparaison_CA_{grp2}_{date.today().isoformat()}.xlsx",
                type="primary",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col_btn3:
            g_label = "Client" if grp2 == "client" else ("Région" if grp2 == "region" else "Collaborateur")
            st.download_button(
                label="Télécharger PDF",
                data=export_df_to_pdf(df_t2, title=f"Comparaison CA par {g_label}", subtitle=sub2),
                file_name=f"Comparaison_CA_{grp2}_{date.today().isoformat()}.pdf",
                type="primary",
                mime="application/pdf"
            )
            
        st.markdown("---")
        total_p1 = df_t2["CA Période 1"].sum() if "CA Période 1" in df_t2.columns else 0.0
        total_p2 = df_t2["CA Période 2"].sum() if "CA Période 2" in df_t2.columns else 0.0
        ecart = total_p2 - total_p1
        evo = (ecart / total_p1 * 100) if total_p1 > 0 else 0.0
        
        df_cmp_sums = pd.DataFrame([{
            "CA P1 Total": total_p1,
            "CA P2 Total": total_p2,
            "Ecart Total": ecart,
            "Evolution (%)": evo
        }])
        
        # Insérer la colonne "Total" en première position
        df_cmp_sums.insert(0, "Total", len(df_t2))

        st.markdown("**Comparaison Générale :**")
        st.dataframe(df_cmp_sums.style.format({
            "Total": "{:,.0f}",
            "CA P1 Total": "{:,.2f}",
            "CA P2 Total": "{:,.2f}",
            "Ecart Total": "{:,.2f}",
            "Evolution (%)": "{:,.2f} %"
        }))
        
            
        st.markdown("**Comparaison en Détail :**")
        st.dataframe(df_t2.style.format({
            "CA Période 1": "{:,.2f}", 
            "CA Période 2": "{:,.2f}",
            "Ecart (MAD)": "{:,.2f}",
            "Evolution (%)": "{:,.2f} %"
        }))

# ---------------------------------------------------------------------------
# Tab 3 : Balance
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("Balance par Clients")
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
    with col_btn1:
        bal_clicked = st.button("Afficher la Balance", type="primary", key="btn_balance")
        
    if bal_clicked:
        with st.spinner("Génération de la balance..."):
            data = fetch_balance_client()
            if data:
                df = pd.DataFrame(data)
                
                # Remplacer 'Non identifier' si nécessaire
                if 'Nom Client' in df.columns:
                    df['Nom Client'] = df['Nom Client'].replace({0: "Non Identifier", "0": "Non Identifier", "": "Non Identifier"})
                
                # S'assurer de l'ordre des colonnes
                desired_cols = ["Ref Client", "Nom Client", "A Nouveau", "M6", "M5", "M4", "M3", "M2", "M1", "En Cours", "Totale"]
                available_cols = [c for c in desired_cols if c in df.columns]
                df_show = df[available_cols]
                
                st.session_state['df_tab3'] = df_show
            else:
                st.session_state['df_tab3'] = pd.DataFrame()
                st.info("Aucune donnée de balance trouvée.")

    df_t3 = st.session_state.get('df_tab3')
    if df_t3 is not None and not df_t3.empty:
        with col_btn2:
            st.download_button(
                label="Télécharger Excel",
                data=export_df_to_excel(df_t3),
                file_name=f"Balance_Clients_{date.today().isoformat()}.xlsx",
                type="primary",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col_btn3:
            st.download_button(
                label="Télécharger PDF",
                data=export_df_to_pdf(
                    df_t3, 
                    title="Balance par Clients", 
                    subtitle=f"Généré le {date.today().isoformat()}"
                ),
                file_name=f"Balance_Clients_{date.today().isoformat()}.pdf",
                type="primary",
                mime="application/pdf"
            )
            
        # Format columns dynamically
        numeric_cols = ["A Nouveau", "M6", "M5", "M4", "M3", "M2", "M1", "En Cours", "Totale"]
        format_dict = {col: "{:,.2f}" for col in numeric_cols if col in df_t3.columns}
        
        st.markdown("**la balance générale :**")
        # Table des totaux
        sums = df_t3[[c for c in numeric_cols if c in df_t3.columns]].sum()
        df_sums = pd.DataFrame([sums])
        df_sums.insert(0, "Nom Client", len(df_t3))
        
        st.dataframe(df_sums.style.format(format_dict))
        
        st.markdown("**Détail de la balance :**")
        st.dataframe(df_t3.style.format(format_dict))

# ---------------------------------------------------------------------------
# Tab 4 : Valeur du Stock
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("Valeur du Stock")

    col_vue, col_filtre = st.columns([1, 2])
    with col_vue:
        vue_option = st.selectbox(
            "Vue",
            options=["Par Dépôt", "Par Famille", "Par Article"],
            key="valstock_vue",
        )

    col_btn_gen, _ = st.columns([1, 3])
    with col_btn_gen:
        valstock_clicked = st.button("Générer", type="primary", key="btn_valstock")

    if valstock_clicked:
        with st.spinner("Chargement de la valeur du stock..."):
            raw = fetch_valeur_stock()
        st.session_state["valstock_raw"] = raw

    raw = st.session_state.get("valstock_raw")
    if raw:
        df_raw = pd.DataFrame(raw)
        # Nettoyage numérique
        for c in ["qte_stock", "prix_revient", "valeur_stock"]:
            if c in df_raw.columns:
                df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce").fillna(0.0)

        # Filtre contextuel
        with col_filtre:
            if vue_option == "Par Dépôt":
                depots = sorted(df_raw["de_intitule"].dropna().unique().tolist())
                filtre_val = st.selectbox("Filtrer par dépôt", options=["Tous"] + depots, key="valstock_filtre_depot")
                if filtre_val != "Tous":
                    df_raw = df_raw[df_raw["de_intitule"] == filtre_val]
            elif vue_option == "Par Famille":
                familles = sorted(df_raw["fa_intitule"].dropna().unique().tolist())
                filtre_val = st.selectbox("Filtrer par famille", options=["Tous"] + familles, key="valstock_filtre_famille")
                if filtre_val != "Tous":
                    df_raw = df_raw[df_raw["fa_intitule"] == filtre_val]
            else:
                articles = sorted(df_raw["ar_design"].dropna().unique().tolist())
                filtre_val = st.selectbox("Filtrer par article", options=["Tous"] + articles, key="valstock_filtre_article")
                if filtre_val != "Tous":
                    df_raw = df_raw[df_raw["ar_design"] == filtre_val]

        # Agrégation selon la vue choisie
        if vue_option == "Par Dépôt":
            df_show = df_raw.groupby("de_intitule", as_index=False).agg(
                {"qte_stock": "sum", "valeur_stock": "sum"}
            ).rename(columns={"de_intitule": "Dépôt", "qte_stock": "Qté Stock", "valeur_stock": "Valeur Stock"})
            df_show = df_show.sort_values("Valeur Stock", ascending=False)
        elif vue_option == "Par Famille":
            df_show = df_raw.groupby(["fa_intitule"], as_index=False).agg(
                {"qte_stock": "sum", "valeur_stock": "sum"}
            ).rename(columns={"fa_intitule": "Famille", "qte_stock": "Qté Stock", "valeur_stock": "Valeur Stock"})
            df_show = df_show.sort_values("Valeur Stock", ascending=False)
        else:
            df_show = df_raw[["de_intitule", "fa_intitule", "ar_ref", "ar_design", "qte_stock", "prix_revient", "valeur_stock"]].copy()
            df_show = df_show.rename(columns={
                "de_intitule": "Dépôt", "fa_intitule": "Famille",
                "ar_ref": "Réf. Article", "ar_design": "Désignation",
                "qte_stock": "Qté Stock", "prix_revient": "Prix Revient", "valeur_stock": "Valeur Stock",
            })
            df_show = df_show.sort_values("Valeur Stock", ascending=False)

        # Total
        total_valeur = df_show["Valeur Stock"].sum()
        st.metric("Valeur Totale du Stock", f"{total_valeur:,.2f} DA")

        st.dataframe(df_show, use_container_width=True)

        col_xl, col_pdf = st.columns(2)
        with col_xl:
            st.download_button(
                label="📥 Télécharger Excel",
                data=export_df_to_excel(df_show),
                file_name=f"Valeur_Stock_{vue_option.replace(' ', '_')}_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        with col_pdf:
            st.download_button(
                label="📄 Télécharger PDF",
                data=export_df_to_pdf(df_show, title=f"Valeur du Stock — {vue_option}"),
                file_name=f"Valeur_Stock_{vue_option.replace(' ', '_')}_{date.today().isoformat()}.pdf",
                mime="application/pdf",
                type="primary",
            )

# ---------------------------------------------------------------------------
# Tab 5 : Rapport Client Avant Visite
# ---------------------------------------------------------------------------
with tab5:
    st.subheader("Avant Visite Client")

    # ── Chargement des clients pour la liste déroulante ─────────────────────
    @st.cache_data(ttl=300, show_spinner=False)
    def _load_clients():
        rows = get_comptes_tiers(client_schema, filters={"ct_type": [0]})
        return [(r.get("ct_num", ""), r.get("ct_intitule", "")) for r in rows if r.get("ct_num")]

    clients_list = _load_clients()
    client_options = {f"{code} — {nom}": code for code, nom in clients_list}

    col_sel, col_btn_gen = st.columns([3, 1])
    with col_sel:
        selected_label = st.selectbox(
            "Sélectionner un client",
            options=list(client_options.keys()),
            key="visite_client_select",
            placeholder="Rechercher par ref ou nom…",
        )
    with col_btn_gen:
        st.markdown("<br>", unsafe_allow_html=True)
        visite_clicked = st.button("Générer le rapport", type="primary", key="btn_visite")

    if visite_clicked and selected_label:
        do_tiers = client_options[selected_label]
        payload = {
            "client_schema": client_schema,
            "source_type": "db_latest",
            "do_tiers": do_tiers,
        }
        try:
            with st.spinner("Génération du rapport avant visite…"):
                r = httpx.post(
                    f"{API_BASE_URL}/api/bi/rapport/visite-client",
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )
            if r.status_code == 200:
                data_visite = r.json().get("data", [{}])[0]
                st.session_state["visite_data"]   = data_visite
                st.session_state["visite_client"] = selected_label
                st.session_state["visite_tiers"]  = do_tiers
            else:
                st.error(f"Erreur API {r.status_code} : {r.text}")
                st.session_state["visite_data"] = None
        except Exception as e:
            handle_auth_error(e)
            st.session_state["visite_data"] = None

    # ── Affichage du rapport ─────────────────────────────────────────────────
    visite_data   = st.session_state.get("visite_data")
    visite_client = st.session_state.get("visite_client", "")
    visite_tiers  = st.session_state.get("visite_tiers",  "")

    if visite_data:
        st.markdown(f"### 📋 Client : {visite_client}")
        subtitle_visite = f"Client : {visite_tiers} — Généré le {date.today().isoformat()}"

        # Construire tous les DataFrames pour l'export groupé
        _dfs_export = {}

        def _show_section(title: str, key: str, numeric_cols: list = None):
            st.markdown(f"#### {title}")
            rows = visite_data.get(key, [])
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            if df.empty:
                st.info("Aucune donnée.")
            else:
                fmt = {c: "{:,.2f}" for c in (numeric_cols or []) if c in df.columns}
                st.dataframe(df.style.format(fmt) if fmt else df, use_container_width=True)
            _dfs_export[key] = df
            return df

        _show_section("1. Bons de Commande en Cours",     "bc_en_cours",
                       ["Montant HT", "Montant TTC"])
        st.markdown("---")
        _show_section("2. Factures Non Réglées",          "factures_non_reglees",
                       ["Montant HT", "Montant TTC", "Reste à Payer"])
        st.markdown("---")
        _show_section("3. Articles Vendus par Mois (6M)", "articles_par_mois",
                       ["M6", "M5", "M4", "M3", "M2", "M1", "En Cours"])
        st.markdown("---")
        _show_section("4. Familles Actives (6 derniers mois)", "familles_actives",
                       ["CA HT"])
        st.markdown("---")
        _show_section("5. Familles Dormantes (vente > 6 mois)", "familles_dormantes",
                       ["CA HT"])
        st.markdown("---")
        _show_section("6. Familles Mortes (jamais vendues)",     "familles_mortes")
        st.markdown("---")

        # Section 7 — Comparaison CA
        st.markdown("#### 7. Comparaison CA (N vs N-1) — 6 mois glissants")
        rows_ca = visite_data.get("comparaison_ca", [])
        if rows_ca:
            df_ca = pd.DataFrame(rows_ca)
            num_cols_ca = [c for c in df_ca.columns if c != "Période"]
            st.dataframe(df_ca.style.format({c: "{:,.2f}" for c in num_cols_ca}),
                         use_container_width=True)
            _dfs_export["comparaison_ca"] = df_ca
        else:
            st.info("Aucune donnée de comparaison CA.")
            _dfs_export["comparaison_ca"] = pd.DataFrame()

        # ── Exports ─────────────────────────────────────────────────────────
        st.markdown("---")

        # Concaténer tous les DFs en un seul Excel multi-feuilles
        import io
        from openpyxl import Workbook
        section_labels = {
            "bc_en_cours":          "1-BCs en cours",
            "factures_non_reglees": "2-Factures impayées",
            "articles_par_mois":    "3-Articles par mois",
            "familles_actives":     "4-Familles actives",
            "familles_dormantes":   "5-Familles dormantes",
            "familles_mortes":      "6-Familles mortes",
            "comparaison_ca":       "7-Comparaison CA",
        }

        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            for key, label in section_labels.items():
                df_s = _dfs_export.get(key, pd.DataFrame())
                if not df_s.empty:
                    df_s.to_excel(writer, sheet_name=label[:31], index=False)
        excel_buf.seek(0)


        col_xl, col_pdf = st.columns(2)
        with col_xl:
            st.download_button(
                label="📥 Télécharger Excel",
                data=excel_buf.getvalue(),
                file_name=f"Rapport_Visite_{visite_tiers}_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        with col_pdf:
            from utils.exports import export_visite_to_pdf
            pdf_sections = [
                (label, _dfs_export.get(key, pd.DataFrame()))
                for key, label in section_labels.items()
            ]
            st.download_button(
                label="📄 Télécharger PDF",
                data=export_visite_to_pdf(
                    pdf_sections,
                    title=f"Rapport Avant Visite - {visite_client}",
                    subtitle=subtitle_visite,
                ),
                file_name=f"Rapport_Visite_{visite_tiers}_{date.today().isoformat()}.pdf",
                mime="application/pdf",
                type="primary",
            )

# ---------------------------------------------------------------------------
# Tab 6 : Produits Dormants
# ---------------------------------------------------------------------------
with tab6:
    st.subheader("Produits Dormants")

    col_d, col_gen = st.columns([1, 1])
    with col_d:
        dormant_months = st.number_input("Mois d'inactivité", min_value=1, max_value=24, value=6, step=1, key="rpt_dormant_months")
    with col_gen:
        st.markdown("<br>", unsafe_allow_html=True)
        dormant_clicked = st.button("Générer", type="primary", key="btn_dormant_report")

    if dormant_clicked:
        dormant_days = dormant_months * 30
        with st.spinner("Chargement des produits dormants..."):
            data_dormant = get_stock_insights(client_schema, category="dormant", limit=100000000, dormant_days=dormant_days)

        _rename_dormant = {
            "ar_ref": "Réf. Article", "ar_design": "Désignation",
            "fa_intitule": "Famille", "de_intitule": "Dépôt",
            "quantite_totale": "Qté Totale",
            "derniere_date_vente": "Dernière Vente",
            "nbr_jours_inactif": "Mois Inactivité",
        }

        if not data_dormant:
            df_dormant = pd.DataFrame()
        else:
            df_dormant = pd.DataFrame(data_dormant)
            df_dormant = df_dormant.rename(columns={k: v for k, v in _rename_dormant.items() if k in df_dormant.columns})
            cols = [v for v in _rename_dormant.values() if v in df_dormant.columns]
            df_dormant = df_dormant[cols] if cols else df_dormant

            if "Dernière Vente" in df_dormant.columns:
                df_dormant["Dernière Vente"] = pd.to_datetime(df_dormant["Dernière Vente"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("-")
            if "Mois Inactivité" in df_dormant.columns:
                df_dormant["Mois Inactivité"] = df_dormant["Mois Inactivité"].apply(
                    lambda x: "Jamais vendu" if pd.isna(x) or x == 999999 else f"{round(float(x) / 30)} mois"
                )

        st.session_state["dormant_df"] = df_dormant
        st.session_state["dormant_months"] = dormant_months

    df_dormant = st.session_state.get("dormant_df")
    d_months = st.session_state.get("dormant_months", 6)
    if df_dormant is not None:
        st.markdown(f"#### Produits inactifs depuis plus de {d_months} mois")
        if df_dormant.empty:
            st.success("Aucun produit dormant détecté ! 🎉")
        else:
            st.dataframe(df_dormant, use_container_width=True)

            col_xl, col_pdf = st.columns(2)
            with col_xl:
                st.download_button(
                    label="📥 Télécharger Excel",
                    data=export_df_to_excel(df_dormant),
                    file_name=f"Dormants_{d_months}mois_{date.today().isoformat()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                )
            with col_pdf:
                st.download_button(
                    label="📄 Télécharger PDF",
                    data=export_visite_to_pdf(
                        [(f"Produits Dormants (inactifs > {d_months} mois)", df_dormant)],
                        title="Rapport Produits Dormants",
                        subtitle=f"Inactivite > {d_months} mois",
                    ),
                    file_name=f"Dormants_{d_months}mois_{date.today().isoformat()}.pdf",
                    mime="application/pdf",
                    type="primary",
                )

# ---------------------------------------------------------------------------
# Tab 7 : Lots en Péremption
# ---------------------------------------------------------------------------
with tab7:
    st.subheader("Lots en Péremption")

    col_p, col_gen = st.columns([1, 1])
    with col_p:
        expiry_days_rpt = st.number_input("Jours avant péremption", min_value=1, value=60, step=10, key="rpt_expiry_days")
    with col_gen:
        st.markdown("<br>", unsafe_allow_html=True)
        perempt_clicked = st.button("Générer", type="primary", key="btn_perempt_report")

    if perempt_clicked:
        with st.spinner("Chargement des lots en péremption..."):
            data_perempt = get_stock_insights(client_schema, category="peremption", limit=100000000, expiry_days=expiry_days_rpt)

        _rename_perempt = {
            "ar_ref": "Réf. Article", "ar_design": "Désignation",
            "fa_intitule": "Famille",
            "ls_noserie": "N° Lot/Série", "ls_qterestant": "Qté Restante",
            "ls_peremption": "Date Péremption", "jours_restants": "Jours Restants",
        }

        if not data_perempt:
            df_perempt = pd.DataFrame()
        else:
            df_perempt = pd.DataFrame(data_perempt)
            df_perempt = df_perempt.rename(columns={k: v for k, v in _rename_perempt.items() if k in df_perempt.columns})
            cols = [v for v in _rename_perempt.values() if v in df_perempt.columns]
            df_perempt = df_perempt[cols] if cols else df_perempt

        st.session_state["perempt_df"] = df_perempt
        st.session_state["perempt_days"] = expiry_days_rpt

    df_perempt = st.session_state.get("perempt_df")
    e_days = st.session_state.get("perempt_days", 60)
    if df_perempt is not None:
        st.markdown(f"#### Lots expirant dans les {e_days} prochains jours")
        if df_perempt.empty:
            st.success("Aucun lot en péremption détecté ! 🎉")
        else:
            st.dataframe(df_perempt, use_container_width=True)

            col_xl, col_pdf = st.columns(2)
            with col_xl:
                st.download_button(
                    label="📥 Télécharger Excel",
                    data=export_df_to_excel(df_perempt),
                    file_name=f"Peremption_{e_days}j_{date.today().isoformat()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                )
            with col_pdf:
                st.download_button(
                    label="📄 Télécharger PDF",
                    data=export_visite_to_pdf(
                        [(f"Lots en Peremption (< {e_days} jours)", df_perempt)],
                        title="Rapport Lots en Peremption",
                        subtitle=f"Expiration dans les {e_days} prochains jours",
                    ),
                    file_name=f"Peremption_{e_days}j_{date.today().isoformat()}.pdf",
                    mime="application/pdf",
                    type="primary",
                )
