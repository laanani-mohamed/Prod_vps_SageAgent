"""
investigation_view.py — Rendu partagé de l'investigation d'un run en échec.
Utilisé à la fois inline (page 'Historique des runs') et sur la page dédiée
'Investigation' (accès direct/manuel).
"""
import pandas as pd
import streamlit as st

from etl.reporting.investigate_error import build_investigation_report


def _rows_table(rows, highlight_col=None):
    """Construit un DataFrame avec une colonne du tableau par champ Sage (pas de bloc texte brut)."""
    if not rows:
        return None
    df = pd.DataFrame(rows)
    if highlight_col and highlight_col in df.columns:
        return df.style.set_properties(
            subset=[highlight_col], **{"background-color": "#fee2e2", "font-weight": "600"}
        )
    return df


def render_investigation(client: str, date_str: str, run_summary: dict) -> None:
    """Affiche l'investigation complète d'un run en échec (aucune navigation de page)."""
    st.markdown(f"**Client :** {client} &nbsp;|&nbsp; **Run :** `{run_summary['run_id']}`")

    error_code = run_summary.get("error_code")
    fichier = run_summary.get("fichier")
    table = run_summary.get("table")

    h1, h2, h3 = st.columns(3)
    h1.metric("Fichier concerné", fichier or "—")
    h2.metric("Table", table or "—")
    h3.metric("Error code", error_code or "—")

    if not error_code:
        st.warning("Aucun error_code identifié pour ce run — impossible d'investiguer automatiquement.")
        with st.expander("Log brut du run"):
            st.json(run_summary.get("raw_lines", []))
        return

    with st.spinner("Analyse du fichier archivé en cours..."):
        report = build_investigation_report(client, date_str, run_summary)

    if report.get("error"):
        st.error(report["error"])
        with st.expander("Log brut du run"):
            st.json(run_summary.get("raw_lines", []))
        return

    st.caption(
        f"📄 Fichier analysé : `{report['filepath']}` — ⚠️ ce fichier a déjà été nettoyé automatiquement "
        "avant l'échec (virgule→point, dates JJ/MM/AAAA→ISO) : ce n'est pas l'exact fichier brut déposé par le client."
    )

    details = report.get("details", {})
    if details.get("error"):
        st.error(details["error"])
        return

    if error_code == "SCHEMA_COLUMN_COUNT_MISMATCH":
        st.markdown("### Comptage de colonnes")
        c1, c2 = st.columns(2)
        c1.metric("Colonnes attendues", details.get("expected"))
        c2.metric("Lignes en erreur", details.get("total_bad_rows"))

        st.markdown("#### ✅ Lignes propres (exemple)")
        clean_df = _rows_table(details.get("clean_sample", []))
        if clean_df is not None:
            st.dataframe(clean_df, width="stretch", hide_index=True)
        else:
            st.caption("Aucune ligne propre trouvée dans ce fichier.")

        st.markdown(f"#### ❌ Lignes fautives ({details.get('total_bad_rows')} au total, {len(details.get('bad_rows', []))} affichées)")
        bad_df = _rows_table(details.get("bad_rows", []))
        if bad_df is not None:
            st.dataframe(bad_df, width="stretch", hide_index=True)

    elif error_code and (error_code.startswith("TYPE_MISMATCH_COL_") or error_code.startswith("NOT_NULL_VIOLATION_COL_")):
        is_type_error = error_code.startswith("TYPE_MISMATCH_COL_")
        st.markdown("### " + ("Type de colonne incompatible" if is_type_error else "Contrainte NOT NULL violée"))

        c1, c2, c3 = st.columns(3)
        c1.metric("Colonne", details.get("colonne") or "—")
        c2.metric("Position", details.get("col_position"))
        if is_type_error:
            c3.metric("Type attendu", details.get("type_attendu") or "—")
        else:
            c3.metric("Lignes en erreur", details.get("total_bad_rows"))

        highlight_col = details.get("colonne")

        st.markdown("#### ✅ Lignes propres (avant les lignes fautives)")
        clean_df = _rows_table(details.get("clean_sample", []), highlight_col)
        if clean_df is not None:
            st.dataframe(clean_df, width="stretch", hide_index=True)
        else:
            st.caption("Aucune ligne propre trouvée pour cette colonne dans ce fichier.")

        st.markdown(f"#### ❌ Lignes fautives ({details.get('total_bad_rows')} au total, {len(details.get('bad_rows', []))} affichées)")
        bad_df = _rows_table(details.get("bad_rows", []), highlight_col)
        if bad_df is not None:
            st.dataframe(bad_df, width="stretch", hide_index=True)

    else:
        st.info("Type d'erreur non pris en charge par l'investigation automatique.")

    with st.expander("Log brut complet du run"):
        st.json(run_summary.get("raw_lines", []))
