"""Page 5 — Journal d'accès à l'API (auth.audit_logs) : connexions, appels, erreurs, refus."""
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services import audit_reader

st.title("Accès API")


@st.cache_data(ttl=60)
def _options():
    return audit_reader.filter_options()


@st.cache_data(ttl=60)
def _data(date_from, date_to, client, action, status):
    return (audit_reader.counts_by_action(date_from, date_to, client),
            audit_reader.daily_counts(date_from, date_to, client),
            audit_reader.events(date_from, date_to, client, action, status))


try:
    opts = _options()
except Exception as e:
    st.error(f"Journal d'audit inaccessible (auth.audit_logs) : {e}")
    st.stop()

today = date.today()
f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
with f1:
    periode = st.date_input("Période (UTC)", value=(today - timedelta(days=6), today), max_value=today)
with f2:
    client = st.selectbox("Client", ["Tous"] + opts["clients"])
with f3:
    action = st.selectbox("Action", ["Toutes"] + opts["actions"])
with f4:
    status = st.selectbox("Statut", ["Tous"] + opts["statuts"])
if not isinstance(periode, tuple) or len(periode) != 2:
    st.info("Choisissez une date de début et une date de fin.")
    st.stop()
date_from, date_to = periode

counts, daily, events = _data(date_from, date_to, None if client == "Tous" else client,
                              None if action == "Toutes" else action, None if status == "Tous" else status)


def _nb(act, stat=None):
    return sum(c["nb"] for c in counts if c["action"] == act and (stat is None or c["status"] == stat))


m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Appels API réussis", _nb("API_CALL", "SUCCESS"))
m2.metric("Erreurs API", _nb("API_ERROR"))
m3.metric("Connexions réussies", _nb("LOGIN", "SUCCESS"))
m4.metric("Connexions échouées", _nb("LOGIN", "FAILED"))
m5.metric("Accès refusés", _nb("ACCESS_DENIED"))
reuse = _nb("REFRESH_REUSE")
if reuse:
    st.warning(f"⚠️ {reuse} réutilisation(s) d'un jeton de rafraîchissement révoqué sur la période : "
               "signe possible de vol de jeton, à vérifier dans le détail ci-dessous (action REFRESH_REUSE).")

# Incidents par jour : même unité (nombre d'événements), un seul axe ; les appels réussis
# (volume ~100× supérieur) sont donnés dans le tableau pour ne pas écraser le graphique.
if daily:
    dfd = pd.DataFrame(daily)
    jours = pd.date_range(date_from, date_to, freq="D")
    dfd = dfd.set_index(pd.to_datetime(dfd["jour"])).drop(columns="jour").reindex(jours, fill_value=0)
    fig = go.Figure()
    for col, nom, couleur in (("erreurs_api", "Erreurs API", "#d03b3b"),
                              ("connexions_echouees", "Connexions échouées", "#ec835a"),
                              ("acces_refuses", "Accès refusés", "#4a3aa7")):
        fig.add_trace(go.Bar(x=dfd.index, y=dfd[col], name=nom, marker_color=couleur, marker_line_width=0,
                             hovertemplate="%{x|%d/%m/%Y} — " + nom + " : %{y}<extra></extra>"))
    fig.update_layout(title="Incidents par jour", barmode="stack", bargap=0.35, height=320,
                      margin=dict(t=50, b=10, l=10, r=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    fig.update_xaxes(tickformat="%d/%m", showgrid=False)
    fig.update_yaxes(rangemode="tozero", tickformat="d", gridcolor="rgba(128,128,128,0.15)", zeroline=False)
    st.plotly_chart(fig, width="stretch", theme="streamlit")
    st.dataframe(dfd.rename_axis("Jour").reset_index().rename(columns={
        "appels_ok": "Appels réussis", "erreurs_api": "Erreurs API",
        "connexions_echouees": "Connexions échouées", "acces_refuses": "Accès refusés",
    }).assign(Jour=lambda d: d["Jour"].dt.strftime("%Y-%m-%d")), width="stretch", hide_index=True)

st.markdown(f"#### Événements ({len(events)} affichés, 1 000 au maximum, les plus récents d'abord)")
if events:
    dfe = pd.DataFrame(events)
    dfe["timestamp"] = pd.to_datetime(dfe["timestamp"], utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(dfe.rename(columns={
        "timestamp": "Date (UTC)", "username": "Utilisateur", "action": "Action", "endpoint": "Endpoint",
        "ip_address": "IP", "client_schema": "Client", "status": "Statut", "details": "Détail",
    }), width="stretch", hide_index=True)
else:
    st.info("Aucun événement pour ces filtres.")
