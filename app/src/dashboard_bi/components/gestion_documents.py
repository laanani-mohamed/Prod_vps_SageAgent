"""
components/gestion_documents.py

Rendu partagé des pages "Gestion des Ventes" / "Gestion des Achats" —
mêmes filtres et mêmes onglets par type de document, seuls le domaine
(0=Ventes, 1=Achats) et les libellés changent.
"""
import streamlit as st
import pandas as pd

from components.data_tables import show_df
from components.date_filters import date_range_filter
from components.auth_guard import handle_auth_error
from services.documents_service import get_documents_entete, get_documents_ligne, get_formatted_documents, commercial_label


def render_gestion_documents_page(
    domaine: int,
    key_ns: str,
    code_label: str,
    intitule_label: str,
    tiers_logical: str,
    tiers_col: str,
    detail_title: str,
    detail_label: str,
    tab_labels: list,
    tab_configs: list,
    client_schema: str,
):
    """
    domaine        : 0 = Ventes, 1 = Achats (passé à get_documents_entete/get_formatted_documents)
    key_ns         : préfixe des clés de widgets ("ventes" / "achats")
    code_label     : libellé du selectbox "Recherche Code ..."
    intitule_label : libellé du selectbox "Recherche Intitulé ..."
    tiers_logical  : "client" / "fournisseur" (texte d'aide, en minuscules)
    tiers_col      : colonne du document contenant l'intitulé du tiers
    detail_title   : titre affiché au-dessus du détail de la pièce sélectionnée
    detail_label   : libellé devant le nom du tiers dans le détail ("Client" / "Fournisseur")
    tab_labels     : libellés des onglets, dans l'ordre de tab_configs
    tab_configs    : liste de `category` (une par onglet, même ordre que tab_labels)
    """
    with st.expander("🔍 Filtres de recherche", expanded=True):
        @st.cache_data(ttl=300, show_spinner=False)
        def fetch_filter_options(schema):
            empty = (["Tout"], ["Tout"], ["Tout"], {}, None, None)
            if not schema:
                return empty
            try:
                docs = get_documents_entete(schema, domaine=[domaine])
                if not docs:
                    return empty
                df = pd.DataFrame(docs)
                pieces = ["Tout"] + sorted([str(x) for x in df["do_piece"].dropna().unique() if str(x).strip()]) if "do_piece" in df.columns else ["Tout"]
                tiers = ["Tout"] + sorted([str(x) for x in df["do_tiers"].dropna().unique() if str(x).strip()]) if "do_tiers" in df.columns else ["Tout"]
                intitules = ["Tout"] + sorted([str(x) for x in df["ct_intitule"].dropna().unique() if str(x).strip()]) if "ct_intitule" in df.columns else ["Tout"]

                commerciaux = {}
                if "co_no" in df.columns:
                    co_cols = [c for c in ("co_no", "co_nom", "co_prenom") if c in df.columns]
                    for r in df[co_cols].drop_duplicates().to_dict("records"):
                        try:
                            co_no = 0 if pd.isna(r["co_no"]) else int(r["co_no"])
                        except (TypeError, ValueError):
                            continue
                        label = commercial_label(co_no, r.get("co_nom"), r.get("co_prenom"))
                        if label in commerciaux and commerciaux[label] != co_no:
                            label = f"{label} ({co_no})"
                        commerciaux[label] = co_no

                date_min = date_max = None
                if "do_date" in df.columns:
                    dates = pd.to_datetime(df["do_date"].astype(str).str[:10], errors="coerce").dropna()
                    if not dates.empty:
                        date_min, date_max = dates.min().date(), dates.max().date()

                return pieces, tiers, intitules, commerciaux, date_min, date_max
            except Exception:
                return empty

        pieces_opts, tiers_opts, intitule_opts, commerciaux, date_min, date_max = fetch_filter_options(client_schema)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            search_piece = st.selectbox("Recherche N° Pièce", options=pieces_opts, help="Numéro exact du document", key=f"piece_{key_ns}")
        with col2:
            search_tiers = st.selectbox(code_label, options=tiers_opts, help=f"Filtre sur le code {tiers_logical}", key=f"tiers_{key_ns}")
        with col3:
            search_intitule = st.selectbox(intitule_label, options=intitule_opts, help=f"Filtre sur le nom du {tiers_logical}", key=f"intitule_{key_ns}")
        with col4:
            search_commercial = st.selectbox(
                "Commercial",
                options=["Tout"] + sorted(commerciaux),
                help="Commercial (collaborateur) porté par le document",
                key=f"commercial_{key_ns}",
            )

        col5, col6, col7 = st.columns([1, 1, 2])
        date_from, date_to, dates_ok = date_range_filter(
            f"df_{key_ns}", f"dt_{key_ns}", date_min, date_max, cols=(col5, col6)
        )
        with col7:
            st.write("")  # Espacement pour aligner verticalement
            st.write("")
            unpaid_only = st.checkbox("Non réglés uniquement (Reste > 0)", key=f"unpaid_{key_ns}")

        st.button(
            "▶ Appliquer les filtres",
            type="primary",
            use_container_width=True,
            key=f"btn_{key_ns}",
            disabled=st.session_state.get(f"loading_{key_ns}", False)
        )

    if not dates_ok:
        return

    tabs = st.tabs(tab_labels)

    for tab, key_prefix in zip(tabs, tab_configs):
        with tab:
            try:
                with st.spinner("Chargement des documents..."):
                    st.session_state[f"loading_{key_ns}"] = True
                    df_docs = get_formatted_documents(
                        client_schema=client_schema,
                        domaine=domaine,
                        category=key_prefix,
                        search_piece="" if search_piece == "Tout" else search_piece,
                        search_tiers="" if search_tiers == "Tout" else search_tiers,
                        search_intitule="" if search_intitule == "Tout" else search_intitule,
                        date_from=date_from.strftime("%Y-%m-%d") if date_from else None,
                        date_to=date_to.strftime("%Y-%m-%d") if date_to else None,
                        unpaid_only=unpaid_only,
                        co_no=commerciaux.get(search_commercial),
                    )
            except Exception as e:
                handle_auth_error(e)
                df_docs = pd.DataFrame()
            finally:
                st.session_state[f"loading_{key_ns}"] = False

            if not df_docs.empty:
                st.markdown("*Cliquez sur une ligne pour afficher les détails du document.*")

                selection = show_df(
                    df_docs,
                    on_select="rerun",
                    selection_mode="single-row",
                    key_suffix=f"sel_{key_ns}_{key_prefix}"
                )

                sel_rows = selection.get("selection", {}).get("rows", [])
                if sel_rows:
                    idx = sel_rows[0]
                    piece_no = df_docs.iloc[idx]["N PIECE"]
                    tiers_name = df_docs.iloc[idx][tiers_col]

                    st.divider()
                    st.subheader(f"{detail_title} : {piece_no}")
                    st.markdown(f"**{detail_label} :** {tiers_name}")

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
                        show_df(df_l_show, key_suffix=f"lignes_{key_ns}_{key_prefix}")
                    else:
                        st.warning("Aucune ligne trouvée pour ce document.")
            else:
                st.info("Aucun document trouvé.")
