"""Page 0 — Synthèse des uploads par jour (succès, échecs, taille déposée), tous clients ou un seul."""
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from services.log_reader import list_clients
from services.run_volumes import daily_summary
from components.formatting import fmt_taille

# Couleurs de statut (réservées : succès / échec), toujours accompagnées d'un libellé
COULEUR_SUCCES, COULEUR_ECHEC, COULEUR_TAILLE = "#0ca30c", "#d03b3b", "#2a78d6"

st.title("Synthèse des uploads")

col_client, col_periode, col_dates = st.columns([1, 1, 2])
with col_client:
    client = st.selectbox("Client", ["Tous"] + list_clients())
with col_periode:
    periode = st.selectbox("Période", ["7 derniers jours", "30 derniers jours", "90 derniers jours", "Personnalisée"], index=1)
aujourd_hui = date.today()
if periode == "Personnalisée":
    with col_dates:
        choix = st.date_input("Du / au", value=(aujourd_hui - timedelta(days=29), aujourd_hui), max_value=aujourd_hui)
    if not isinstance(choix, tuple) or len(choix) != 2:
        st.info("Choisissez une date de début et une date de fin.")
        st.stop()
    date_from, date_to = choix
else:
    date_from, date_to = aujourd_hui - timedelta(days=int(periode.split()[0]) - 1), aujourd_hui


@st.cache_data(ttl=60)
def _load(date_from: str, date_to: str, client):
    return daily_summary(date_from, date_to, client)


rows = _load(date_from.isoformat(), date_to.isoformat(), None if client == "Tous" else client)
if not rows:
    st.info("Aucun upload sur cette période.")
    st.stop()

df = pd.DataFrame(rows)
total_succes, total_echecs = int(df["succes"].sum()), int(df["echecs"].sum())
total_runs = total_succes + total_echecs + int(df["en_cours"].sum())
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Uploads", total_runs)
m2.metric("✅ Succès", total_succes)
m3.metric("❌ Échecs", total_echecs)
m4.metric("Taux de succès", f"{total_succes / total_runs * 100:.0f} %" if total_runs else "—")
m5.metric("Volume déposé", fmt_taille(int(df["taille"].sum())))

# Tous les jours de la période, y compris ceux sans upload (0), additionnés sur les clients affichés
jours = pd.date_range(date_from, date_to, freq="D").strftime("%Y-%m-%d")
par_jour = df.groupby("date")[["succes", "echecs", "taille"]].sum().reindex(jours, fill_value=0)
x = pd.to_datetime(par_jour.index)
taille_mo = par_jour["taille"] / 1e6

# Deux panneaux sur le même axe des jours (pas de double axe Y : comptes et Mo ont des échelles sans rapport)
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12, row_heights=[0.6, 0.4],
                    subplot_titles=("Uploads par jour", "Taille déposée par jour (Mo)"))
fig.add_trace(go.Bar(x=x, y=par_jour["succes"], name="Succès", marker_color=COULEUR_SUCCES,
                     hovertemplate="%{x|%d/%m/%Y} — Succès : %{y}<extra></extra>"), row=1, col=1)
fig.add_trace(go.Bar(x=x, y=par_jour["echecs"], name="Échecs", marker_color=COULEUR_ECHEC,
                     hovertemplate="%{x|%d/%m/%Y} — Échecs : %{y}<extra></extra>"), row=1, col=1)
fig.add_trace(go.Bar(x=x, y=taille_mo, name="Taille (Mo)", marker_color=COULEUR_TAILLE, showlegend=False,
                     hovertemplate="%{x|%d/%m/%Y} — %{y:,.1f} Mo<extra></extra>"), row=2, col=1)
fig.update_layout(barmode="stack", bargap=0.35, height=520, margin=dict(t=40, b=10, l=10, r=10),
                  legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="left", x=0),
                  hovermode="closest")
fig.update_traces(marker_line_width=0)
fig.update_xaxes(tickformat="%d/%m", showgrid=False)
fig.update_yaxes(rangemode="tozero", gridcolor="rgba(128,128,128,0.15)", zeroline=False)
fig.update_yaxes(tickformat="d", row=1, col=1)
st.plotly_chart(fig, width="stretch", theme="streamlit")

st.markdown("#### Détail par jour" + ("" if client == "Tous" else f" — {client}"))
detail = df.sort_values(["date", "client"], ascending=[False, True]).rename(columns={
    "date": "Date", "client": "Client", "succes": "Succès", "echecs": "Échecs", "en_cours": "En cours",
})
detail["Taille déposée"] = detail.pop("taille").map(fmt_taille)
st.dataframe(detail, width="stretch", hide_index=True)
