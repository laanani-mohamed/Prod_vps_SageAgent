"""Page 3 — Onboarding d'un nouveau client (SFTP + utilisateur API + registre)."""
import pandas as pd
import streamlit as st

from services.onboarding import (
    append_client_to_registry,
    create_db_user,
    is_sftp_provisioned,
    next_available_port,
    provision_sftp,
    read_clients_registry,
)

st.title("Onboarding client")

# ── Section A — Clients existants ────────────────────────────────────────────
st.subheader("Clients existants")

registry = read_clients_registry()
if not registry:
    st.warning("Aucun client trouvé dans data_Client/reference/auth.json.")
else:
    rows = [
        {
            "Client": entry["key"],
            "Login": entry.get("login"),
            "Schema": entry.get("shema"),
            "Rôle": entry.get("role"),
            "Port": entry.get("port"),
            "SFTP provisionné ?": "✅" if is_sftp_provisioned(entry["key"]) else "❌",
        }
        for entry in registry
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

# ── Section B — Ajouter un nouveau client ────────────────────────────────────
st.subheader("Ajouter un nouveau client")

with st.form("onboarding_form"):
    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Nom du client (identifiant)", placeholder="ex: nouveauclient")
        login = st.text_input("Login", placeholder="pré-rempli à partir du nom si laissé vide")
        schema = st.text_input("Schema DB", placeholder="pré-rempli à partir du nom si laissé vide")
    with col2:
        manual_password = st.text_input("Mot de passe SFTP", type="password")
        default_port = next_available_port(registry)
        port = st.number_input("Port Streamlit dédié", min_value=1024, max_value=65535, value=default_port, step=1)
        roles = st.text_input("Rôles API (séparés par une virgule)", value="admin")

    submitted = st.form_submit_button("Provisionner", type="primary")

if submitted:
    if not client_name.strip():
        st.error("Le nom du client est obligatoire.")
        st.stop()

    key = client_name.strip().upper()
    login = (login or client_name).strip().upper()
    schema = (schema or client_name).strip().lower()
    roles_list = [r.strip().lower() for r in roles.split(",") if r.strip()] or ["admin"]
    password = manual_password

    if not password:
        st.error("Le mot de passe est obligatoire.")
        st.stop()

    # 1. Provisioning SFTP (sudo, script existant)
    with st.spinner(f"Provisioning SFTP pour '{client_name}'..."):
        sftp_ok, sftp_output = provision_sftp(client_name.strip(), password)

    if sftp_ok:
        st.success("Compte SFTP provisionné.")
    else:
        st.error("Échec du provisioning SFTP — voir la sortie ci-dessous.")
    with st.expander("Sortie de sftp_onboard.sh"):
        st.code(sftp_output or "(aucune sortie)")

    # 2. Utilisateur API (auth.users)
    db_ok, db_message = create_db_user(login, password, [schema], roles_list)
    (st.success if db_ok else st.error)(db_message)

    # 3. Registre auth.json
    if sftp_ok and db_ok:
        append_client_to_registry(key, login, schema, roles_list[0], int(port), password)
        st.success(f"Client '{key}' ajouté à data_Client/reference/auth.json.")
        st.info(
            f"Pour activer son sous-domaine, suivre les étapes 2 à 4 de "
            f"docs/nginx/2st_implementation/README.md avec le port **{int(port)}**."
        )
        st.rerun()
    else:
        st.warning("Le registre auth.json n'a pas été mis à jour car au moins une étape a échoué.")
