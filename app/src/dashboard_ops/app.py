"""
# Stopper
pkill -f "streamlit run src/dashboard_ops"

# Relancer (depuis /opt/SageAgent/app)
cd /opt/SageAgent/app
nohup .venv/bin/streamlit run src/dashboard_ops/app.py --server.port 8585 --server.headless true > /tmp/dashboard_ops.log 2>&1 &

dashboard_ops/app.py — Point d'entrée de l'app Streamlit d'observabilité ETL.
App séparée de dashboard_bi (ITBORD) : outil interne de debug, pas destiné aux clients.

Lancer avec : streamlit run src/dashboard_ops/app.py --server.port 8585
pkill -f "streamlit run src/dashboard_ops" 2>/dev/null; echo "pkill done"
"""
import sys
import os

_DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))          # .../src/dashboard_ops
_SRC_DIR = os.path.dirname(_DASHBOARD_DIR)                            # .../src
_APP_ROOT = os.path.dirname(_SRC_DIR)                                 # .../app

# Ordre important : DASHBOARD_DIR en dernier inséré donc en tête de sys.path,
# pour que les imports locaux (ops_config, auth, services.*) priment sur tout
# module de même nom éventuellement présent plus haut dans l'arborescence.
for path in (_APP_ROOT, _SRC_DIR, _DASHBOARD_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import streamlit as st

from ops_config import PAGE_TITLE
from auth import require_auth, logout_button

st.set_page_config(page_title=PAGE_TITLE, layout="wide", initial_sidebar_state="expanded")

require_auth()
logout_button()

pages = {
    "Observabilité": [
        st.Page("pages/1_Runs.py", title="Historique des runs"),
        st.Page("pages/2_Investigation.py", title="Investigation"),
    ],
    "Administration": [
        st.Page("pages/3_Onboarding.py", title="Onboarding client"),
    ],
}

pg = st.navigation(pages)
pg.run()
