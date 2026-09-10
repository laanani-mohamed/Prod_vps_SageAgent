"""
Dash/pages/5_Mouvements_Stock.py
Page 5 — Stock & Mouvements (v2)
"""
import os
import streamlit as st
import pandas as pd
import datetime
from components.styles_initiale import apply_custom_css
from components.data_tables import show_df
from components.auth_guard import require_auth, handle_auth_error, require_api_health

apply_custom_css()
require_auth()

from services.stock_service import get_stock_availability, get_stock_insights, get_mouvements_entrants, get_mouvements_sortants
from services.referentiel_service import get_familles, get_depots

st.header("Stock & Mouvements")

require_api_health()

# ---------------------------------------------------------------------------
# Rendu commun aux onglets Mouvements Entrants / Sortants
# ---------------------------------------------------------------------------
_MOUVEMENT_LABELS = {
    "entrant": {"title": "Entrants", "adj": "entrante", "empty_adj": "entrant", "key": "ent"},
    "sortant": {"title": "Sortants", "adj": "sortante", "empty_adj": "sortant", "key": "sort"},
}


def render_mouvements_tab(direction: str, fetch_fn, client_schema: str, search_ref: str, limit: int):
    labels = _MOUVEMENT_LABELS[direction]
    key = labels["key"]

    st.subheader(f"Mouvements {labels['title']}")

    with st.expander("🔍 Filtres de date", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            today = datetime.date.today()
            date_from = st.date_input("Date début", value=today.replace(month=1, day=1), key=f"{key}_date_from")
        with c2:
            date_to = st.date_input("Date fin", value=today, key=f"{key}_date_to")
        st.button("▶ Appliquer", type="primary", use_container_width=True, key=f"btn_{key}")

    with st.spinner(f"Chargement des mouvements {labels['title'].lower()}..."):
        df_mvt = fetch_fn(
            client_schema=client_schema,
            ar_ref=search_ref,
            date_from=str(date_from),
            date_to=str(date_to),
            limit=limit,
        )

    if df_mvt.empty:
        st.info(f"Aucun document {labels['empty_adj']} trouvé pour les filtres sélectionnés.")
        return

    total_val = df_mvt["Montant HT"].sum() if "Montant HT" in df_mvt.columns else 0

    k1, k2 = st.columns(2)
    k1.metric("Nombre de documents", f"{len(df_mvt):,}")
    k2.metric(f"Valeur HT {labels['adj']}", f"{total_val:,.2f} DH")
    st.divider()

    types = ["Tous"] + sorted(df_mvt["Type"].unique().tolist()) if "Type" in df_mvt.columns else ["Tous"]
    sel_type = st.selectbox("Filtrer par type", types, key=f"sel_type_{key}")
    df_mvt_show = df_mvt if sel_type == "Tous" else df_mvt[df_mvt["Type"] == sel_type]

    st.markdown(f"*{len(df_mvt_show):,} document(s) affiché(s)*")
    selection = show_df(
        df_mvt_show.reset_index(drop=True),
        on_select="rerun",
        selection_mode="single-row",
        key_suffix=f"stock_{key}"
    )

    sel_rows = selection.get("selection", {}).get("rows", [])
    if not sel_rows:
        return

    row = df_mvt_show.reset_index(drop=True).iloc[sel_rows[0]]
    piece_no = row.get("N° Pièce", "-")
    st.divider()
    st.subheader(f"🔍 Lignes du document : {piece_no}")

    if piece_no and piece_no != "-":
        with st.spinner("Chargement des lignes..."):
            from services.documents_service import get_documents_ligne
            filters_l = {}
            if search_ref:
                filters_l["ar_ref"] = [search_ref]
            lignes = get_documents_ligne(client_schema, do_piece=piece_no, filters=filters_l)

        if lignes:
            df_l = pd.DataFrame(lignes)
            cols_l = {
                "ar_ref": "Réf. Article",
                "dl_design": "Désignation",
                "dl_qte": "Qté",
                "dl_prixunitaire": "PU HT",
                "dl_montantht": "Montant HT"
            }
            df_l_show = df_l[[c for c in cols_l.keys() if c in df_l.columns]].rename(columns=cols_l)
            show_df(df_l_show, key_suffix=f"{key}_lignes")
        else:
            st.warning("Aucune ligne trouvée pour ce document (ou ne correspondant à votre filtre article).")

# ---------------------------------------------------------------------------
# Sidebar — filtres communs
# ---------------------------------------------------------------------------
with st.sidebar:
    client_schema = st.session_state.get("client_schema", "")

limit = 100000000

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "État des Stocks",
    "Mouvements Entrants",
    "Mouvements Sortants",
    "Alertes & Insights",
])

