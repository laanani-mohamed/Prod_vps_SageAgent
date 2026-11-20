#!/usr/bin/env bash
# Côté 51.255.161.55 : front ITBORD derrière nginx (443) pour le reverse proxy de 5.196.101.123.
# Lancer : sudo bash /opt/SageAgent/docs/nginx/3rd_implementation/install_itbord.sh
# Relançable sans risque : chaque étape ne refait que ce qui manque. Le pare-feu n'est PAS touché
# (étape manuelle, voir README.md).
set -euo pipefail
REPO=/opt/SageAgent
SSL=/etc/nginx/ssl

[ "$(id -u)" -eq 0 ] || { echo "À lancer avec sudo"; exit 1; }

echo "== 1. Certificat auto-signé (trajet 5.196 → nous)"
mkdir -p "$SSL"
if [ ! -f "$SSL/itbord-backend.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
    -keyout "$SSL/itbord-backend.key" -out "$SSL/itbord-backend.crt" \
    -subj "/CN=ittelecom.ma" -addext "subjectAltName=DNS:*.ittelecom.ma,DNS:ittelecom.ma"
  chmod 600 "$SSL/itbord-backend.key"
else
  echo "   déjà présent, conservé"
fi
cp "$SSL/itbord-backend.crt" "$REPO/docs/nginx/3rd_implementation/itbord-backend.crt"   # à envoyer à l'admin de 5.196
chmod 644 "$REPO/docs/nginx/3rd_implementation/itbord-backend.crt"

echo "== 2. Site nginx"
cp "$REPO/nginx/itbord.conf" /etc/nginx/sites-available/itbord.conf
ln -sf /etc/nginx/sites-available/itbord.conf /etc/nginx/sites-enabled/itbord.conf
nginx -t
systemctl reload nginx

echo "== 3. Front et API en local uniquement (127.0.0.1)"
cp "$REPO/service/SageAgent_front" /etc/systemd/system/SageAgent_front.service
cp "$REPO/service/SageAgent_api"   /etc/systemd/system/SageAgent_api.service
systemctl daemon-reload
systemctl restart SageAgent_api
sleep 3
systemctl restart SageAgent_front
sleep 5

echo "== 4. Vérifications"
ss -tlnp | grep -E ':8000 |:8504 ' || true
printf "front via nginx (attendu 200)   : "; curl -sk -o /dev/null -w "%{http_code}\n" --resolve cross.ittelecom.ma:443:127.0.0.1 https://cross.ittelecom.ma/login
printf "API en direct publique (attendu 000) : "; curl -s -m 4 -o /dev/null -w "%{http_code}\n" http://51.255.161.55:8000/docs || true
echo
echo "Certificat à envoyer à l'admin de 5.196 : $REPO/docs/nginx/3rd_implementation/itbord-backend.crt"
echo "Avec le fichier de config : $REPO/nginx/ittelecom_proxy_5196.conf"
