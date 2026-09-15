"""
Dash/pages/9_Nouveau_Bon_Commande.py
Page 9 — Saisie d'un bon de commande client.

Le bon de commande vit dans la session (aucune écriture en base) et se
matérialise par un PDF récapitulatif.
"""
import re
import datetime
import streamlit as st
import pandas as pd

from components.styles_initiale import apply_custom_css
from components.data_tables import show_df
from components.auth_guard import require_auth, handle_auth_error, require_api_health

apply_custom_css()
require_auth()

from core.constants import TAUX_TVA
from core.formatters import format_montant
from services.referentiel_service import get_articles, get_comptes_tiers, get_familles
from utils.exports import export_df_to_pdf

st.header("Nouveau Bon de Commande")

require_api_health()

with st.sidebar:
    client_schema = st.session_state.get("client_schema", "")

st.session_state.setdefault("bc_lignes", {})


def _total_ligne(ligne: dict) -> float:
    return ligne["pu"] * ligne["qte"] * (1 - ligne["remise_pct"] / 100)


def oublier_widgets_ligne(ref: str) -> None:
    """Un number_input conserve sa valeur en session tant que sa clé existe, et celle-ci
    prime sur `value`. Sans purge, réajouter un article ressortirait l'ancienne quantité."""
    for prefixe in ("bc_qte_", "bc_rem_", "bc_sup_"):
        st.session_state.pop(prefixe + ref, None)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_clients_et_familles(schema: str):
    clients = get_comptes_tiers(schema, limit=50000, filters={"ct_type": [0]})
    familles = get_familles(schema, limit=5000)
    return clients, familles


if not client_schema:
    st.error("Aucun schéma client associé à votre compte.")
    st.stop()

try:
    clients, familles = fetch_clients_et_familles(client_schema)
except Exception as e:
    handle_auth_error(e)
    st.stop()

# ---------------------------------------------------------------------------
# 1. Client — un seul champ, cherchable par référence ou par nom
# ---------------------------------------------------------------------------
clients_par_libelle = {}
for c in clients:
    num = str(c.get("ct_num") or "").strip()
    if not num:
        continue
    intitule = str(c.get("ct_intitule") or "").strip()
    clients_par_libelle[f"{num} — {intitule}" if intitule else num] = (num, intitule)

libelle_client = st.selectbox(
    "Client",
    options=sorted(clients_par_libelle),
    index=None,
    placeholder="Rechercher un client par référence ou par nom…",
    key="bc_client",
)

if not libelle_client:
    st.info("Sélectionnez un client pour commencer le bon de commande.")
    st.stop()

ct_num, ct_intitule = clients_par_libelle[libelle_client]

# ---------------------------------------------------------------------------
# 2. Recherche d'articles
# ---------------------------------------------------------------------------
st.subheader("Articles")

familles_par_libelle = {}
for f in familles:
    code = str(f.get("fa_codefamille") or "").strip()
    if not code:
        continue
    intitule = str(f.get("fa_intitule") or "").strip()
    familles_par_libelle[f"{code} — {intitule}" if intitule else code] = code

col_fam, col_ref, col_des = st.columns([2, 1, 1])
with col_fam:
    libelles_familles = st.multiselect(
        "Famille (référence ou nom)",
        options=sorted(familles_par_libelle),
        key="bc_familles",
    )
with col_ref:
    recherche_ref = st.text_input("Réf. article contient", key="bc_recherche_ref").strip()
with col_des:
    recherche_design = st.text_input("Désignation contient", key="bc_recherche_design").strip()

codes_familles = [familles_par_libelle[lib] for lib in libelles_familles]

filtres = {"with_stock": True}
if codes_familles:
    filtres["fa_codefamille"] = codes_familles
if recherche_ref:
    filtres["ar_ref"] = recherche_ref
if recherche_design:
    filtres["ar_design"] = [recherche_design]

if not (codes_familles or recherche_ref or recherche_design):
    st.info("Choisissez une famille ou saisissez une recherche pour afficher des articles.")
