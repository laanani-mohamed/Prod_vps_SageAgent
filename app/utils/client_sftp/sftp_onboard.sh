#!/bin/bash
# =============================================================================
# SFTP Onboarding Script — SageAgent
# =============================================================================
# Usage:
#   sudo ./sftp_onboard.sh <client_name>
#   sudo SFTP_PASSWORD="MonMdp123!" ./sftp_onboard.sh <client_name>
#
# Ce script :
#   1. Crée le groupe sftp_users (s'il n'existe pas)
#   2. Sécurise le répertoire upload pour le chroot SSH
#   3. Crée l'utilisateur Linux dédié (sans shell)
#   4. Crée le dossier client avec les bonnes permissions
#   5. Configure sshd_config pour le chroot SFTP
#   6. Redémarre SSH si nécessaire
# =============================================================================

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
SFTP_GROUP="sftp_users"
UPLOAD_ROOT="/var/sftp/upload"
APP_UPLOAD_DIR="/opt/SageAgent/storage_srv/upload"
SSHD_CONFIG="/etc/ssh/sshd_config"
NOLOGIN_SHELL="/usr/sbin/nologin"
WATCHER_GROUP="etl_watchers"

# ── Couleurs ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ── Utilitaires ──────────────────────────────────────────────────────────────
log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Vérifications préliminaires ──────────────────────────────────────────────
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        log_err "Ce script doit être exécuté en root (sudo)."
        exit 1
    fi
}

check_deps() {
    if ! command -v sshd &>/dev/null; then
        log_err "OpenSSH server n'est pas installé."
        exit 1
    fi
    if [ ! -f "$NOLOGIN_SHELL" ]; then
        NOLOGIN_SHELL="/bin/false"
    fi
}

# ── Groupe SFTP ──────────────────────────────────────────────────────────────
setup_groups() {
    # Groupe pour les clients (utilisé par OpenSSH Match Group)
    if ! getent group "$SFTP_GROUP" &>/dev/null; then
        log_info "Création du groupe '$SFTP_GROUP'..."
        groupadd "$SFTP_GROUP"
        log_ok "Groupe '$SFTP_GROUP' créé."
    else
        log_ok "Groupe '$SFTP_GROUP' existe déjà."
    fi

    # Groupe pour le watcher (ETL)
    if ! getent group "$WATCHER_GROUP" &>/dev/null; then
        log_info "Création du groupe '$WATCHER_GROUP'..."
        groupadd "$WATCHER_GROUP"
        log_ok "Groupe '$WATCHER_GROUP' créé."
    else
        log_ok "Groupe '$WATCHER_GROUP' existe déjà."
    fi
}

# ── Répertoire racine upload (chroot parent) ─────────────────────────────────
setup_upload_root() {
    log_info "Vérification de $UPLOAD_ROOT..."

    if [ ! -d "$UPLOAD_ROOT" ]; then
        mkdir -p "$UPLOAD_ROOT"
        log_info "Répertoire $UPLOAD_ROOT créé."
    fi

    # Le chroot parent DOIT être root-owned. 
    # On assigne le groupe au WATCHER_GROUP avec r-x (751)
    # Ainsi le watcher peut lister le contenu, mais pas les clients (others)
    chown root:"$WATCHER_GROUP" "$UPLOAD_ROOT"
    chmod 751 "$UPLOAD_ROOT"        # rwxr-x--x : le groupe etl_watchers peut lire/traverser, les clients (others) ne peuvent que traverser

    # Lier le dossier SFTP vers le répertoire de l'application
    if [ ! -d "$APP_UPLOAD_DIR" ]; then
        mkdir -p "$APP_UPLOAD_DIR"
    fi
    if ! findmnt -M "$APP_UPLOAD_DIR" >/dev/null 2>&1; then
        mount --bind "$UPLOAD_ROOT" "$APP_UPLOAD_DIR"
        if ! grep -q "$APP_UPLOAD_DIR" /etc/fstab; then
            echo "$UPLOAD_ROOT $APP_UPLOAD_DIR none bind 0 0" >> /etc/fstab
        fi
        log_ok "Dossier applicatif lié (bind mount)."
    fi

    # Vérification sécurité chroot : remonter jusqu'à /
    local dir="$UPLOAD_ROOT"
    while [ "$dir" != "/" ]; do
        local owner perm group_name
        owner=$(stat -c '%U' "$dir")
        perm=$(stat -c '%a' "$dir")
        group_name=$(stat -c '%G' "$dir")

        if [ "$owner" != "root" ]; then
            log_err "Sécurité chroot : '$dir' doit être owned par root (actuel: $owner)."
            exit 1
        fi

        # Vérifier que group n'a pas le droit d'écriture (perm[1] >= 2)
        local g_write="${perm:1:1}"
        if [ "$g_write" -ge 2 ] 2>/dev/null && [ "$group_name" != "root" ]; then
            log_warn "'$dir' est group-writable ($group_name). Correction..."
            chmod g-w "$dir"
        fi

        dir=$(dirname "$dir")
    done

    log_ok "Permissions chroot vérifiées sur $UPLOAD_ROOT."
}

