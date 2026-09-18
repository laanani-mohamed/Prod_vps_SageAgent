"""Page 1 — Historique des runs par client/date."""
import streamlit as st
import pandas as pd

from services.log_reader import list_clients, list_dates, read_log_lines
from services.run_status import list_runs_for_day
from components.status_badge import status_html

st.title("Historique des uploads")

clients = list_clients()
if not clients:
    st.warning("Aucun client trouvé dans les logs (app/logs/etl.log/).")
    st.stop()

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    client = st.selectbox("Client", clients)

dates = list_dates(client)
with col2:
    date_str = st.selectbox("Date", dates) if dates else None

with col3:
    status_filter = st.selectbox("Statut", ["Tous", "SUCCESS", "FAILED", "RUNNING", "UNKNOWN"])

if not date_str:
    st.info("Aucun log disponible pour ce client.")
    st.stop()


@st.cache_data(ttl=30)
def _load_runs(client: str, date_str: str):
    lines = read_log_lines(client, date_str)
    return list_runs_for_day(client, date_str, lines)


runs = _load_runs(client, date_str)

if status_filter != "Tous":
    runs = [r for r in runs if r["status"] == status_filter]

total = len(runs)
n_success = sum(1 for r in runs if r["status"] == "SUCCESS")
n_failed = sum(1 for r in runs if r["status"] == "FAILED")
n_running = sum(1 for r in runs if r["status"] == "RUNNING")
fail_rate = f"{(n_failed / total * 100):.0f}%" if total else "—"

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total runs", total)
m2.metric("Succès", n_success)
m3.metric("Échecs", n_failed)
m4.metric("Taux d'échec", fail_rate)

if not runs:
    st.info("Aucun run pour ces filtres.")
    st.stop()

df = pd.DataFrame([
    {
        "Heure": r["started_at"],
        "Statut": r["status"],
        "Table / fichier": r.get("fichier") or r.get("table") or "—",
        "Error code": r.get("error_code") or "—",
        "run_id": r["run_id"],
    }
    for r in runs
])

st.markdown("#### Runs")
event = st.dataframe(
    df.drop(columns=["run_id"]),
    width='stretch',
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
)

selected_idx = event.selection.rows if event and event.selection else []
selected_run = None
if selected_idx:
    selected_run = runs[selected_idx[0]]
    st.markdown(f"**Run sélectionné :** `{selected_run['run_id']}` — {status_html(selected_run['status'])}", unsafe_allow_html=True)

    if selected_run["status"] == "FAILED":
        if st.button("🔍 Investiguer ce run", type="primary"):
            st.session_state.investigate_client = client
            st.session_state.investigate_date = date_str
            st.session_state.investigate_run = selected_run
            st.switch_page("pages/2_Investigation.py")
    else:
        st.caption("Ce run n'est pas en échec — rien à investiguer.")

    with st.expander("Log brut de ce run"):
        st.json(selected_run["raw_lines"])