else:
    with st.spinner("Recherche des articles…"):
        try:
            articles = get_articles(client_schema, limit=300, filters=filtres)
        except Exception as e:
            handle_auth_error(e)
            articles = []

    if not articles:
        st.warning("Aucun article ne correspond à cette recherche.")
    else:
        df_articles = pd.DataFrame(articles)
        df_affichage = pd.DataFrame({
            "Réf. Article": df_articles["ar_ref"].astype(str),
            "Désignation": df_articles["ar_design"].astype(str),
            "Famille": df_articles["fa_codefamille"].astype(str),
            "PU HT": pd.to_numeric(df_articles["ar_prixven"], errors="coerce").fillna(0.0),
            "Stock": pd.to_numeric(df_articles["qte_stock_totale"], errors="coerce").fillna(0.0),
        })

        st.caption("Cochez un ou plusieurs articles puis ajoutez-les d'un coup : la quantité se règle dans le tableau ci-dessous.")
        selection = show_df(
            df_affichage,
            on_select="rerun",
            selection_mode="multi-row",
            key_suffix="bc_articles",
        )

        lignes_selectionnees = selection.get("selection", {}).get("rows", [])
        if lignes_selectionnees:
            articles_selectionnes = df_affichage.iloc[lignes_selectionnees]
            libelle_bouton = (
                f"Ajouter « {articles_selectionnes.iloc[0]['Réf. Article']} »"
                if len(articles_selectionnes) == 1
                else f"Ajouter les {len(articles_selectionnes)} articles sélectionnés"
            )
            if st.button(libelle_bouton, type="primary"):
                for _, article in articles_selectionnes.iterrows():
                    ref_ajout = article["Réf. Article"]
                    oublier_widgets_ligne(ref_ajout)
                    st.session_state.bc_lignes[ref_ajout] = {
                        "famille": article["Famille"],
                        "design": article["Désignation"],
                        "pu": float(article["PU HT"]),
                        "stock": float(article["Stock"]),
                        "qte": 1.0,
                        "remise_pct": 0.0,
                    }
                st.rerun()

# ---------------------------------------------------------------------------
# 3. Panier — une ligne par article, quantité et remise saisies directement
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Bon de commande")

lignes = st.session_state.bc_lignes
if not lignes:
    st.info("Aucun article dans le bon de commande.")
    st.stop()

# Un panier créé avant l'ajout de la colonne « Qté max » n'a pas de stock : on le complète.
refs_sans_stock = [ref for ref, ligne in lignes.items() if "stock" not in ligne]
if refs_sans_stock:
    try:
        stock_lu = get_articles(
            client_schema,
            limit=len(refs_sans_stock),
            filters={"ar_ref_exact": refs_sans_stock, "with_stock": True},
        )
    except Exception as e:
        handle_auth_error(e)
        stock_lu = []
    stock_par_ref = {
        str(row.get("ar_ref")): float(pd.to_numeric(row.get("qte_stock_totale"), errors="coerce") or 0.0)
        for row in stock_lu
    }
    for ref in refs_sans_stock:
        lignes[ref]["stock"] = stock_par_ref.get(ref, 0.0)

PROPORTIONS_PANIER = [0.8, 1.0, 1.2, 2.4, 1.0, 1.0, 1.1, 1.1, 1.3]

entetes = st.columns(PROPORTIONS_PANIER, vertical_alignment="bottom")
for colonne, libelle in zip(
    entetes,
    ["Suppr.", "Réf. Famille", "Réf. Article", "Désignation", "PU HT", "Qté max", "Qté", "Remise %", "Montant HT"],
):
    colonne.markdown(f"**{libelle}**")

# La quantité saisie est lue en session avant de dessiner la ligne, pour colorer toute la ligne
# dès la saisie. Les sélecteurs CSS reposent sur la position, jamais sur la référence article.
positions_depassement = [
    position
    for position, (ref, ligne) in enumerate(lignes.items())
    if float(st.session_state.get(f"bc_qte_{ref}", ligne["qte"])) > ligne["stock"]
]
if positions_depassement:
    selecteurs = ", ".join(f".st-key-bc_ligne_{p}" for p in positions_depassement)
    st.markdown(
        f"""<style>
{selecteurs} {{ background-color: rgba(229, 57, 53, 0.12); border-left: 4px solid #e53935;
  border-radius: 6px; padding: 2px 6px; }}
{", ".join(f".st-key-bc_ligne_{p} p" for p in positions_depassement)} {{ color: #c62828; font-weight: 600; }}
</style>""",
        unsafe_allow_html=True,
    )

