"""
Dash/pages/1_Tableau_de_Bord.py
Page 1 — Tableau de Bord (KPIs & Indicateurs de Performance)
"""
import os
import streamlit as st
import pandas as pd
from datetime import date
import plotly.graph_objects as go

from components.styles_initiale import apply_custom_css
from components.data_tables import show_df
from components.auth_guard import require_auth, handle_auth_error

apply_custom_css()
require_auth()

from services.bi_service import get_dashboard_analytique, get_dashboard_kpis
from services.top_client_service import get_top_clients_from_docentete
from services.base import check_api_health

# ---------------------------------------------------------------------------
# Titre
# ---------------------------------------------------------------------------
st.header("Tableau de Bord — Indicateurs de Performance")

# ---------------------------------------------------------------------------
# Sidebar — uniquement le schéma et actualisation
# ---------------------------------------------------------------------------
with st.sidebar:
    client_schema = st.session_state.get("client_schema", "")
    today = date.today()
    

# ---------------------------------------------------------------------------
# Vérification API
# ---------------------------------------------------------------------------
if not check_api_health():
    st.error(
        "L'API FastAPI n'est pas joignable sur `http://localhost:8000`.\n\n"
        "Lancez d'abord le backend :\n"
        "```\n./venv/bin/uvicorn api.main:app --app-dir src --reload --port 8000\n```"
    )
    st.stop()

# ---------------------------------------------------------------------------
# Périodes de calcul (YTD automatique sur l'année de la dernière transaction)
# ---------------------------------------------------------------------------
latest_date = today
try:
    from services.documents_service import get_documents_entete
    docs = get_documents_entete(client_schema, domaine=[0, 1], limit=1)
    if docs and docs[0].get("do_date"):
        raw_date = docs[0].get("do_date").split(" ")[0]
        latest_date = date.fromisoformat(raw_date)
except Exception:
    pass

ytd_from = latest_date.replace(month=1, day=1).isoformat()
ytd_to   = latest_date.isoformat()
all_time_from = "2000-01-01"

# Même période un an plus tôt (29 février → 28 février), comme le calcul du CA N-1 côté API
_ytd_to_n1 = latest_date.replace(year=latest_date.year - 1, day=28) if (latest_date.month, latest_date.day) == (2, 29) \
    else latest_date.replace(year=latest_date.year - 1)
ytd_from_n1 = latest_date.replace(year=latest_date.year - 1, month=1, day=1).isoformat()
ytd_to_n1   = _ytd_to_n1.isoformat()
periode_txt = f"**Période** : du {ytd_from} au {ytd_to}"

# Seuils de pilotage (MAD)
OBJECTIF_CA      = 25_000_000
LIMITE_ENCOURS   = 30_000_000
LIMITE_DETTES    = 20_000_000

# ---------------------------------------------------------------------------
# Calcul des KPIs
# ---------------------------------------------------------------------------
with st.spinner("Calcul des indicateurs principaux..."):
    try:
        kpis_data = get_dashboard_kpis(client_schema, ytd_from, ytd_to)
        kpis = kpis_data.get("kpis", {})
        
        ca = kpis.get("chiffre_affaires", 0.0)
        ca_n_1 = kpis.get("ca_n_minus_1", 0.0)
        achats = kpis.get("total_achats", 0.0)
        valeur_stock = kpis.get("valeur_stock", 0.0)
        encours_clients = kpis.get("encours_clients", 0.0)
        dettes_fournisseurs = kpis.get("dettes_fournisseurs", 0.0)
        ca_evo = kpis.get("ca_evolution_pct")  # None si CA N-1 ≤ 0
        nb_clients = kpis.get("nb_clients_actifs", 0)
    except Exception as e:
        handle_auth_error(e)
        ca = ca_n_1 = achats = valeur_stock = encours_clients = dettes_fournisseurs = 0.0
        ca_evo = None
        nb_clients = 0

# Taux d'atteinte calculés sur les montants affichés (même période, même base HT/TTC)
pct_ca      = round(ca / OBJECTIF_CA * 100, 1)
pct_encours = round(encours_clients / LIMITE_ENCOURS * 100, 1)
pct_dettes  = round(dettes_fournisseurs / LIMITE_DETTES * 100, 1)

st.caption(f"Période : du {ytd_from} au {ytd_to}")

