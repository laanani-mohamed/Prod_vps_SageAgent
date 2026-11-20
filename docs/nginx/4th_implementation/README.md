# Implémentation 4 — Domaine `itbord.ma` en HTTPS (Let's Encrypt / certbot)

**Mis en place le 20/11/2026.** Le front ITBORD (Next.js, port 8504) est servi en HTTPS sur
**https://itbord.ma** par le nginx du serveur `51.255.161.55`, avec un certificat Let's Encrypt
renouvelé automatiquement par certbot.

```
navigateur ══HTTPS══▶ nginx 51.255.161.55:443 ──▶ 127.0.0.1:8504 (front Next.js) ──▶ 127.0.0.1:8000 (API)
           itbord.ma   certificat Let's Encrypt
```

---

## 1. Pourquoi cette méthode (historique de la décision)

| Option étudiée | Verdict |
|---|---|
| **Redirections 301 de `*.ittelecom.ma`** (serveur 5.196.101.123) vers `http://51.255.161.55:<port>` — en place côté ittelecom | Pas de HTTPS possible : le navigateur finit sur une IP (aucun certificat ne couvre une IP), en clair. Et les ports 8506-8509 n'écoutent qu'en local : ces liens ne répondent pas. |
| **Reverse proxy sur 5.196.101.123** (`proxy_pass` vers notre nginx en HTTPS) | Valable, préparé (`docs/nginx/3rd_implementation/`) mais **non déployé** : dépend de l'admin de 5.196, pas disponible pour l'instant. |
| **OVH SSL Gateway** | Exige aussi de changer le DNS ; offre payante (Advanced) dès plusieurs sous-domaines ; un seul ensemble IP:port pour tous les domaines. Pas d'avantage ici. |
| **DNS direct + certbot sur notre nginx** ✅ | Retenu : gratuit, officiel (Let's Encrypt = autorité reconnue par tous les navigateurs), renouvellement automatique, aucune dépendance externe. |

**Un seul front pour tous les clients** (au lieu d'un port Streamlit par client) : le client et le
profil viennent du jeton de connexion, pas de l'adresse. L'API refuse tout schéma hors
`allowed_schemas` et impose le `co_no` d'un collaborateur ; le cache de l'API a une clé par client et
par requête (dont `co_no`) ; le front n'a pas de cache partagé (`cache: 'no-store'`).

---

## 2. DNS (chez Heberjahiz, registrar de `itbord.ma`)

Espace client Heberjahiz → **Mes services → itbord.ma → Mon domaine**.

- Onglet **DNS** (serveurs DNS) : **non modifié** — reste sur « DNS de redirection »
  (`dmns1.heberjahiz.com`, `dmns2.heberjahiz.com`), ce qui laisse la zone gérée par Heberjahiz.
- Onglet **Zone Edit** (enregistrements) :

| Hostname | Type | Avant | Après |
|---|---|---|---|
| `@` | A | 169.50.173.20 (parking Heberjahiz) | **51.255.161.55** |
| `www` | A | 169.50.173.20 | **51.255.161.55** |
| `*` | A | 169.50.173.20 | **supprimé** (pas de sous-domaines pour l'instant) |

Pas d'enregistrement AAAA (IPv6) : nginx n'écoute pas en IPv6 sur 443. Onglet Email/MX non touché.
Expiration du domaine : **22/09/2027** (à renouveler chez Heberjahiz).

Vérification :
```bash
dig +short itbord.ma @8.8.8.8          # 51.255.161.55
dig +short www.itbord.ma @8.8.8.8      # 51.255.161.55
```

---

## 3. Commandes exécutées sur le serveur

certbot 4.0.0 et `python3-certbot-nginx` étaient déjà installés (paquets Ubuntu).

```bash
# 1. Certificat (validation HTTP-01 sur le port 80, via nginx)
sudo certbot certonly --nginx -d itbord.ma -d www.itbord.ma -m <email> --agree-tos --no-eff-email

# 2. Site nginx (fichier du dépôt)
sudo cp /opt/SageAgent/nginx/itbord_ma.conf /etc/nginx/sites-available/itbord_ma.conf
sudo ln -sf /etc/nginx/sites-available/itbord_ma.conf /etc/nginx/sites-enabled/itbord_ma.conf
sudo nginx -t && sudo systemctl reload nginx
```

Résultat constaté le 20/11/2026 :

| Test | Résultat |
|---|---|
| `http://itbord.ma` | 301 → `https://itbord.ma/` |
| `https://www.itbord.ma` | 301 → `https://itbord.ma/` |
| `https://itbord.ma/login` | 200, en-tête `Strict-Transport-Security: max-age=31536000` |
| Certificat | `CN=itbord.ma`, SAN `itbord.ma, www.itbord.ma`, émetteur Let's Encrypt `YE1`, clé ECDSA, **valide du 20/11/2026 au 18/02/2027** |

---

## 4. Fichiers et dossiers créés

### Dans le dépôt (versionnés)

| Fichier | Rôle |
|---|---|
| [`nginx/itbord_ma.conf`](/opt/SageAgent/nginx/itbord_ma.conf) | Site nginx : HTTP → HTTPS, `www` → domaine nu, HTTPS → `127.0.0.1:8504` avec `Host`, `X-Forwarded-Proto https` (cookies `Secure`), `X-Forwarded-For`, HSTS, timeout 300 s (exports). **Source de vérité** : toute modification se fait ici puis est recopiée dans `/etc/nginx/`. |
| `docs/nginx/4th_implementation/README.md` | Ce document. |

### Sur le serveur (hors dépôt)

| Chemin | Créé par | Contenu |
|---|---|---|
| `/etc/nginx/sites-available/itbord_ma.conf` | nous (copie du dépôt) | Site actif |
| `/etc/nginx/sites-enabled/itbord_ma.conf` | nous (lien symbolique) | Active le site |
| `/etc/letsencrypt/live/itbord.ma/` | certbot | **Liens** vers la version courante : `fullchain.pem` (certificat + chaîne, utilisé par nginx), `privkey.pem` (**clé privée**, utilisée par nginx), `cert.pem`, `chain.pem`. nginx pointe toujours ici : un renouvellement ne demande aucun changement de config. |
| `/etc/letsencrypt/archive/itbord.ma/` | certbot | Les vrais fichiers, numérotés (`cert1.pem`, `privkey1.pem`, puis `…2.pem` au renouvellement). |
| `/etc/letsencrypt/renewal/itbord.ma.conf` | certbot | Paramètres du renouvellement : `authenticator = nginx`, `installer = nginx` (rechargement de nginx après renouvellement), `key_type = ecdsa`, serveur ACME de production. |
| `/etc/letsencrypt/accounts/` | certbot | Compte ACME Let's Encrypt (lié à l'email fourni). |
| `/etc/letsencrypt/renewal-hooks/{pre,deploy,post}/` | certbot | Scripts optionnels lancés autour d'un renouvellement (vides). |
| `/etc/letsencrypt/options-ssl-nginx.conf`, `ssl-dhparams.pem` | plugin nginx de certbot | Réglages TLS proposés par certbot — **non utilisés** par `itbord_ma.conf`. |
| `/var/log/letsencrypt/letsencrypt.log` | certbot | Journal des demandes et renouvellements (premier endroit à lire en cas d'échec). |

`/etc/letsencrypt/` contient la clé privée : **jamais dans git**. À inclure dans les sauvegardes du
serveur (sinon, après une réinstallation, refaire simplement la commande certbot de l'étape 3).

---

## 5. Renouvellement

- Un certificat Let's Encrypt dure **90 jours**. Le timer systemd `certbot.timer` (installé par le
  paquet) lance `certbot renew` deux fois par jour ; certbot ne renouvelle qu'à **30 jours** de
  l'échéance, soit vers le **19/01/2027** pour le certificat actuel, puis tous les ~60 jours.
- Le renouvellement refait la validation HTTP-01 sur le port 80, puis recharge nginx. Aucune action
  manuelle.

Conditions pour que ça continue de marcher :
1. **Le DNS de `itbord.ma` et `www.itbord.ma` reste sur `51.255.161.55`.**
2. **Le port 80 reste ouvert** (si `ufw` est activé : `sudo ufw allow 'Nginx Full'`, pas seulement 443).
3. Le bloc `listen 80` de `itbord_ma.conf` reste en place (certbot y injecte temporairement le défi).
4. Le domaine reste payé chez Heberjahiz (échéance 22/09/2027).

Let's Encrypt n'envoie plus d'emails d'alerte avant expiration : vérifier de temps en temps.

### Commandes utiles

```bash
sudo certbot certificates                 # certificats gérés, domaines, date d'expiration
sudo certbot renew --dry-run              # simulation complète du renouvellement (sans rien changer)
systemctl list-timers | grep certbot      # prochain passage du timer
echo | openssl s_client -connect itbord.ma:443 -servername itbord.ma 2>/dev/null \
  | openssl x509 -noout -dates            # dates du certificat réellement servi (sans sudo)
sudo tail -50 /var/log/letsencrypt/letsencrypt.log
```

Renouvellement forcé (si besoin, ex. après un incident) : `sudo certbot renew --force-renewal`
(à ne pas répéter : Let's Encrypt limite le nombre de certificats par semaine).

---

## 6. Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| `certbot renew` échoue, « Timeout during connect » / « unauthorized » | Port 80 fermé ou DNS modifié | `dig +short itbord.ma @8.8.8.8`, `sudo ufw status`, `curl -I http://itbord.ma` |
| Navigateur : certificat expiré | Renouvellement en échec depuis 30 jours | Lire `/var/log/letsencrypt/letsencrypt.log`, corriger, `sudo certbot renew` |
| 502 Bad Gateway | Front arrêté | `systemctl status SageAgent_front`, `curl -I http://127.0.0.1:8504/login` |
| Connexion impossible (erreur « Server Action » / origine) | En-tête `Host` non transmis | Vérifier `proxy_set_header Host $host;` dans `itbord_ma.conf` |
| Déconnecté à chaque page | Cookies `Secure` non reçus | Vérifier `X-Forwarded-Proto https` dans `itbord_ma.conf` |

---

## 7. Retour arrière

```bash
sudo rm /etc/nginx/sites-enabled/itbord_ma.conf
sudo nginx -t && sudo systemctl reload nginx
```
Le front n'écoute plus que sur `127.0.0.1` : pour le rendre de nouveau joignable sans nginx, remettre
`-H 0.0.0.0` dans `service/SageAgent_front` (puis `cp` vers `/etc/systemd/system/`, `daemon-reload`,
`restart`) ; il est alors sur `http://51.255.161.55:8504`. Le certificat peut rester dans
`/etc/letsencrypt` (ou `sudo certbot delete --cert-name itbord.ma` pour le supprimer et arrêter
son renouvellement).

---

## 8. Ce qui reste à faire

- [x] **API fermée au public** (fait le 20/11/2026) : `SageAgent_api` lancé avec `--host 127.0.0.1` ;
      `http://<IP>:8000` ne répond plus (il était sondé chaque jour par des robots). Appelants, tous en
      local : le front (`API_URL`) et Hermes (`API_BASE_URL` dans `~/.hermes/plugins/zoo_api/__init__.py`,
      passé de l'IP publique à `127.0.0.1`). `/telegram/*` est conservé tel quel (Hermes s'en sert) : il
      reste sans authentification, mais seulement pour les programmes du serveur. Swagger : tunnel SSH
      `ssh -L 8000:127.0.0.1:8000 <utilisateur>@51.255.161.55`, puis `http://localhost:8000/docs`.
- [x] **Front en local** (fait le 20/11/2026) : `SageAgent_front` lancé avec `-H 127.0.0.1` ; accès public
      uniquement par **https://itbord.ma**, `http://<IP>:8504` ne répond plus.
- [ ] Pare-feu : `sudo ufw allow OpenSSH` (en premier), `sudo ufw allow 'Nginx Full'`, `sudo ufw enable`
      — garder une 2ᵉ session SSH ouverte pendant l'opération.
- [ ] Arrêter les instances Streamlit (8505-8510) quand tous les clients sont passés sur le front.
- [ ] (Optionnel) Alerte d'expiration du certificat (cron + `openssl x509 -checkend`).
- [ ] (Plus tard) Si le proxy de 5.196 est déployé : `docs/nginx/3rd_implementation/`.
