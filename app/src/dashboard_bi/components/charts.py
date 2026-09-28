"""
Dash/components/charts.py
Graphiques Plotly réutilisables pour le dashboard.
"""
import plotly.graph_objects as go
import streamlit as st
from typing import List, Dict, Any

def render_ca_evolution_chart(ca_monthly: List[Dict[str, Any]], height: int = 300) -> None:
    """Graphique bar : évolution du CA mensuel."""
    if not ca_monthly:
        st.info("Aucune donnée d'évolution CA disponible.")
        return

    mois = [r.get("mois", "") for r in ca_monthly]
    ca   = [r.get("ca", 0) for r in ca_monthly]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=mois,
        y=ca,
        name="CA HT",
        marker_color="#10b981",
        text=[f"{v:,.0f}" for v in ca],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>CA HT : %{y:,.0f} DH<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Évolution du Chiffre d'Affaires", font=dict(size=14, color="#0F172A", family="Outfit")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#475569", family="Outfit"),
        height=height,
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(showgrid=False, tickfont=dict(color="#64748b")),
        yaxis=dict(showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color="#64748b"), tickformat=",.0f"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

def render_top_clients_chart(data: List[Dict[str, Any]], height: int = 300) -> None:
    """Graphique bar horizontal : Top clients par CA."""
    if not data:
        st.info("Aucune donnée Top Clients.")
        return

    labels = [r.get("ct_intitule") or r.get("do_tiers", "?") for r in data[:10]]
    values = [r.get("ca_ht", 0) for r in data[:10]]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color="#8b5cf6",
        text=[f"{v:,.0f} DH" for v in values],
        textposition="inside",
        hovertemplate="<b>%{y}</b><br>CA : %{x:,.0f} DH<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Top Clients par CA", font=dict(size=14, color="#0F172A", family="Outfit")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#475569", family="Outfit"),
        height=height,
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(showgrid=True, gridcolor="#E2E8F0", tickformat=",.0f", tickfont=dict(color="#64748b")),
        yaxis=dict(autorange="reversed", tickfont=dict(color="#64748b")),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

def render_top_articles_chart(data: List[Dict[str, Any]], height: int = 300) -> None:
    """Graphique bar : Top articles vendus par quantité."""
    if not data:
        st.info("Aucune donnée Top Articles.")
        return

    labels = [r.get("ar_design") or r.get("ar_ref", "?") for r in data[:10]]
    values = [r.get("qte_vendue", 0) for r in data[:10]]

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color="#f59e0b",
        hovertemplate="<b>%{x}</b><br>Qté : %{y:,.1f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Top Articles par Quantité Vendue", font=dict(size=14, color="#0F172A", family="Outfit")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#475569", family="Outfit"),
        height=height,
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(showgrid=False, tickangle=-30, tickfont=dict(color="#64748b")),
        yaxis=dict(showgrid=True, gridcolor="#E2E8F0", tickfont=dict(color="#64748b")),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

def render_line_chart(data: List[Dict[str, Any]], title: str, series_name: str, color: str = "#10b981", height: int = 300) -> None:
    """Rend un graphique en ligne natif Plotly/Streamlit."""
    if not data:
        st.info(f"Aucune donnée disponible pour : {title}")
        return

    mois = [r.get("mois", "") for r in data]
    values = [r.get("value", 0.0) for r in data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=mois,
        y=values,
        mode="lines+markers",
        name=series_name,
        line=dict(color=color, width=3),
        hovertemplate="<b>%{x}</b><br>" + series_name + " : %{y:,.0f} DH<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#0F172A")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#475569"),
        height=height,
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#E2E8F0", tickformat=",.0f"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

def render_product_evolution_chart(evolution: list, height: int = 320) -> None:
    """Graphique combiné (barres CA + ligne Marge Brute)."""
    if not evolution:
        st.info("Aucune donnée d'évolution disponible pour cet article.")
        return

    mois  = [r.get("mois", "") for r in evolution]
    ca    = [r.get("ca", 0.0) for r in evolution]
    marge = [r.get("marge", 0.0) for r in evolution]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=mois,
        y=ca,
        name="CA HT",
        marker_color="#6366f1",
        opacity=0.85,
        hovertemplate="<b>%{x}</b><br>CA HT : %{y:,.0f} DH<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=mois,
        y=marge,
        name="Marge Brute",
        mode="lines+markers",
        line=dict(color="#10b981", width=3),
        marker=dict(size=7, color="#10b981"),
        hovertemplate="<b>%{x}</b><br>Marge : %{y:,.0f} DH<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Évolution Mensuelle — CA HT & Marge Brute", font=dict(size=14, color="#0F172A", family="Outfit")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#475569", family="Outfit"),
        height=height,
        margin=dict(l=0, r=0, t=45, b=0),
        xaxis=dict(showgrid=False, tickfont=dict(color="#64748b")),
        yaxis=dict(showgrid=True, gridcolor="#E2E8F0", tickformat=",.0f", tickfont=dict(color="#64748b")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=12)),
        barmode="overlay",
    )
    st.plotly_chart(fig, use_container_width=True)
