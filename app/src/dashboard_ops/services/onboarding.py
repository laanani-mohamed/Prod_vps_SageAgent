"""
onboarding.py — Lecture/écriture du registre clients (auth.json) et provisioning SFTP.
Logique métier pure (pas de Streamlit) : la page appelante gère l'affichage.
"""

import json
import os
import subprocess
import sys
from typing import Dict, List, Tuple

_SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))            # .../src/dashboard_ops/services
_DASHBOARD_DIR = os.path.dirname(_SERVICES_DIR)                       # .../src/dashboard_ops
_SRC_DIR = os.path.dirname(_DASHBOARD_DIR)                            # .../src
_APP_ROOT = os.path.dirname(_SRC_DIR)                                 # .../app
_REPO_ROOT = os.path.dirname(_APP_ROOT)                               # racine du dépôt

if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from utils.auth.create_user import create_api_user  # noqa: E402  (import après ajustement de sys.path)

AUTH_JSON_PATH = os.path.join(_REPO_ROOT, "data_Client", "reference", "auth.json")
SFTP_ONBOARD_SCRIPT = os.path.join(_APP_ROOT, "utils", "client_sftp", "sftp_onboard.sh")
SFTP_UPLOAD_ROOT = "/var/sftp/upload"


def read_clients_registry() -> List[Dict]:
    """Lit auth.json et retourne une liste de dicts (une entrée par client, clé incluse)."""
    if not os.path.isfile(AUTH_JSON_PATH):
        return []
    with open(AUTH_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [{"key": key, **infos} for key, infos in data.items()]


def is_sftp_provisioned(name: str) -> bool:
    """Teste l'existence du dossier SFTP du client, en essayant plusieurs casses
    (des incohérences MAJ/min existent déjà sur ce serveur — voir docs)."""
    for candidate in {name, name.upper(), name.lower()}:
        if os.path.isdir(os.path.join(SFTP_UPLOAD_ROOT, candidate)):
            return True
    return False


def next_available_port(registry: List[Dict], base: int = 8506) -> int:
    """Propose le prochain port libre après le plus grand port déjà attribué dans le registre."""
    used = [int(entry["port"]) for entry in registry if str(entry.get("port", "")).isdigit()]
    return max(used) + 1 if used else base


def provision_sftp(client_name: str, password: str) -> Tuple[bool, str]:
    """
    Exécute sftp_onboard.sh via sudo (règle sudoers restreinte à ce script, voir
    service/sudoers-sftp-onboard). Retourne (succès, sortie combinée stdout+stderr).
    """
    result = subprocess.run(
        ["sudo", f"SFTP_PASSWORD={password}", SFTP_ONBOARD_SCRIPT, client_name],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def create_db_user(username: str, password: str, allowed_schemas: List[str], roles: List[str]) -> Tuple[bool, str]:
    """Enveloppe create_api_user() : retourne (succès, message) au lieu de laisser
    remonter l'exception, pour un affichage Streamlit direct."""
    import psycopg2

    try:
        create_api_user(username, password, allowed_schemas, roles)
        return True, f"Utilisateur '{username}' créé dans auth.users."
    except psycopg2.IntegrityError:
        return False, f"L'utilisateur '{username}' existe déjà dans auth.users."
    except Exception as e:
        return False, f"Erreur lors de l'insertion dans auth.users : {e}"


def append_client_to_registry(key: str, login: str, schema: str, role: str, port: int, password: str) -> None:
    """Ajoute (ou remplace) une entrée dans auth.json, même format que les entrées existantes."""
    data = {}
    if os.path.isfile(AUTH_JSON_PATH):
        with open(AUTH_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

    data[key] = {
        "shema": schema,
        "login": login,
        "pswd": password,
        "role": role,
        "port": port,
    }

    with open(AUTH_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
