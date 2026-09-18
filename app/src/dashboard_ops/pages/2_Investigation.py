"""Page 2 — Investigation d'un fichier archivé en échec (accès direct/manuel).
Depuis la page 'Historique des runs', l'investigation s'affiche désormais inline
sur place plutôt que de naviguer ici — cette page reste utile pour un accès direct
(lien, sélection manuelle) sans repasser par la liste des runs.
"""
import streamlit as st

from services.log_reader import list_clients, list_dates, read_log_lines
from services.run_status import list_runs_for_day
from components.investigation_view import render_investigation

st.title("Investigation d'un échec")

client = st.session_state.get("investigate_client")
date_str = st.session_state.get("investigate_date")
run_summary = st.session_state.get("investigate_run")

if not run_summary:
    st.info("Sélection manuelle (aucun run transmis depuis la page 'Historique des runs').")
    clients = list_clients()
    if not clients:
        st.warning("Aucun client trouvé.")
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        client = st.selectbox("Client", clients)
    dates = list_dates(client)
    with c2:
        date_str = st.selectbox("Date", dates) if dates else None

    if not date_str:
        st.stop()

    runs = list_runs_for_day(client, date_str, read_log_lines(client, date_str))
    failed_runs = [r for r in runs if r["status"] == "FAILED"]
    if not failed_runs:
        st.info("Aucun run en échec pour ce client/cette date.")
        st.stop()

    options = {f"{r['started_at']} — {r.get('error_code') or '?'} — {r.get('fichier') or ''}": r for r in failed_runs}
    choice = st.selectbox("Run en échec", list(options.keys()))
    run_summary = options[choice]

render_investigation(client, date_str, run_summary)
