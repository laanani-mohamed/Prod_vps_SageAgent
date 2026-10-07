"""
reporting/envoi.py — Envoi par email (compte Gmail) des rapports déposés dans storage_srv/rapport/.

Identifiants dans app/.env.mail (non versionné, cf. .gitignore « .env.* ») :
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=465
    SMTP_USER=<adresse>@gmail.com
    SMTP_PASSWORD=<mot de passe d'application Google, 16 caractères — pas le mot de passe du compte>

Le résultat de chaque envoi (envoyé / échec + erreur) est ajouté au .json du rapport, clé "envois".
"""
import json
import os
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import parseaddr

from dotenv import load_dotenv

ENV_MAIL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env.mail")

_TYPES_FICHIERS = {
    "pdf":   ("application", "pdf"),
    "excel": ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
}


def adresse_valide(adresse) -> bool:
    """Adresse email simple : texte@domaine.ext, sans nom affiché."""
    if not isinstance(adresse, str):
        return False
    _, addr = parseaddr(adresse)
    return addr == adresse and addr.count("@") == 1 and "." in addr.split("@")[1]


def _smtp_config() -> dict:
    load_dotenv(ENV_MAIL_PATH)
    cfg = {k: os.getenv(k) for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD")}
    manquants = [k for k, v in cfg.items() if not v]
    if manquants:
        raise RuntimeError(f"Envoi impossible : {', '.join(manquants)} non renseigné(s) dans {ENV_MAIL_PATH}")
    return cfg


def _message(expediteur: str, client: str, destinataire: str, json_paths: list) -> EmailMessage:
    details = []
    for path in json_paths:
        with open(path, "r", encoding="utf-8") as fh:
            details.append((path, json.load(fh)))

    msg = EmailMessage()
    msg["From"] = expediteur
    msg["To"] = destinataire
    msg["Subject"] = f"Rapports {client} du {date.today().strftime('%d/%m/%Y')}"

    lignes = [
        f"- {os.path.splitext(d['fichiers']['pdf'])[0]} : {d['titre']} — {d['sous_titre']} ({d['nb_lignes']} ligne(s))"
        for _, d in details
    ]
    msg.set_content(
        "Bonjour,\n\n"
        "Veuillez trouver ci-joint vos rapports (PDF et Excel) :\n\n" + "\n".join(lignes) + "\n\n"
        "Cordialement,\nIT-Board§\n"
    )

    for path, d in details:
        dossier = os.path.dirname(path)
        for type_fichier, (maintype, subtype) in _TYPES_FICHIERS.items():
            nom = d["fichiers"][type_fichier]
            with open(os.path.join(dossier, nom), "rb") as fh:
                msg.add_attachment(fh.read(), maintype=maintype, subtype=subtype, filename=nom)
    return msg


def _noter_envoi(json_paths: list, destinataire: str, erreur: str = None) -> None:
    """Ajoute le résultat de l'envoi à la clé "envois" de chaque .json."""
    envoi = {"destinataire": destinataire, "date": datetime.now().isoformat(timespec="seconds"),
             "statut": "échec" if erreur else "envoyé"}
    if erreur:
        envoi["erreur"] = erreur
    for path in json_paths:
        with open(path, "r", encoding="utf-8") as fh:
            detail = json.load(fh)
        detail.setdefault("envois", []).append(envoi)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(detail, fh, indent=4, ensure_ascii=False)
            fh.write("\n")


def envoyer_rapports(client: str, destinataire: str, json_paths: list) -> None:
    """Envoie à `destinataire` un seul email avec le PDF et l'Excel de chaque rapport (.json) de
    `json_paths`, et note le résultat dans chaque .json. Lève l'exception en cas d'échec."""
    try:
        cfg = _smtp_config()
        msg = _message(cfg["SMTP_USER"], client, destinataire, json_paths)
        with smtplib.SMTP_SSL(cfg["SMTP_HOST"], int(cfg["SMTP_PORT"]), timeout=60) as smtp:
            # Google affiche le mot de passe d'application par groupes de 4 : espaces ignorés
            smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"].replace(" ", ""))
            smtp.send_message(msg)
    except Exception as exc:
        _noter_envoi(json_paths, destinataire, erreur=str(exc))
        raise
    _noter_envoi(json_paths, destinataire)