# ===========================================================================
# Tab 1 : État des Stocks
# ===========================================================================
with tab1:
    st.subheader("État actuel des stocks")

    famille_codes = ["Tous"]
    famille_names_map = {"Tous": "Toutes les familles"}
    try:
        fam_data = get_familles(client_schema, limit=100000000)
        if fam_data:
            for f in fam_data:
                code = str(f.get("fa_codefamille")).strip() if f.get("fa_codefamille") else None
                name = str(f.get("fa_intitule")).strip() if f.get("fa_intitule") else code
                if code and code not in famille_names_map:
                    famille_codes.append(code)
                    famille_names_map[code] = name if name else code
            famille_codes = ["Tous"] + sorted(famille_codes[1:])
    except Exception as e:
        handle_auth_error(e)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        search_ref = st.text_input("Référence", key="search_ref_stock")
    with col2:
        search_name = st.text_input("Désignation (Nom)", key="search_name_stock")
    with col3:
        search_fam = st.selectbox("Famille", famille_codes, format_func=lambda x: famille_names_map.get(x, x), key="search_fam_stock")
    with col4:
        only_available = st.checkbox("Articles disponibles", value=False, key="only_available_stock")

    with st.spinner("Chargement des stocks..."):
        ar_ref_list = [search_ref.strip()] if search_ref.strip() else None
        search_terms_list = [search_name.strip()] if search_name.strip() else None
        fa_codefamille_list = [search_fam] if search_fam != "Tous" else None
        
        stocks_data = get_stock_availability(
            client_schema, ar_ref=ar_ref_list,
            search_terms=search_terms_list,
            fa_codefamille=fa_codefamille_list,
            with_depots=True, by_depot=True, only_rupture=False, limit=limit
        )

        try:
            depots_list = get_depots(client_schema)
            nbr_depots = len(depots_list) if depots_list else 0
        except Exception as e:
            handle_auth_error(e)
            nbr_depots = 0

    if stocks_data:
        df_stock = pd.DataFrame(stocks_data)

        if "quantite_depot" in df_stock.columns:
            df_stock["quantite_depot"] = pd.to_numeric(df_stock["quantite_depot"], errors="coerce").fillna(0)

        if only_available and "quantite_depot" in df_stock.columns:
            df_stock = df_stock[df_stock["quantite_depot"] > 0]

        if not df_stock.empty:
            total_articles = df_stock["ar_ref"].nunique() if "ar_ref" in df_stock.columns else 0
            total_qte = df_stock.get("quantite_depot", pd.Series()).sum()
            
            km1, km2, km3 = st.columns(3)
            km1.metric("Articles uniques", f"{total_articles:,}")
            km2.metric("Quantité totale", f"{int(total_qte):,}")
            km3.metric("Nombre de dépôts", f"{nbr_depots:,}")
            st.divider()

            st.markdown("Détail du stock par Dépôt")
            cols_s = {
                "ar_ref":          "Réf. Article",
                "ar_design":       "Désignation",
                "fa_codefamille":  "Code Famille",
                "de_intitule":     "Nom Dépôt",
                "quantite_depot":  "Quantité en Stock",
            }
            if "quantite_depot" in df_stock.columns:
                df_stock["quantite_depot"] = df_stock["quantite_depot"].astype(int)
                
            df_stock_show = df_stock[[c for c in cols_s if c in df_stock.columns]].rename(columns=cols_s)
            show_df(df_stock_show, key_suffix="stock_state")
        else:
            st.info("Aucun article en stock correspondant à vos critères après filtrage des articles disponibles.")
    else:
        st.info("Aucun article en stock trouvé.")


# ===========================================================================
# Tab 2 : Mouvements ENTRANTS
# ===========================================================================
with tab2:
    render_mouvements_tab("entrant", get_mouvements_entrants, client_schema, search_ref, limit)


# ===========================================================================
# Tab 3 : Mouvements SORTANTS
# ===========================================================================
with tab3:
    render_mouvements_tab("sortant", get_mouvements_sortants, client_schema, search_ref, limit)


