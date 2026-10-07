import os
import sys

import pandas as pd
import streamlit as st

from services.bi_service import get_last_update
from core.formatters import format_datetime_minute

# Les exports PDF/Excel sont partagés avec la génération planifiée : ils vivent dans src/reporting/
_SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC_ROOT not in sys.path:
    sys.path.append(_SRC_ROOT)

from reporting import exports as _exports  # noqa: E402  (import après ajustement de sys.path)
from reporting.exports import export_df_to_excel, export_sections_to_excel  # noqa: E402,F401


def _derniere_maj_text() -> str:
    """Texte 'Derniere mise a jour: JJ/MM/AAAA HH:MM' pour le client courant,
    ou chaîne vide si le client/l'horodatage n'est pas disponible."""
    client_schema = st.session_state.get("client_schema", "")
    if not client_schema:
        return ""
    try:
        last_update = get_last_update(client_schema)
    except Exception:
        return ""
    return f"Derniere mise a jour: {format_datetime_minute(last_update)}"


def export_df_to_pdf(df: pd.DataFrame, title: str, subtitle: str = "", recap_rows: int = 0) -> bytes:
    """reporting.exports.export_df_to_pdf avec la date de dernière mise à jour du client en session."""
    return _exports.export_df_to_pdf(df, title, subtitle, recap_rows, derniere_maj=_derniere_maj_text())


def export_visite_to_pdf(sections: list, title: str, subtitle: str = "") -> bytes:
    """reporting.exports.export_visite_to_pdf avec la date de dernière mise à jour du client en session."""
    return _exports.export_visite_to_pdf(sections, title, subtitle, derniere_maj=_derniere_maj_text())
