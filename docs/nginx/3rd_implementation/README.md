# Implémentation 3 — Front ITBORD en HTTPS via le reverse proxy de 5.196.101.123

Remplace les redirections 301 (`cross.ittelecom.ma` → `http://51.255.161.55:8506`, etc.), qui ne
permettent pas le HTTPS, par un reverse proxy :

```
navigateur ══HTTPS══▶ 5.196.101.123:443 ══HTTPS══▶ 51.255.161.55:443 ──▶ 127.0.0.1:8504 (front) ──▶ 127.0.0.1:8000 (API)
                     cert *.ittelecom.ma         cert auto-signé (vérifié par 5.196)
```

Un seul front pour tous les clients : client et profil viennent du jeton de connexion (API :
`allowed_schemas`, `co_no` ; cache : clé client + requête). Les 6 sous-domaines arrivent sur le même front.

## Fichiers

| Fichier | Où | Rôle |
|---|---|---|
| [`nginx/itbord.conf`](/opt/SageAgent/nginx/itbord.conf) | notre serveur, `/etc/nginx/sites-available/` | 443, n'accepte que 5.196.101.123, proxy vers 127.0.0.1:8504 |
| [`nginx/ittelecom_proxy_5196.conf`](/opt/SageAgent/nginx/ittelecom_proxy_5196.conf) | serveur 5.196 (leur admin) | remplace les 301 par `proxy_pass https://51.255.161.55` |
| [`install_itbord.sh`](install_itbord.sh) | notre serveur | certificat, site nginx, front et API en 127.0.0.1, vérifications |
| `itbord-backend.crt` (créé par le script ici) | à envoyer à 5.196 | certificat public seul ; la clé reste dans `/etc/nginx/ssl/` |
| [`service/SageAgent_front`](/opt/SageAgent/service/SageAgent_front), [`service/SageAgent_api`](/opt/SageAgent/service/SageAgent_api) | `/etc/systemd/system/` | écoute en `127.0.0.1` au lieu de `0.0.0.0` |

## Étapes

1. **Vérifier qui utilise l'API en direct** (`http://51.255.161.55:8000`) : après l'étape 2 elle
   ne sera plus joignable de l'extérieur. `ss -tn | grep :8000` montre les connexions en cours.
   Les appels internes (front, Streamlit, dashboard_ops, hermes) passent par `localhost` : non concernés.
2. **Notre serveur** : `sudo bash /opt/SageAgent/docs/nginx/3rd_implementation/install_itbord.sh`.
   Attendu : `200` pour le front via nginx, `000` pour l'API publique.
3. **Envoyer à l'admin de 5.196** : `itbord-backend.crt` + `nginx/ittelecom_proxy_5196.conf`.
4. **Leur serveur** : installer le `.crt`, remplacer les 301 par le fichier fourni, `nginx -t`, reload.
5. **Tests** : `curl -I https://cross.ittelecom.ma/login` → 200 sans `-k` ; navigateur : cadenas,
   connexion CROSS directeur, CROSS collaborateur, MMS — chacun ne voit que ses données.
6. **Pare-feu** (2ᵉ session SSH ouverte) :
   ```bash
   sudo ufw allow OpenSSH
   sudo ufw allow from 5.196.101.123 to any port 443 proto tcp
   sudo ufw enable && sudo ufw status verbose
   ```
   Ferme de l'extérieur 8000, 8504, 8505, 8585 et 80. Accès à dashboard_ops : `ssh -L 8585:localhost:8585`.
7. **Après validation** : arrêter Streamlit
   (`sudo systemctl disable --now SageAgent_dashbi sageagent-dashbi@{cross,rousseau,mms,muliparts,client_01}`)
   et retirer `sites-enabled/sageagent.conf`.

## Retour arrière

- Chez eux : remettre les blocs 301.
- Chez nous : `sudo rm /etc/nginx/sites-enabled/itbord.conf && sudo systemctl reload nginx` ;
  repasser `-H 0.0.0.0` / `--host 0.0.0.0` dans les deux units, `daemon-reload`, restart ;
  `sudo ufw disable`.
