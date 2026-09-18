"""
error_report.py — Rapport d'erreur lisible déposé dans le dossier d'upload du client.

En complément des logs internes (destinés au support), ce module écrit un fichier
texte en français simple directement dans storage_srv/upload/<client>/ à chaque
échec de validation ou d'ingestion, pour que le client comprenne sans avoir à
consulter les logs.
"""

import os
import time
import logging
from datetime import datetime

from config.etl_config import ERROR_REPORT_PREFIX, ERROR_REPORT_RETENTION_DAYS, error_report_filename

logger = logging.getLogger("etl.reporting.error_report")


def _format_detail_lines(detail: dict) -> str:
    lines = []
    if detail.get("fichier"):
        lines.append(f"Fichier concerné : {detail['fichier']}")
    if detail.get("ligne") is not None:
        lines.append(f"Ligne concernée   : {detail['ligne']}")
    if detail.get("colonne"):
        col_pos = detail.get("col_position")
        suffixe = f" (colonne n°{col_pos})" if col_pos else ""
        lines.append(f"Colonne concernée : {detail['colonne']}{suffixe}")
    return "\n".join(lines)


def _build_message(detail: dict, run_id: str) -> str:
    error_code = detail.get("error_code", "UNKNOWN_ERROR")
    date_str = datetime.now().strftime("%d/%m/%Y")
    context_lines = _format_detail_lines(detail)

    if error_code == "INVALID_INPUT_FILES":
        probleme = (
            "les fichiers déposés ne correspondent pas à ceux attendus.\n"
            f"Fichiers attendus : {', '.join(detail.get('fichiers_attendus', []))}\n"
            f"Fichiers trouvés  : {', '.join(detail.get('fichiers_trouves', []))}"
        )
        actions = "Vérifiez les noms exacts des fichiers à déposer (respecter la casse et l'extension), puis redéposez l'ensemble des fichiers dans ce dossier."

    elif error_code == "EMPTY_FILES":
        probleme = f"le(s) fichier(s) suivant(s) sont vides (0 ligne de données) : {', '.join(detail.get('fichiers', []))}"
        actions = "Vérifiez que l'export Sage s'est bien déroulé jusqu'au bout, régénérez-le, puis redéposez l'ensemble des fichiers."

    elif error_code == "SCHEMA_COLUMN_COUNT_MISMATCH":
        probleme = f"cette ligne contient un nombre de colonnes différent de celui attendu ({detail.get('valeur_trouvee', '?')} au lieu de {detail.get('attendu', '?')})."
        actions = "Vérifiez que l'export Sage n'a pas été modifié ou tronqué. Contactez votre support technique si le problème persiste."

    elif error_code.startswith("TYPE_MISMATCH_COL_"):
        probleme = (
            f"la valeur \"{detail.get('valeur_trouvee', '?')}\" trouvée à cet endroit "
            f"n'est pas valide pour le type attendu ({detail.get('attendu', '?')})."
        )
        actions = "Vérifiez et corrigez cette valeur dans votre export Sage, ou contactez votre support technique."

    elif error_code.startswith("NOT_NULL_VIOLATION_COL_"):
        probleme = "cette colonne est obligatoire mais est vide sur cette ligne."
        actions = "Complétez la valeur manquante dans votre export Sage, ou contactez votre support technique."

    elif error_code == "SCHEMA_NOT_FOUND":
        probleme = "une erreur de configuration interne empêche de traiter votre import."
        actions = "Aucune action de votre part n'est nécessaire sur les fichiers. Contactez votre support technique."

    else:
        probleme = "une erreur technique est survenue lors du traitement de votre import."
        actions = "Contactez votre support technique en mentionnant la référence ci-dessous."

    parts = [
        "Bonjour,",
        "",
        f"L'import de vos fichiers du {date_str} n'a pas pu être finalisé.",
        "",
    ]
    if context_lines:
        parts.append(context_lines)
        parts.append("")
    parts.append(f"Problème : {probleme}")
    parts.append("")
    parts.append("Que faire :")
    parts.append(f"  {actions}")
    parts.append("")
    parts.append(f"Si le problème persiste, contactez votre support technique en mentionnant la référence : {run_id}")
    parts.append("")
    parts.append("---")
    parts.append("Détail technique (pour le support) :")
    parts.append(f"error_code: {error_code}")
    if detail.get("phase"):
        parts.append(f"phase: {detail['phase']}")
    if detail.get("table"):
        parts.append(f"table: {detail['table']}")
    parts.append(f"run_id: {run_id}")

    return "\n".join(parts) + "\n"


def write_error_report(folder_path: str, client_schema: str, run_id: str, detail: dict) -> None:
    """
    Écrit un rapport d'erreur lisible dans le dossier d'upload d'origine du client.
    N'échoue jamais le pipeline : toute erreur d'écriture est simplement loguée.
    """
    if not detail:
        detail = {"error_code": "UNKNOWN_ERROR"}

    report_path = os.path.join(folder_path, error_report_filename())
    try:
        message = _build_message(detail, run_id)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(message)
        logger.info(
            f"Rapport d'erreur écrit : {report_path}",
            extra={"run_id": run_id, "client": client_schema, "path": report_path, "step": "error_report_written"},
        )
    except OSError as e:
        logger.warning(
            f"Impossible d'écrire le rapport d'erreur dans {folder_path} : {e}",
            extra={"run_id": run_id, "client": client_schema, "path": folder_path, "step": "error_report_failed"},
        )


def purge_old_error_reports(folder_path: str) -> None:
    """Supprime les rapports d'erreur plus vieux que ERROR_REPORT_RETENTION_DAYS."""
    cutoff = time.time() - ERROR_REPORT_RETENTION_DAYS * 86400
    try:
        for filename in os.listdir(folder_path):
            if not filename.startswith(ERROR_REPORT_PREFIX):
                continue
            fpath = os.path.join(folder_path, filename)
            if os.path.isfile(fpath) and os.stat(fpath).st_mtime < cutoff:
                os.remove(fpath)
    except OSError as e:
        logger.warning(f"Erreur lors de la purge des rapports d'erreur de {folder_path} : {e}")
