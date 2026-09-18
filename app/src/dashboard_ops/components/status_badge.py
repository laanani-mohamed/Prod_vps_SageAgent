"""status_badge.py — Badge coloré pour le statut d'un run."""
import streamlit as st

_STYLES = {
    "SUCCESS": ("#16a34a", "#dcfce7", "✅ SUCCESS"),
    "FAILED":  ("#dc2626", "#fee2e2", "❌ FAILED"),
    "RUNNING": ("#2563eb", "#dbeafe", "⏳ RUNNING"),
    "UNKNOWN": ("#6b7280", "#f3f4f6", "❔ UNKNOWN"),
}


def status_html(status: str) -> str:
    color, bg, label = _STYLES.get(status, _STYLES["UNKNOWN"])
    return (
        f'<span style="background:{bg};color:{color};padding:2px 10px;'
        f'border-radius:12px;font-weight:600;font-size:0.85rem;">{label}</span>'
    )


def render_status_badge(status: str) -> None:
    st.markdown(status_html(status), unsafe_allow_html=True)
