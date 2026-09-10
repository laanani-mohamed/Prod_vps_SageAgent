"""
Dash/pages/2_Fichier_de_Base.py
Page 2 — Fichier de Base (Articles, Clients, Dépôts, Familles, Lots, Collaborateurs)
"""
import os
import streamlit as st
import pandas as pd
from components.styles_fichier_base import apply_fichier_base_css
from components.data_tables import show_df
from components.charts import render_product_evolution_chart
from components.auth_guard import require_auth, handle_auth_error, require_api_health

apply_fichier_base_css()
require_auth()

from services.referentiel_service import (
    get_articles, get_comptes_tiers, get_depots,
    get_familles, get_lots_series, get_collaborateurs
)
from services.article_service import get_article_top_clients, get_article_stock_depots, get_article_stats
from services.tiers_service import search_comptes_tiers
from services.depot_service import get_depots_summary

st.header("Fichier de Base")

with st.sidebar:
    client_schema = st.session_state.get("client_schema", "")
    limit = 100000000

require_api_health()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Articles", "Clients", "Fournisseurs", "Dépôts", "Familles"]
)

# ---------------------------------------------------------------------------
# Options des filtres
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_base_options(schema):
    if not schema:
        return {"art_des": ["Tout"], "art_ref": ["Tout"], "cli_nom": ["Tout"], "cli_ref": ["Tout"], "fou_nom": ["Tout"], "fou_ref": ["Tout"], "fam_int": ["Tout"], "fam_code": ["Tout"]}
    try:
        import pandas as pd
        from services.referentiel_service import get_articles, get_comptes_tiers, get_familles
        
        opts = {"art_des": ["Tout"], "art_ref": ["Tout"], "cli_nom": ["Tout"], "cli_ref": ["Tout"], "fou_nom": ["Tout"], "fou_ref": ["Tout"], "fam_int": ["Tout"], "fam_code": ["Tout"]}
        
        arts = get_articles(schema, limit=100000)
        if arts:
            df_a = pd.DataFrame(arts)
            opts["art_des"] += sorted([str(x) for x in df_a["ar_design"].dropna().unique() if str(x).strip()]) if "ar_design" in df_a.columns else []
            opts["art_ref"] += sorted([str(x) for x in df_a["ar_ref"].dropna().unique() if str(x).strip()]) if "ar_ref" in df_a.columns else []
            
        tiers = get_comptes_tiers(schema, limit=100000)
        if tiers:
            df_t = pd.DataFrame(tiers)
            if "ct_type" in df_t.columns and "ct_intitule" in df_t.columns:
                opts["cli_nom"] += sorted([str(x) for x in df_t[df_t["ct_type"] == 0]["ct_intitule"].dropna().unique() if str(x).strip()])
                opts["cli_ref"] += sorted([str(x) for x in df_t[df_t["ct_type"] == 0]["ct_num"].dropna().unique() if str(x).strip()]) if "ct_num" in df_t.columns else []
                opts["fou_nom"] += sorted([str(x) for x in df_t[df_t["ct_type"] == 1]["ct_intitule"].dropna().unique() if str(x).strip()])
                opts["fou_ref"] += sorted([str(x) for x in df_t[df_t["ct_type"] == 1]["ct_num"].dropna().unique() if str(x).strip()]) if "ct_num" in df_t.columns else []
                
        fams = get_familles(schema, limit=100000)
        if fams:
            df_f = pd.DataFrame(fams)
            opts["fam_int"] += sorted([str(x) for x in df_f["fa_intitule"].dropna().unique() if str(x).strip()]) if "fa_intitule" in df_f.columns else []
            opts["fam_code"] += sorted([str(x) for x in df_f["fa_codefamille"].dropna().unique() if str(x).strip()]) if "fa_codefamille" in df_f.columns else []
            
        return opts
    except Exception as e:
        handle_auth_error(e)
        return {"art_des": ["Tout"], "art_ref": ["Tout"], "cli_nom": ["Tout"], "cli_ref": ["Tout"], "fou_nom": ["Tout"], "fou_ref": ["Tout"], "fam_int": ["Tout"], "fam_code": ["Tout"]}