# ---------------------------------------------------------------------------
# KPI Metrics
# ---------------------------------------------------------------------------
def to_m_str(val):
    if not val and val != 0:
        return "—"
    n = float(val)
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}".replace('.', ',') + " MMAD"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.2f}".replace('.', ',') + " KMAD"
    return f"{n:,.2f}".replace('.', ',') + " MAD"

km1, km2 = st.columns(2)
km5, km6 = st.columns(2)
km3, km4, km7 = st.columns(3)


with km1:
    with st.container(border=True, key="kpi1"):
        pct_ca_val = pct_ca
        st.metric(
            label="Chiffre d'Affaires (Obj)",
            value=to_m_str(ca),
            #delta=f"{pct_ca_val}% de l'objectif 25 MMAD",
            #delta_color="inverse",
            help=(
                "**Formule** : Σ montants HT des factures de vente (avoirs déduits)  \n"
                f"{periode_txt}  \n"
                "**% de l'objectif** : CA HT ÷ 25 000 000 × 100"
            ),
        )
        st.html(
            f"""
            <div style="
                color: #000000; 
                font-size: 0.85rem; 
                margin-top: -10px; 
                font-family: inherit;
            ">
                {pct_ca_val}% de l'objectif 25 MMAD
            </div>
            """
        )

with km2:
    year_n_1 = latest_date.year - 1
    with st.container(border=True, key="kpi2"):
        st.metric(
            label=f"Chiffre d'Affaires ({year_n_1})",
            value=to_m_str(ca_n_1),
            help=(
                "**Formule** : Σ montants HT des factures de vente (avoirs déduits)  \n"
                f"**Période** : du {ytd_from_n1} au {ytd_to_n1} (même période un an plus tôt)  \n"
                f"**Évolution** : (CA {latest_date.year} − CA {year_n_1}) ÷ CA {year_n_1} × 100 "
                f"— N/A si le CA {year_n_1} est nul ou négatif"
            ),
        )
        st.html(
            f"""
            <div style="
                color: #000000; 
                font-size: 0.85rem; 
                margin-top: -10px; 
                font-family: inherit;
            ">
                {f"{ca_evo:+.1f}% vs {year_n_1}" if ca_evo is not None else "N/A"}
            </div>
            """
        )

with km3:
    with st.container(border=True, key="kpi3"):
        st.metric(
            label="Total Achats",
            value=to_m_str(achats),
            help=(
                "**Formule** : Σ montants HT des factures d'achat (avoirs fournisseurs déduits)  \n"
                f"{periode_txt}"
            ),
        )

with km4:
    with st.container(border=True, key="kpi4"):
        st.metric(
            label="Valeur Stock",
            value=to_m_str(valeur_stock),
            help=(
                "**Formule** : Σ montant du stock Sage (AS_MontSto), tous dépôts  \n"
                "**Date** : état actuel du stock"
            ),
        )

with km5:
    with st.container(border=True, key="kpi5"):
        st.metric(
            label="Encours Clients",
            value=to_m_str(encours_clients),
            help=(
                "**Formule** : Σ (Montant TTC − Montant réglé) des factures de vente dont le reste à payer est > 0  \n"
                "**Période** : tout l'historique  \n"
                "**% de la limite** : Encours ÷ 30 000 000 × 100"
            ),
        )
        delta_text_encours = f"{pct_encours}% de la limite 30 MMAD"
        st.html(
            f"""
            <div style="
                color: #000000; 
                font-size: 0.85rem; 
                margin-top: -10px; 
                font-family: inherit;
            ">
                {delta_text_encours}
            </div>
            """
        )

with km6:
    with st.container(border=True, key="kpi6"):
        st.metric(
            label="Dettes Fournisseurs",
            value=to_m_str(dettes_fournisseurs),
            help=(
                "**Formule** : Σ (Montant TTC − Montant réglé) des factures d'achat dont le reste à payer est > 0  \n"
                "**Période** : tout l'historique  \n"
                "**% de la limite** : Dettes ÷ 20 000 000 × 100"
            ),
        )
        st.html(
            f"""
            <div style="
                color: #000000; 
                font-size: 0.85rem; 
                margin-top: -10px; 
                font-family: inherit;
            ">
                {pct_dettes}% de la limite 20 MMAD
            </div>
            """
        )

