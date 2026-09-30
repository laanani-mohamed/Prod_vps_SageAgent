"""
components/tiers_stats.py

Affichage des statistiques d'un client ou d'un fournisseur (Fichier de Base),
à partir de la réponse de POST /api/bi/stats-tiers.
Cartes KPI au style du Tableau de Bord (CSS « tstat-* » dans styles_fichier_base.py).
"""
from itertools import count
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.data_tables import show_df

COULEUR_MONTANT, COULEUR_MARGE = "#2a78d6", "#eb6834"   # bleu CA / Achats HT, orange marge brute
# Même ordre de couleurs que les « Indicateurs Analytiques » du Tableau de Bord (kc1 → kc4),
# pour chaque rangée de 4 cartes
STYLES_BASE = STYLES_ANALYSE = ["kc1", "kc2", "kc3", "kc4"]
SOUS_TEXTE_COULEUR = "#001219"   # comme la ligne sous les cartes analytiques du Tableau de Bord


def _dh(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:,.2f} DH"


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:,.1f} %"


def _periode_txt(p: dict) -> str:
    return (f"**Période** : du {p['date_from']} au {p['date_to']}  \n"
            f"**N-1** : du {p['date_from_n1']} au {p['date_to_n1']}")


class _Cartes:
    """Cartes KPI numérotées (clé unique par carte), avec une ligne d'information sous la valeur."""

    def __init__(self, key: str):
        self.key, self.n = key, count()

    def carte(self, col, style: str, label: str, value: str, help_txt: str, sous_texte: Optional[str] = None):
        with col:
            with st.container(border=True, key=f"tstat-{style}-{self.key}-{next(self.n)}"):
                st.metric(label, value, help=help_txt)
                if sous_texte:
                    st.html(f'<div style="color:{SOUS_TEXTE_COULEUR};font-size:0.85rem;margin-top:-10px;'
                            f'font-family:inherit;">{sous_texte}</div>')

    def ligne(self, styles: list, cartes: list):
        """`cartes` : liste de (label, valeur, aide, sous_texte) ; styles appliqués dans l'ordre."""
        for col, style, c in zip(st.columns(len(styles)), styles, cartes):
            self.carte(col, style, *c)