a_supprimer = []
for position, (ref, ligne) in enumerate(lignes.items()):
    c_sup, c_fam, c_ref, c_design, c_pu, c_max, c_qte, c_remise, c_montant = st.container(
        key=f"bc_ligne_{position}"
    ).columns(PROPORTIONS_PANIER, vertical_alignment="center")
    if c_sup.checkbox("Supprimer", key=f"bc_sup_{ref}", label_visibility="collapsed"):
        a_supprimer.append(ref)

    c_fam.write(ligne["famille"])
    c_ref.write(ref)
    c_design.write(ligne["design"])
    c_pu.write(format_montant(ligne["pu"]))
    c_max.write(f"{ligne['stock']:,.2f}")

    ligne["qte"] = float(c_qte.number_input(
        "Qté", min_value=0.01, value=ligne["qte"], step=1.0, format="%.2f",
        key=f"bc_qte_{ref}", label_visibility="collapsed",
    ))
    ligne["remise_pct"] = float(c_remise.number_input(
        "Remise %", min_value=0.0, max_value=100.0, value=ligne["remise_pct"], step=1.0, format="%.2f",
        key=f"bc_rem_{ref}", label_visibility="collapsed",
    ))
    c_montant.write(format_montant(_total_ligne(ligne)))

if a_supprimer:
    for ref in a_supprimer:
        lignes.pop(ref, None)
        oublier_widgets_ligne(ref)
    st.rerun()

remise_globale = st.number_input(
    "Remise globale sur le total (%)",
    min_value=0.0, max_value=100.0, value=0.0, step=1.0, format="%.2f",
    key="bc_remise_globale",
)

total_brut = sum(_total_ligne(ligne) for ligne in lignes.values())
total_ht = total_brut * (1 - remise_globale / 100)
total_ttc = total_ht * (1 + TAUX_TVA / 100)

montant_remise = sum(ligne["pu"] * ligne["qte"] for ligne in lignes.values()) - total_ht

col_remise, col_ht, col_ttc = st.columns(3)
col_remise.metric("Montant remisé", format_montant(montant_remise))
col_ht.metric("Total HT", format_montant(total_ht))
col_ttc.metric(f"Total TTC (TVA {TAUX_TVA:.0f} %)", format_montant(total_ttc))

if positions_depassement:
    st.warning(
        "Certaines quantités dépassent le stock disponible (lignes surlignées en rouge ci-dessus). "
        "Le bon de commande peut tout de même être généré."
    )

# ---------------------------------------------------------------------------
# 4. PDF récapitulatif
# ---------------------------------------------------------------------------
date_commande = datetime.date.today().isoformat()

df_pdf = pd.DataFrame([
    {
        "Réf. Famille": ligne["famille"],
        "Réf. Article": ref,
        "Désignation": ligne["design"],
        "Qté": ligne["qte"],
        "PU HT": ligne["pu"],
        "Remise %": ligne["remise_pct"],
        "Total HT": _total_ligne(ligne),
    }
    for ref, ligne in lignes.items()
])

nb_lignes_articles = len(df_pdf)
# Ligne entièrement vide : tracée sans bordure, elle détache le récapitulatif des produits.
df_pdf.loc[len(df_pdf)] = ["", "", "", "", "", "", ""]
if remise_globale > 0:
    df_pdf.loc[len(df_pdf)] = ["", "", "Remise globale", "", "", remise_globale, -(total_brut - total_ht)]
df_pdf.loc[len(df_pdf)] = ["", "", "TOTAL HT", "", "", "", total_ht]
df_pdf.loc[len(df_pdf)] = ["", "", f"TVA {TAUX_TVA:.0f} %", "", "", "", total_ttc - total_ht]
df_pdf.loc[len(df_pdf)] = ["", "", "TOTAL TTC", "", "", "", total_ttc]

st.download_button(
    label="Télécharger le bon de commande (PDF)",
    data=export_df_to_pdf(
        df_pdf,
        title=f"Bon de Commande - {ct_intitule or ct_num}",
        subtitle=f"Client {ct_num} - Date {date_commande}",
        recap_rows=len(df_pdf) - nb_lignes_articles,
    ),
    # La référence client alimente un nom de fichier : on la restreint aux caractères sûrs.
    file_name=f"{re.sub(r'[^A-Za-z0-9_-]', '_', ct_num)}_{date_commande}.pdf",
    mime="application/pdf",
    type="primary",
)