with km7:
    with st.container(border=True, key="kpi7"):
        st.metric(
            label="Clients Actifs",
            value=f"{nb_clients}",
            help=(
                "**Formule** : nombre de clients distincts ayant au moins une facture de vente  \n"
                f"{periode_txt}"
            ),
        )

st.divider()

# ---------------------------------------------------------------------------
# KPIs Analytiques (Marge, DSO, Litige, Retour, Conversion)
# ---------------------------------------------------------------------------
with st.spinner("Calcul des KPIs analytiques..."):
    try:
        analytique = get_dashboard_analytique(client_schema, ytd_from, ytd_to)
    except Exception as e:
        handle_auth_error(e)
        analytique = {}

st.subheader("Indicateurs Analytiques")
kc1, kc2, kc3, kc4 = st.columns(4)
#kc1, kc2 = st.columns(2)
#kc3, kc4 = st.columns(2)

marge_brute   = analytique.get("marge_brute", 0.0)
taux_marge    = analytique.get("taux_marge", 0.0)
taux_impayes  = analytique.get("taux_impayes", 0.0)
taux_retour   = analytique.get("taux_retour", 0.0)
taux_conv     = analytique.get("taux_conversion", 0.0)
nb_fac_livre  = analytique.get("nb_fac", 0)
nb_fac_total  = analytique.get("nb_factures_total", 0)
nb_fac_imp    = analytique.get("nb_factures_impayees", 0)
nb_bl         = analytique.get("nb_bon_livraison", 0)
nb_br         = analytique.get("nb_bon_retour", 0)
nb_devis      = analytique.get("nb_devis", 0)
nb_fac_conv    = analytique.get("nb_bc_issus_devis", 0)

sub_info_color = "#001219"
with kc1:
    with st.container(border=True, key="kc1"):
        st.metric(
            label="Marge Brute",
            value=to_m_str(marge_brute),
            help=(
                "**Formule** : CA HT des lignes facturées − Σ (Quantité livrée × Coût unitaire)  \n"
                "**Coût unitaire** : prix de revient de la ligne ; à défaut le CMUP ; "
                "à défaut le prix d'achat de la fiche article  \n"
                "**Taux de marge** : Marge brute ÷ CA HT × 100  \n"
                f"{periode_txt}"
            ),
        )
        st.markdown(
            f"<span style='color:{sub_info_color};font-size:0.85rem;'>"
            f"Taux de marge : **{taux_marge:.1f} %**"
            f"</span>",
            unsafe_allow_html=True,
        )

with kc2:
    with st.container(border=True, key="kc2"):
        st.metric(
            label="Taux Factures Impayées",
            value=f"{taux_impayes:.1f} %",
            help=(
                "**Formule** : Factures impayées ÷ Factures de vente × 100  \n"
                "**Facture impayée** : reste à payer (TTC − réglé) > 1 MAD  \n"
                "**Période** : tout l'historique"
            ),
        )
        st.markdown(
            f"<span style='color:{sub_info_color};font-size:0.85rem;'>"
            f"{nb_fac_imp} impayées sur {nb_fac_total} factures"
            f"</span>",
            unsafe_allow_html=True,
        )

with kc3:
    with st.container(border=True, key="kc3"):
        st.metric(
            label="Taux de Retour",
            value=f"{taux_retour:.1f} %",
            help=(
                "**Formule** : Bons de retour ÷ Factures de vente × 100  \n"
                f"{periode_txt}"
            ),
        )
        st.markdown(
            f"<span style='color:{sub_info_color};font-size:0.85rem;'>"
            f"{nb_br} bon(s) de retour sur {nb_fac_livre} factures"
            f"</span>",
            unsafe_allow_html=True,
        )

with kc4:
    with st.container(border=True, key="kc4"):
        # Sans aucun devis sur la période, le taux n'a pas de sens (l'API renvoie 0)
        st.metric(
            label="Taux Conversion Devis → Facture",
            value=f"{taux_conv:.1f} %" if nb_devis else "N/A",
            help=(
                "**Formule** : Factures ÷ (Factures + Devis non transformés) × 100  \n"
                "**Devis non transformés** : documents encore au stade de devis  \n"
                "N/A s'il n'y a aucun devis sur la période  \n"
                f"{periode_txt}"
            ),
        )
        st.markdown(
            f"<span style='color:{sub_info_color};font-size:0.85rem;'>"
            f"{nb_fac_conv} factures, {nb_devis} devis non transformés"
            f"</span>",
            unsafe_allow_html=True,
        )