def _chart_mensuel(mensuel: list, libelle: str, avec_marge: bool) -> None:
    if not mensuel:
        return
    x = [f"{m['mois'][5:7]}-{m['mois'][:4]}" for m in mensuel]      # « 01-2026 »
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=[m["montant_ht"] for m in mensuel], name=libelle,
                         marker_color=COULEUR_MONTANT, marker_line_width=0,
                         hovertemplate="%{x} — " + libelle + " : %{y:,.2f} DH<extra></extra>"))
    if avec_marge:
        fig.add_trace(go.Bar(x=x, y=[m.get("marge") for m in mensuel], name="Marge brute",
                             marker_color=COULEUR_MARGE, marker_line_width=0,
                             hovertemplate="%{x} — Marge brute : %{y:,.2f} DH<extra></extra>"))
    titre = f"{libelle} et marge brute par mois (DH)" if avec_marge else f"{libelle} par mois (DH)"
    fig.update_layout(title=titre, barmode="group", bargap=0.3, height=340,
                      margin=dict(t=50, b=10, l=10, r=10), showlegend=avec_marge,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    fig.update_xaxes(type="category", showgrid=False)
    fig.update_yaxes(tickformat=",.0f", gridcolor="rgba(128,128,128,0.15)", zeroline=True,
                     zerolinecolor="rgba(128,128,128,0.4)")
    st.plotly_chart(fig, width="stretch", theme="streamlit")


def _table(rows: list, colonnes: dict, key: str) -> None:
    """Tableau à partir d'une liste de dicts ; `colonnes` = {clé API: libellé}, dans l'ordre d'affichage."""
    if not rows:
        st.caption("Aucune donnée sur la période.")
        return
    df = pd.DataFrame(rows)
    df = df[[c for c in colonnes if c in df.columns]].rename(columns=colonnes)
    show_df(df, key_suffix=key)


def _evo_txt(v: Optional[float]) -> Optional[str]:
    return None if v is None else f"{v:+,.1f} % vs N-1"


def render_client_stats(stats: dict, key: str) -> None:
    k, periode = stats["kpis"], _periode_txt(stats["periode"])
    cartes = _Cartes(key)

    st.markdown("##### Indicateurs de base")
    cartes.ligne(STYLES_BASE, [
        ("CA HT", _dh(k["montant_ht"]),
         f"**Formule** : Σ montants HT des factures de vente (avoirs déduits)  \n{periode}",
         _evo_txt(k["evolution_pct"])),
        ("Factures / Avoirs", f"{k['nb_factures']} / {k['nb_avoirs']}",
         f"**Factures** : documents de montant > 0 ; **avoirs** : montant < 0  \n{periode}",
         f"Avoirs : {_dh(k['montant_avoirs'])}"),
        ("Panier moyen", _dh(k["facture_moyenne"]), f"**Formule** : CA HT ÷ nombre de factures  \n{periode}", None),
        ("Encours", _dh(k["encours"]),
         "**Formule** : Σ (TTC − réglé) des factures dont le reste à payer est > 0  \n**Période** : tout l'historique",
         None),
    ])

    st.markdown("##### Indicateurs d'analyse")
    cartes.ligne(STYLES_ANALYSE, [
        ("Marge brute", _dh(k["marge_brute"]),
         "**Formule** : CA HT des lignes facturées − Σ (Quantité livrée × Coût unitaire)  \n"
         "**Coût unitaire** : prix de revient de la ligne ; à défaut le CMUP ; à défaut le prix d'achat de la fiche article  \n"
         f"{periode}", f"Taux de marge : {_pct(k['taux_marge_pct'])}"),
        ("Transformation des devis", _pct(k["taux_transformation_devis_pct"]) if k["nb_devis"] else "N/A",
         "**Formule** : Factures ÷ (Factures + Devis non transformés) × 100  \n"
         f"N/A s'il n'y a aucun devis sur la période  \n{periode}",
         f"{k['nb_factures']} factures, {k['nb_devis']} devis non transformés"),
        ("Dernière facture", k["derniere_facture"] or "—",
         "**Date** de la facture de vente la plus récente de ce client (tout l'historique)", None),
        ("Taux d'avoir", _pct(k["taux_avoir_pct"]),
         f"**Formule** : montant des avoirs ÷ montant des factures (hors avoirs) × 100  \n{periode}", None),
    ])

    _chart_mensuel(stats["mensuel"], "CA HT", avec_marge=True)

    col_a, col_f = st.columns(2)
    with col_a:
        st.markdown("**Top 10 articles achetés**")
        _table(stats["top_articles"], {"ar_ref": "Réf. Article", "designation": "Désignation", "qte": "Qté",
                                       "montant_ht": "CA HT", "pct": "% du CA"}, f"{key}_articles")
    with col_f:
        st.markdown("**Familles achetées**")
        _table(stats["familles"], {"famille": "Famille", "qte": "Qté", "montant_ht": "CA HT", "pct": "% du CA"},
               f"{key}_familles")
    st.markdown("**Commerciaux** (commercial porté par la facture)")
    _table(stats["commerciaux"], {"commercial": "Commercial", "montant_ht": "CA HT", "pct": "% du CA"}, f"{key}_commerciaux")


def render_fournisseur_stats(stats: dict, key: str) -> None:
    k, periode = stats["kpis"], _periode_txt(stats["periode"])
    cartes = _Cartes(key)

    st.markdown("##### Indicateurs de base")
    cartes.ligne(STYLES_BASE, [
        ("Achats HT", _dh(k["montant_ht"]),
         f"**Formule** : Σ montants HT des factures d'achat (avoirs fournisseurs déduits)  \n{periode}",
         _evo_txt(k["evolution_pct"])),
        ("Factures / Avoirs", f"{k['nb_factures']} / {k['nb_avoirs']}",
         f"**Factures** : documents de montant > 0 ; **avoirs** : montant < 0  \n{periode}",
         f"Bons de retour : {k['nb_bons_retour']}"),
        ("Facture moyenne", _dh(k["facture_moyenne"]), f"**Formule** : Achats HT ÷ nombre de factures  \n{periode}", None),
        ("Dettes", _dh(k["dettes"]),
         "**Formule** : Σ (TTC − réglé) des factures d'achat dont le reste à payer est > 0  \n**Période** : tout l'historique",
         "Tout l'historique"),
    ])

    st.markdown("##### Indicateurs d'analyse")
    cartes.ligne(STYLES_ANALYSE, [
        ("Part des achats", _pct(k["part_achats_pct"]),
         f"**Formule** : achats HT de ce fournisseur ÷ achats HT de tous les fournisseurs × 100  \n{periode}",
         f"Rang {k['rang']} sur {k['nb_fournisseurs_actifs']} fournisseurs" if k["rang"] else None),
        ("Délai de livraison", f"{k['delai_moyen_jours']:,.1f} j" if k["delai_moyen_jours"] is not None else "—",
         "**Formule** : moyenne de (date BL − date BC) sur les lignes livrées après la commande  \n"
         "Les autres lignes ont la même date de commande et de livraison (ex. facture directe)  \n" + periode,
         f"Sur {k['nb_lignes_bl_apres_bc']} / {k['nb_lignes_datees']} lignes datées"),
        ("Évolution des prix d'achat",
         f"{k['evolution_prix_ponderee_pct']:+,.2f} %" if k["evolution_prix_ponderee_pct"] is not None else "—",
         "**Formule** : par article, (dernier prix − premier prix) ÷ premier prix × 100, "
         "puis moyenne pondérée par les quantités achetées  \n"
         "**Prix** : montant HT ÷ quantité (remises incluses), factures uniquement  \n" + periode,
         f"Sur {k['nb_articles_prix_compares']} articles (achetés à 2 dates ou plus)"),
        ("Taux d'avoir", _pct(k["taux_avoir_pct"]),
         f"**Formule** : montant des avoirs ÷ montant des factures (hors avoirs) × 100  \n{periode}",
         f"Avoirs : {_dh(k['montant_avoirs'])}"),
    ])

    _chart_mensuel(stats["mensuel"], "Achats HT", avec_marge=False)

    colonnes_prix = {"ar_ref": "Réf. Article", "designation": "Désignation", "qte": "Qté",
                     "montant_ht": "Montant HT", "prix_moyen": "Prix moyen", "premier_prix": "Premier prix",
                     "dernier_prix": "Dernier prix", "evolution_prix_pct": "Évolution prix %"}
    st.markdown("**Top 10 articles achetés**")
    _table(stats["top_articles"], colonnes_prix, f"{key}_articles")

    s = stats["seuils"]
    st.markdown(f"**Articles à surveiller** — hausse de prix ≥ {s['hausse_prix_pct']:g} % sur la période, "
                f"ou autre fournisseur ≥ {s['ecart_fournisseur_pct']:g} % moins cher (prix moyen sur la période)")
    _table(stats["articles_a_surveiller"], {**colonnes_prix,
                                            "meilleur_prix_autre": "Meilleur prix autre fournisseur",
                                            "fournisseur_moins_cher": "Fournisseur le moins cher",
                                            "ecart_meilleur_prix_pct": "Écart vs meilleur prix %",
                                            "motif": "Motif"}, f"{key}_surveiller")