# ===========================================================================
# Tab 4 : Alertes & Insights
# ===========================================================================
with tab4:
    st.subheader("Type d'alerte :")

    insight_type = st.radio(
        " ",
        options=[
            ("Rupture de stock", "rupture"),
            ("Produits dormants", "dormant"),
            ("Produits jamais vendus", "jamais_vendu"),
            ("Lots en péremption", "peremption"),
        ],
        format_func=lambda x: x[0],
        horizontal=True
    )

    col_ins1, col_ins2, col_ins3, col_ins4 = st.columns(4)
    with col_ins1:
        ins_ref = st.text_input("🔍 Référence article", key="ins_ref_filter", placeholder="ex: ART (optionnel)")
    with col_ins2:
        ins_name = st.text_input("🔍 Désignation (Nom)", key="ins_name_filter", placeholder="ex: Nom (optionnel)")
    with col_ins3:
        ins_fam = st.selectbox("Famille", famille_codes, format_func=lambda x: famille_names_map.get(x, x), key="ins_fam_filter")
    with col_ins4:
        expiry_days = 30
        dormant_days = 90
        if insight_type[1] == "peremption":
            expiry_days = st.number_input(
                "Jours avant péremption :",
                min_value=1, max_value=365, value=30, step=1,
                key="expiry_days_stock"
            )
        elif insight_type[1] == "dormant":
            dormant_days = st.number_input(
                "Jours d'inactivité supérieur à :",
                min_value=1, max_value=1000000, value=90, step=1,
                key="dormant_days_stock"
            )

    with st.spinner(f"Chargement des alertes ({insight_type[0]})..."):
        insights = get_stock_insights(
            client_schema, category=insight_type[1],
            limit=limit, expiry_days=expiry_days, dormant_days=dormant_days
        )

    if insights:
        df_ins = pd.DataFrame(insights)

        if ins_ref.strip():
            df_ins = df_ins[df_ins["ar_ref"].astype(str).str.contains(ins_ref.strip(), case=False, na=False)]
        if ins_name.strip() and "ar_design" in df_ins.columns:
            df_ins = df_ins[df_ins["ar_design"].astype(str).str.contains(ins_name.strip(), case=False, na=False)]
        if ins_fam != "Tous" and "fa_codefamille" in df_ins.columns:
            df_ins = df_ins[df_ins["fa_codefamille"].astype(str).str.strip() == ins_fam.strip()]

        if not df_ins.empty:
            if "quantite_totale" in df_ins.columns:
                df_ins["quantite_totale"] = pd.to_numeric(df_ins["quantite_totale"], errors="coerce").fillna(0).astype(int)
            if "ls_qterestant" in df_ins.columns:
                df_ins["ls_qterestant"] = pd.to_numeric(df_ins["ls_qterestant"], errors="coerce").fillna(0).astype(int)

            if insight_type[1] in ("rupture", "dormant", "jamais_vendu") and "fa_codefamille" in df_ins.columns:
                st.markdown(f"#### 📁 Nombre de produits concernés par Famille ({insight_type[0]})")
                df_fam_alert = df_ins.groupby("fa_codefamille").size().reset_index(name="Nombre de produits")
                df_fam_alert = df_fam_alert.sort_values(by="Nombre de produits", ascending=False)
                show_df(df_fam_alert, key_suffix="stock_alerts_fam")
                st.divider()

            st.markdown("#### Liste détaillée des alertes")
            rename_map = {
                "ar_ref":          "Réf. Article",
                "ar_design":       "Désignation",
                "fa_codefamille":  "Code Famille",
                "de_intitule":     "Dépôt",
                "suivi_lot":       "Suivi par Lot",
                "quantite_totale": "Quantité Totale",
                "derniere_date_vente": "Dernière Vente",
                "nbr_jours_inactif": "Jours d'inactivité",
                "ls_noserie":      "N° Lot/Série",
                "ls_qterestant":   "Qté Restante",
                "ls_peremption":   "Date Péremption",
                "jours_restants":  "Jours Restants",
            }
            df_ins_show = df_ins.rename(columns=rename_map)
            cols_to_show = [c for c in rename_map.values() if c in df_ins_show.columns]
            
            # Formatage de la date de dernière vente
            if "Dernière Vente" in df_ins_show.columns:
                df_ins_show["Dernière Vente"] = pd.to_datetime(df_ins_show["Dernière Vente"], errors="coerce").dt.strftime("%d/%m/%Y")
                df_ins_show["Dernière Vente"] = df_ins_show["Dernière Vente"].fillna("-")
            
            # Formatage des Jours d'inactivité
            if "Jours d'inactivité" in df_ins_show.columns:
                df_ins_show["Jours d'inactivité"] = df_ins_show["Jours d'inactivité"].apply(
                    lambda x: "Jamais vendu" if pd.isna(x) or x == 999999 else f"{int(x)} j"
                )
            
            # Masquer les colonnes inutiles pour certains types d'alertes
            if insight_type[1] in ("rupture", "jamais_vendu"):
                if "Dernière Vente" in cols_to_show:
                    cols_to_show.remove("Dernière Vente")
                if "Jours d'inactivité" in cols_to_show:
                    cols_to_show.remove("Jours d'inactivité")

            show_df(df_ins_show[cols_to_show], key_suffix="stock_alerts_detail")
        else:
            st.info(f"Aucune alerte de type '{insight_type[0]}' ne correspond à vos filtres de recherche.")
    else:
        st.success(f"Aucune alerte de type '{insight_type[0]}' à signaler ! 🎉")