st.subheader("Classements")
tab1, tab2, tab3 = st.tabs(["Top Clients", "Top Fournisseurs", "Top Familles"])

with tab1:
    with st.container(border=True):
        top_clients_data = analytique.get("top_clients", [])
        if not top_clients_data:
            with st.spinner("Chargement du classement clients..."):
                top_cl = get_top_clients_from_docentete(
                    client_schema, ytd_from, ytd_to, limit=10
                )
            if top_cl:
                df_top = pd.DataFrame(top_cl)
                rename_map = {"ct_intitule": "Nom Client", "ca_ht": "CA HT (MAD)"}
                df_top_show = df_top[[c for c in rename_map.keys() if c in df_top.columns]].rename(columns=rename_map)
                if "CA HT (MAD)" in df_top_show.columns:
                    df_top_show["CA HT (MAD)"] = pd.to_numeric(df_top_show["CA HT (MAD)"], errors="coerce").astype(float)
                show_df(df_top_show, key_suffix="top_clients_1")
            else:
                st.info("Aucune vente enregistrée pour cette période.")
        else:
            df_top = pd.DataFrame(top_clients_data)
            df_top_show = pd.DataFrame({
                "Nom Client": df_top.get("ct_intitule", df_top.get("ct_num", [])),
                "CA HT (MAD)": pd.to_numeric(df_top["ca_ht"], errors="coerce").astype(float),
                "% du CA": pd.to_numeric(df_top["pct_ca"], errors="coerce").astype(float),
            })
            show_df(df_top_show, key_suffix="top_clients_2")

with tab2:
    with st.container(border=True):
        top_fournisseurs_data = analytique.get("top_fournisseurs", [])
        if top_fournisseurs_data:
            df_top_f = pd.DataFrame(top_fournisseurs_data)
            df_top_f_show = pd.DataFrame({
                "Nom Fournisseur": df_top_f.get("ct_intitule", df_top_f.get("ct_num", [])),
                "Encours (MAD)": pd.to_numeric(df_top_f.get("encours", pd.Series([0]*len(df_top_f))), errors="coerce").astype(float),
            })
            show_df(df_top_f_show, key_suffix="top_fournisseurs")
        else:
            st.info("Aucun encours fournisseur enregistré.")

with tab3:
    with st.container(border=True):
        top_familles_data = analytique.get("top_familles", [])
        if top_familles_data:
            df_fam = pd.DataFrame(top_familles_data)
            df_fam_show = pd.DataFrame({
                "Code Famille": df_fam["fa_codefamille"],
                "Famille": df_fam["fa_intitule"],
                "CA HT": pd.to_numeric(df_fam["ca_ht"], errors="coerce").astype(float),
                "% du CA": pd.to_numeric(df_fam["pct_ca"], errors="coerce").astype(float),
            })

            st.caption("💡 Cliquez sur une famille pour voir ses articles.")
            selection_fam = show_df(
                df_fam_show,
                on_select="rerun",
                selection_mode="single-row",
                key_suffix="top_familles"
            )

            sel_rows = selection_fam.get("selection", {}).get("rows", [])
            if sel_rows:
                idx = sel_rows[0]
                fa_code = df_fam.iloc[idx]["fa_codefamille"]
                fa_intitule = df_fam.iloc[idx]["fa_intitule"]

                st.divider()
                st.markdown(f"#### Articles — {fa_intitule}")

                top_arts_map = analytique.get("top_articles_par_famille", {})
                articles_fam = top_arts_map.get(fa_code, [])

                if articles_fam:
                    df_arts = pd.DataFrame(articles_fam)
                    df_arts_show = pd.DataFrame({
                        "Réf. Article": df_arts["ar_ref"],
                        "Désignation": df_arts["designation"],
                        "CA HT": pd.to_numeric(df_arts["ca_ht"], errors="coerce").astype(float),
                    })
                    show_df(df_arts_show, key_suffix=f"arts_{fa_code}")
                    st.caption(f"{len(df_arts)} article(s) avec CA > 0")
                else:
                    st.info("Aucun article vendu pour cette famille sur la période.")
        else:
            st.info("Aucune donnée famille disponible — la connexion à l'archive est peut-être nécessaire.")