# ── Mot de passe ─────────────────────────────────────────────────────────────
get_password() {
    if [ -n "${SFTP_PASSWORD:-}" ]; then
        PASSWORD="$SFTP_PASSWORD"
        log_info "Mot de passe récupéré depuis la variable d'environnement SFTP_PASSWORD."
        return
    fi

    echo
    echo -n "Mot de passe pour '$CLIENT_NAME' : "
    read -rs PASSWORD
    echo
    echo -n "Confirmation du mot de passe : "
    read -rs PASSWORD_CONFIRM
    echo

    if [ "$PASSWORD" != "$PASSWORD_CONFIRM" ]; then
        log_err "Les mots de passe ne correspondent pas."
        exit 1
    fi

    if [ ${#PASSWORD} -lt 8 ]; then
        log_warn "Le mot de passe fait moins de 8 caractères. C'est déconseillé."
        read -rp "Continuer quand même ? [y/N] " confirm
        [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
    fi
}

# ── Création / Mise à jour utilisateur ───────────────────────────────────────
setup_user() {
    local client_dir="$UPLOAD_ROOT/$CLIENT_NAME"

    if id "$CLIENT_NAME" &>/dev/null; then
        log_warn "L'utilisateur '$CLIENT_NAME' existe déjà. Mise à jour du mot de passe..."
        usermod -g "$SFTP_GROUP" -d "/nonexistent" -s "$NOLOGIN_SHELL" "$CLIENT_NAME"
    else
        log_info "Création de l'utilisateur '$CLIENT_NAME'..."
        useradd -g "$SFTP_GROUP" -d "/nonexistent" -s "$NOLOGIN_SHELL" "$CLIENT_NAME"
        log_ok "Utilisateur '$CLIENT_NAME' créé."
    fi

    # Définir le mot de passe
    echo "$CLIENT_NAME:$PASSWORD" | chpasswd
    log_ok "Mot de passe défini pour '$CLIENT_NAME'."
}

# ── Dossier client ───────────────────────────────────────────────────────────
setup_client_dir() {
    local client_dir="$UPLOAD_ROOT/$CLIENT_NAME"

    if [ ! -d "$client_dir" ]; then
        mkdir -p "$client_dir"
        log_info "Dossier '$client_dir' créé."
    fi

    # Ownership : le client est propriétaire, groupe etl_watchers
    # Cela permet au watcher d'y accéder, mais empêche les autres clients (qui sont dans sftp_users) d'y accéder
    chown "${CLIENT_NAME}:${WATCHER_GROUP}" "$client_dir"

    # Permissions : 2770
    #   2 (SGID) → les nouveaux fichiers héritent du groupe etl_watchers
    #   7 (rwx)  → le client peut tout faire
    #   7 (rwx)  → le groupe (watcher) peut lire, écrire, et supprimer (nécessaire pour déplacer les fichiers archivés)
    #   0 (---)  → les autres (dont les autres clients) n'ont aucun accès
    chmod 2770 "$client_dir"

    log_ok "Permissions appliquées sur '$client_dir' (SGID + 2770)."

    # Vérification visuelle
    local ls_out
    ls_out=$(ls -ld "$client_dir")
    log_info "Dossier client : $ls_out"
}

# ── Configuration SSH (chroot) ───────────────────────────────────────────────
ensure_sshd_config() {
    local marker="# === SFTP Chroot Jail for SageAgent ==="

    if grep -qF "$marker" "$SSHD_CONFIG"; then
        log_ok "Configuration SFTP déjà présente dans $SSHD_CONFIG."
        return
    fi

    log_info "Ajout de la configuration SFTP dans $SSHD_CONFIG..."

    cat >> "$SSHD_CONFIG" <<EOF

$marker
Match Group $SFTP_GROUP
    ChrootDirectory $UPLOAD_ROOT
    ForceCommand internal-sftp -d %u
    AllowTcpForwarding no
    X11Forwarding no
    PasswordAuthentication yes
EOF

    log_ok "Configuration SSH mise à jour."
    SSHD_NEEDS_RELOAD=1
}

# ── Rechargement SSH ─────────────────────────────────────────────────────────
reload_sshd() {
    if [ "${SSHD_NEEDS_RELOAD:-0}" -eq 1 ]; then
        log_info "Test de syntaxe sshd..."
        if sshd -t; then
            log_ok "Syntaxe sshd OK."
            log_info "Redémarrage du service SSH..."
            systemctl restart sshd || service ssh restart
            log_ok "Service SSH redémarré."
        else
            log_err "Erreur de syntaxe dans $SSHD_CONFIG !"
            log_err "Vérifiez manuellement avant de redémarrer SSH."
            exit 1
        fi
    else
        log_ok "Aucun redémarrage SSH nécessaire."
    fi
}

# ── Récapitulatif ────────────────────────────────────────────────────────────
print_summary() {
    local client_dir="$UPLOAD_ROOT/$CLIENT_NAME"
    local server_ip
    server_ip=$(hostname -I | awk '{print $1}')

    echo
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ Client '$CLIENT_NAME' provisionné avec succès${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo
    echo -e "  ${YELLOW}Serveur :${NC}  $server_ip (port 22)"
    echo -e "  ${YELLOW}Utilisateur :${NC} $CLIENT_NAME"
    echo -e "  ${YELLOW}Mot de passe :${NC} $( [ -n "${SFTP_PASSWORD:-}" ] && echo '<défini via env>' || echo '<saisi interactivement>' )"
    echo -e "  ${YELLOW}Dossier distant :${NC} /$CLIENT_NAME/ (racine du chroot)"
    echo -e "  ${YELLOW}Chemin local :${NC}  $client_dir"
    echo
    echo -e "  ${BLUE}Commande de test :${NC}"
    echo -e "    sftp $CLIENT_NAME@$server_ip"
    echo
    echo -e "  ${BLUE}Script WinSCP (Windows) :${NC}"
    cat <<'WINSCP'
    @echo off
    set WINSCP="C:\Program Files\WinSCP\WinSCP.com"
    %WINSCP% /command ^
        "open sftp://CLIENT@SERVER/ -hostkey=*" ^
        "lcd C:\Sage\Export\" ^
        "put *.csv" ^
        "exit"
WINSCP
    echo
    echo -e "${YELLOW}⚠️  Important :${NC}"
    echo -e "   - L'utilisateur n'a PAS de shell (SFTP uniquement)"
    echo -e "   - Il est enfermé dans son dossier (chroot jail)"
    echo -e "   - Les fichiers déposés seront lisibles par le groupe '$SFTP_GROUP'"
    echo
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    CLIENT_NAME="${1:-}"

    if [ -z "$CLIENT_NAME" ]; then
        echo "Usage: sudo $0 <client_name>"
        echo "       sudo SFTP_PASSWORD='xxx' $0 <client_name>"
        exit 1
    fi

    # Validation du nom (alphanumérique + underscore uniquement)
    if [[ ! "$CLIENT_NAME" =~ ^[a-zA-Z0-9_]+$ ]]; then
        log_err "Nom de client invalide. Utilisez uniquement lettres, chiffres et underscores."
        exit 1
    fi

    check_root
    check_deps

    log_info "Provisioning du client '$CLIENT_NAME'..."

    setup_groups
    setup_upload_root
    get_password
    setup_user
    setup_client_dir
    ensure_sshd_config
    reload_sshd

    print_summary
}

main "$@"