base_opts = fetch_base_options(client_schema)

# ---------------------------------------------------------------------------
# Tab 1 : Articles
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Catalogue Articles")
    
    options_fam = []
    fam_names_map = {}
    try:
        fam_list = get_familles(client_schema, limit=500)
        for f in fam_list:
            code = f.get("fa_codefamille")
            if code:
                options_fam.append(code)
                name = str(f.get("fa_intitule")).strip() if f.get("fa_intitule") else code
                fam_names_map[code] = name
    except Exception as e:
        handle_auth_error(e)
        
    col1, col2, col3 = st.columns(3)
    with col1:
        search_design = st.selectbox("🔍 Recherche par désignation", options=base_opts["art_des"], key="art_des")
    with col2:
        search_ref = st.selectbox("🔍 Recherche par référence", options=base_opts["art_ref"], key="art_ref")
    with col3:
        search_fam_code = st.multiselect("📁 Famille", options=options_fam, format_func=lambda x: fam_names_map.get(x, x), key="art_fam")
    
    filters_art = {"with_stock": True, "with_lots": True}
    if search_design and search_design != "Tout": filters_art["ar_design"] = [search_design]
    if search_ref and search_ref != "Tout": filters_art["ar_ref"] = search_ref
    if search_fam_code: filters_art["fa_codefamille"] = search_fam_code

    with st.spinner("Chargement des articles..."):
        articles = get_articles(client_schema, limit, filters_art)
    
    if articles:
        df = pd.DataFrame(articles)
        cols_to_show = ["ar_ref", "ar_design", "fa_codefamille", "ar_prixach", "ar_prixven", "qte_stock_totale"]
        df_show = df[[c for c in cols_to_show if c in df.columns]]
        rename_map = {
            "ar_ref": "Réf.", "ar_design": "Désignation", "fa_codefamille": "Famille",
            "ar_prixach": "Prix Achat", "ar_prixven": "Prix Vente", 
            "qte_stock_totale": "Stock Actuel"
        }
        df_show = df_show.rename(columns=rename_map)
        
        st.markdown("*Cliquez sur un article pour voir ses statistiques (Top 10 Clients, Stock, KPIs).*")
        selection_art = show_df(
            df_show,
            on_select="rerun",
            selection_mode="single-row",
            key_suffix="articles"
        )
        
        sel_art_rows = selection_art.get("selection", {}).get("rows", [])
        if sel_art_rows:
            idx = sel_art_rows[0]
            selected_ar_ref = df_show.iloc[idx]["Réf."]
            selected_design = df_show.iloc[idx]["Désignation"]
            
            st.divider()
            st.markdown(f"#### Détails de l'article : **{selected_ar_ref} - {selected_design}**")
            
            c_top, c_stock = st.columns(2)
            
            with c_top:
                st.markdown("**Top 10 Clients (Ventes)**")
                with st.spinner("Analyse des ventes..."):
                    top_c = get_article_top_clients(client_schema, selected_ar_ref)
                if not top_c.empty:
                    show_df(top_c, key_suffix="top_c")
                else:
                    st.info("Aucune vente client exploitable trouvée.")
                    
            with c_stock:
                st.markdown("**Détail du Stock (Dépôts)**")
                with st.spinner("Chargement des dépôts..."):
                    df_dep = get_article_stock_depots(client_schema, selected_ar_ref)
                if not df_dep.empty:
                    show_df(df_dep, key_suffix="art_dep")
                else:
                    st.info("Aucune information de stock ou de dépôt disponible.")

            st.divider()
            st.markdown("**Statistiques Produit**")

            _art_row = df.iloc[idx]
            _prixach = float(_art_row.get("ar_prixach") or 0.0)
            _prixven = float(_art_row.get("ar_prixven") or 0.0)
            _stock   = float(_art_row.get("qte_stock_totale") or 0.0)

            st.markdown("**Période d'analyse**")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                import datetime
                date_from_stat = st.date_input(
                    "Date début",
                    value=datetime.date.today().replace(month=1, day=1),
                    key="stat_date_from"
                )
            with col_d2:
                date_to_stat = st.date_input(
                    "Date fin",
                    value=datetime.date.today(),
                    key="stat_date_to"
                )

            st.divider()

            with st.spinner(f"Calcul des statistiques pour {selected_ar_ref}..."):
                stats = get_article_stats(
                    client_schema=client_schema,
                    ar_ref=selected_ar_ref,
                    ar_prixach=_prixach,
                    ar_prixven=_prixven,
                    qte_stock_actuel=_stock,
                    date_from=str(date_from_stat),
                    date_to=str(date_to_stat),
                )

            st.markdown("##### Indicateurs de base")
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                with st.container(border=True, key="kpi1"):
                    st.metric(
                        "Stock actuel",
                        f"{_stock:,.1f}",
                        help="Quantité en stock au moment de la consultation"
                    )
            with k2:
                with st.container(border=True, key="kpi2"):
                    st.metric(
                        "Quantité vendue",
                        f"{stats['quantite_vendue']:,.1f}",
                        help=f"Sur la période {date_from_stat} → {date_to_stat}"
                    )
            with k3:
                with st.container(border=True, key="kpi3"):
                    st.metric(
                        "CA HT",
                        f"{stats['chiffre_affaires_ht']:,.2f} DH",
                        help="Chiffre d'affaires hors taxes sur la période"
                    )
            with k4:
                with st.container(border=True, key="kpi4"):
                    st.metric(
                        "Coût d'achat total",
                        f"{stats['cout_achat_total']:,.2f} DH",
                        help=f"Qté vendue × Prix achat catalogue ({_prixach:,.2f} DH)"
                    )

            st.markdown("")

            st.markdown("##### Métriques analytiques")
            k5, k6, k7, k8 = st.columns(4)

            with k5:
                with st.container(border=True, key="kc1"):
                    st.metric(
                        "Marge brute",
                        f"{stats['marge_brute']:,.2f} DH",
                        help="CA HT − Coût d'achat total"
                    )
            with k6:
                with st.container(border=True, key="kc2"):
                    st.metric(
                        "Taux de marge",
                        f"{stats['marge_brute_pct']:.1f} %",
                        help="Marge brute / CA HT × 100"
                    )
            with k7:
                with st.container(border=True, key="kc3"):
                    st.metric(
                        "Rentabilité globale",
                        f"{stats['rentabilite_globale']:.1f} %",
                        help="Marge brute / Coût d'achat × 100"
                    )


            st.divider()
    else:
        st.info("Aucun article trouvé.")

