#!/usr/bin/env bash
# Installation phase 1 (test) : nginx + reverse proxy + 1 instance Streamlit par client.
# Domaine utilise : sageagent.test (placeholder, resolu via /etc/hosts, pas de vrai DNS/TLS).
#
# A executer UNE SEULE FOIS sur le serveur, avec sudo :
#   sudo bash /opt/SageAgent/docs/nginx/1st_implementation/install_phase1.sh
#
# Ce script ne touche PAS au service de production existant (SageAgent_dashbi.service,
# port 8505) : il cree 5 NOUVELLES instances Streamlit sur des ports dedies (8506-8510).

set -euo pipefail
REPO=/opt/SageAgent

echo "== 1. Installer nginx =="
apt-get update
apt-get install -y nginx

echo "== 2. Fichiers d'environnement par client (port dedie) =="
mkdir -p /etc/sageagent/clients
cp "$REPO/service/clients/cross.env"      /etc/sageagent/clients/cross.env
cp "$REPO/service/clients/rousseau.env"   /etc/sageagent/clients/rousseau.env
cp "$REPO/service/clients/mms.env"        /etc/sageagent/clients/mms.env
cp "$REPO/service/clients/muliparts.env"  /etc/sageagent/clients/muliparts.env
cp "$REPO/service/clients/client_01.env"  /etc/sageagent/clients/client_01.env

echo "== 3. Unit systemd templatee =="
cp "$REPO/service/sageagent-dashbi@" /etc/systemd/system/sageagent-dashbi@.service
systemctl daemon-reload

echo "== 4. Activer une instance Streamlit par client =="
for client in cross rousseau mms muliparts client_01; do
    systemctl enable --now "sageagent-dashbi@${client}"
done

echo "== 5. Certificat TLS auto-signe (phase de test uniquement) =="
mkdir -p /etc/nginx/ssl
if [ ! -f /etc/nginx/ssl/sageagent-selfsigned.crt ]; then
    openssl req -x509 -nodes -days 365 \
      -newkey rsa:2048 \
      -keyout /etc/nginx/ssl/sageagent-selfsigned.key \
      -out /etc/nginx/ssl/sageagent-selfsigned.crt \
      -subj "/CN=*.sageagent.test"
else
    echo "   (deja present, non regenere)"
fi

echo "== 6. Config nginx (map + site) =="
rm -f /etc/nginx/conf.d/sageagent_clients.map   # nettoyage : mauvaise extension utilisee lors d'un essai precedent, jamais chargee par nginx
cp "$REPO/nginx/sageagent_clients.conf" /etc/nginx/conf.d/sageagent_clients.conf
cp "$REPO/nginx/sageagent.conf" /etc/nginx/sites-available/sageagent.conf
ln -sf /etc/nginx/sites-available/sageagent.conf /etc/nginx/sites-enabled/sageagent.conf
nginx -t
systemctl reload nginx

echo "== 7. Resolution de noms locale (/etc/hosts) pour tester depuis ce serveur =="
HOSTS_MARKER="# sageagent.test - phase 1 (reverse proxy multi-client, test)"
if ! grep -qF "$HOSTS_MARKER" /etc/hosts; then
    {
        echo "$HOSTS_MARKER"
        echo "127.0.0.1  cross.sageagent.test"
        echo "127.0.0.1  rousseau.sageagent.test"
        echo "127.0.0.1  mms.sageagent.test"
        echo "127.0.0.1  muliparts.sageagent.test"
        echo "127.0.0.1  client_01.sageagent.test"
    } >> /etc/hosts
    echo "   entrees ajoutees a /etc/hosts"
else
    echo "   deja present dans /etc/hosts"
fi

echo ""
echo "== Termine =="
echo "Teste depuis ce serveur :"
echo "  curl -k -I https://cross.sageagent.test"
echo "  curl -k -I https://inconnu.sageagent.test   # doit repondre 404"
echo ""
echo "Pour tester depuis un navigateur/poste externe, ajouter dans SON /etc/hosts :"
echo "  51.255.161.55  cross.sageagent.test rousseau.sageagent.test mms.sageagent.test muliparts.sageagent.test client_01.sageagent.test"
