"""Page 3 — Onboarding client (schéma PostgreSQL, SFTP, utilisateur API, registre)."""
import pandas as pd
import streamlit as st

from services.onboarding import (
    append_client_to_registry,
    create_client_schema,
    collaborateur_existe,
    create_db_user,
    is_sftp_provisioned,
    mot_de_passe_invalide,
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

# ── Section B — Créer le schéma d'un client ──────────────────────────────────
st.subheader("Créer le schéma d'un client")
st.caption("Crée le schéma PostgreSQL et ses 11 tables Sage vides (utils/migrations/create_client_schema.sql).")

with st.form("schema_form"):
    new_schema = st.text_input("Nom du schéma", placeholder="ex: nouveauclient")
    schema_submitted = st.form_submit_button("Créer", type="primary")

if schema_submitted:
    with st.spinner(f"Création du schéma '{new_schema.strip().lower()}'..."):
        schema_ok, schema_message = create_client_schema(new_schema)
    (st.success if schema_ok else st.error)(schema_message)

st.divider()

# ── Section C — Ajouter un nouveau client ────────────────────────────────────
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
        profil = st.selectbox(
            "Profil API", ["directeur"], disabled=True,
            help="Compte principal du client. Les collaborateurs se créent dans « Créer un profil ».",
        )

    submitted = st.form_submit_button("Provisionner", type="primary")

if submitted:
    if not client_name.strip():
        st.error("Le nom du client est obligatoire.")
        st.stop()

    key = client_name.strip().upper()
    login = (login or client_name).strip().upper()
    schema = (schema or client_name).strip().lower()
    roles_list = [profil]
    password = manual_password

    if not password:
        st.error("Le mot de passe est obligatoire.")
        st.stop()
    # Avant le SFTP : sftp_onboard.sh réinitialise le mot de passe d'un compte existant
    if key in {entry["key"].upper() for entry in registry}:
        st.error(f"Le client '{key}' existe déjà. Pour lui ajouter un utilisateur, utiliser « Créer un profil ».")
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

st.divider()

# ── Section D — Créer un profil ──────────────────────────────────────────────
st.subheader("Créer un profil")
st.caption("Ajoute un utilisateur API (directeur ou collaborateur) à un client existant : "
           "ni compte SFTP, ni modification du registre auth.json.")

clients_par_nom = {entry["key"]: entry for entry in registry}
nom_client = st.selectbox("Nom du client", list(clients_par_nom), index=None, placeholder="Choisir un client…",
                          key="profil_client")

if nom_client:
    client = clients_par_nom[nom_client]
    with st.form("profil_form"):
        col1, col2 = st.columns(2)
        with col1:
            profil_login = st.text_input("Login", placeholder="ex: M.AMANOU")
            st.text_input("Schema DB", value=client.get("shema", ""), disabled=True, key=f"profil_schema_{nom_client}")
            st.number_input("Port Streamlit dédié", value=int(client.get("port") or 0), disabled=True,
                            key=f"profil_port_{nom_client}")
            profil_password = st.text_input("Mot de passe", type="password",
                                            help="8 caractères minimum, dont une majuscule et un chiffre.")
        with col2:
            profil_role = st.selectbox(
                "Profil API", ["directeur", "collaborateur"],
                help="directeur : accès complet. collaborateur : uniquement ses propres chiffres.",
            )
            profil_co_no = st.number_input(
                "Identifiant collaborateur (co_no Sage)", min_value=0, value=0, step=1,
                help="Obligatoire pour un collaborateur (F_COLLABORATEUR.co_no, > 0). Ignoré pour un directeur.",
            )
        profil_submitted = st.form_submit_button("Créer le profil", type="primary")

    if profil_submitted:
        profil_schema = client.get("shema", "")
        co_no = int(profil_co_no) if profil_role == "collaborateur" else None
        motif = None
        if not profil_login.strip():
            motif = "Le login est obligatoire."
        elif mot_de_passe_invalide(profil_password):
            motif = mot_de_passe_invalide(profil_password)
        elif profil_role == "collaborateur" and not co_no:
            motif = "L'identifiant collaborateur (co_no > 0) est obligatoire pour un profil collaborateur."
        elif co_no and not collaborateur_existe(profil_schema, co_no):
            motif = f"Le collaborateur {co_no} n'existe pas dans {profil_schema}.f_collaborateur."
        if motif:
            st.error(motif)
        else:
            profil_ok, profil_message = create_db_user(
                profil_login.strip(), profil_password, [profil_schema], [profil_role], co_no)
            (st.success if profil_ok else st.error)(profil_message)