# ---------------------------------------------------------------------------
# Tab 2 : Clients 
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("Comptes Clients")
    col1, col2 = st.columns(2)
    with col1:
        search_intitule = st.selectbox("🔍 Recherche par nom", options=base_opts["cli_nom"], key="client_nom")
    with col2:
        search_ref = st.selectbox("🔍 Recherche par référence", options=base_opts["cli_ref"], key="client_ref")
    
    type_tiers = "Clients"

    with st.spinner("Chargement..."):
        df_tiers = search_comptes_tiers(
            client_schema=client_schema,
            search_term=search_intitule if search_intitule != "Tout" else "",
            search_ref=search_ref if search_ref != "Tout" else "",
            type_filter=type_tiers,
            limit=limit
        )
    
    if not df_tiers.empty:
        show_df(df_tiers, key_suffix="Clients")
    else:
        st.info("Aucun compte Clients trouvé.")

# ---------------------------------------------------------------------------
# Tab 3 : Fournisseurs
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("Comptes Fournisseurs")
    col1, col2 = st.columns(2)
    with col1:
        search_intitule = st.selectbox("🔍 Recherche par nom", options=base_opts["fou_nom"], key="Fournisseurs_nom")
    with col2:
        search_ref = st.selectbox("🔍 Recherche par référence", options=base_opts["fou_ref"], key="Fournisseurs_ref")
    
    type_tiers = "Fournisseurs"

    with st.spinner("Chargement..."):
        df_tiers = search_comptes_tiers(
            client_schema=client_schema,
            search_term=search_intitule if search_intitule != "Tout" else "",
            search_ref=search_ref if search_ref != "Tout" else "",
            type_filter=type_tiers,
            limit=limit
        )
    
    if not df_tiers.empty:
        show_df(df_tiers, key_suffix="Fournisseurs")
    else:
        st.info("Aucun compte Fournisseurs trouvé.")

# ---------------------------------------------------------------------------
# Tab 4 : Dépôts
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("Dépôts de Stock")
    with st.spinner("Chargement des dépôts..."):
        df_depots = get_depots_summary(client_schema)
    
    if not df_depots.empty:
        show_df(df_depots, key_suffix="depots")
    else:
        st.info("Aucun dépôt trouvé.")

# ---------------------------------------------------------------------------
# Tab 5 : Familles
# ---------------------------------------------------------------------------
with tab5:
    st.subheader("Familles d'articles")
    col1, col2 = st.columns(2)
    with col1:
        search_fam = st.selectbox("🔍 Recherche par intitulé", options=base_opts["fam_int"], key="fam_int")
    with col2:
        search_fam_code = st.selectbox("🔍 Recherche par code", options=base_opts["fam_code"], key="fam_code")
    filters_fam = {}
    if search_fam and search_fam != "Tout": filters_fam["fa_intitule"] = search_fam
    if search_fam_code and search_fam_code != "Tout": filters_fam["fa_codefamille"] = [search_fam_code]

    with st.spinner("Chargement..."):
        familles = get_familles(client_schema, limit, filters_fam)
    
    if familles:
        df = pd.DataFrame(familles)
        cols_to_show = ["fa_codefamille", "fa_intitule", "fa_suivistock", "nb_articles", "u_intitule"]
        df_show = df[[c for c in cols_to_show if c in df.columns]].copy()
            
        suivi_map = {0: "Aucun", 1: "Sérialisé", 2: "CMUP", 3: "FIFO", 4: "LIFO", 5: "Par lot"}
        if "fa_suivistock" in df_show.columns:
            df_show["fa_suivistock"] = df_show["fa_suivistock"].map(suivi_map)
            
        rename_map = {
            "fa_codefamille": "Code Famille",
            "fa_intitule": "Intitulé",
            "fa_suivistock": "Suivi Stock",
            "nb_articles": "Nombre d'Articles",
            "u_intitule": "Unité de Vente"
        }
        df_show = df_show.rename(columns=rename_map)
        
        st.markdown("*Sélectionnez une ou plusieurs familles pour afficher leurs articles.*")
        selection = show_df(
            df_show,
            on_select="rerun",
            selection_mode="multi-row",
            key_suffix="familles"
        )
        
        selected_rows = selection.get("selection", {}).get("rows", [])
        if selected_rows:
            selected_fa_codes = [df.iloc[idx]["fa_codefamille"] for idx in selected_rows]
            
            st.divider()
            st.markdown(f"#### Articles des familles sélectionnées : **{', '.join(selected_fa_codes)}**")
            with st.spinner("Chargement des articles..."):
                arts_fam = get_articles(client_schema, limit=500, filters={"fa_codefamille": selected_fa_codes})
                if arts_fam:
                    df_arts = pd.DataFrame(arts_fam)
                    cols_arts = ["ar_ref", "ar_design", "fa_codefamille", "ar_prixach", "ar_prixven", "qte_stock_totale"]
                    rename_arts = {
                        "ar_ref": "Réf.", "ar_design": "Nom Article", "fa_codefamille": "Famille",
                        "ar_prixach": "Prix Achat", "ar_prixven": "Prix Vente", "qte_stock_totale": "Stock Actuel"
                    }
                    df_arts_show = df_arts[[c for c in cols_arts if c in df_arts.columns]].rename(columns=rename_arts)
                    show_df(df_arts_show, key_suffix="arts_fam")
                else:
                    st.warning("Aucun article trouvé pour ces familles.")
    else:
        st.info("Aucune famille trouvée.")
