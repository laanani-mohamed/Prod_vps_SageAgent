# Implémentation 2 — Bascule finale (vrai domaine + vrai certificat TLS) et onboarding client

Ce document couvre deux choses distinctes :
1. **La bascule** : remplacer le domaine de test (`sageagent.test`) et le certificat
   auto-signé (mis en place dans `1st_implementation`) par le vrai domaine et un vrai
   certificat Let's Encrypt.
2. **La procédure répétable** pour ajouter un nouveau client (6e, 7e, ...) une fois la base
   en place.

Pré-requis pour commencer la partie 1 : avoir reçu le nom de domaine réel, et avoir accès à
la gestion DNS de ce domaine (pour créer un enregistrement wildcard et, si on automatise le
renouvellement du certificat, un accès API chez le registrar/fournisseur DNS).

---

## Partie 1 — Bascule vers le vrai domaine et le vrai certificat

Remplacer `VOTREDOMAINE.COM` ci-dessous par le vrai domaine dans chaque commande.

### Étape 1 — DNS : enregistrement wildcard (une seule fois)

Chez le fournisseur DNS du domaine, créer :
```
Type: A
Nom:  *.VOTREDOMAINE.COM
Valeur: 51.255.161.55   (IP publique actuelle du serveur — à reconfirmer avec `hostname -I` le jour J)
TTL: 3600
```
Ainsi, `cross.VOTREDOMAINE.COM`, `rousseau.VOTREDOMAINE.COM`, etc. résolvent automatiquement,
et ajouter un futur client ne demande **aucune** nouvelle entrée DNS.

**Pourquoi un wildcard plutôt qu'un enregistrement par client** : avec un enregistrement par
client, chaque onboarding demanderait un aller-retour DNS (propagation, délai) en plus du
travail serveur. Le wildcard élimine cette dépendance externe pour tout le cycle de vie du
projet.

### Étape 2 — Certificat TLS wildcard (Let's Encrypt)

Le serveur est hébergé chez OVH (IP `51.255.161.55` dans un bloc OVH) — si le domaine est
aussi géré chez OVH, utiliser le plugin `certbot-dns-ovh` ; sinon adapter au vrai
registrar/fournisseur DNS (`certbot-dns-cloudflare`, `certbot-dns-gandi`,
`certbot-dns-route53`, ...). Le principe est identique, seul le plugin change.

Un certificat **wildcard** exige un challenge DNS-01 (pas http-01), donc ce plugin est
nécessaire (impossible d'obtenir un wildcard autrement) :

```bash
sudo apt install -y certbot python3-certbot-dns-ovh   # adapter le paquet au fournisseur réel

sudo mkdir -p /etc/letsencrypt/secrets
sudo tee /etc/letsencrypt/secrets/ovh.ini <<'EOF'
dns_ovh_endpoint = ovh-eu
dns_ovh_application_key = VOTRE_APPLICATION_KEY
dns_ovh_application_secret = VOTRE_APPLICATION_SECRET
dns_ovh_consumer_key = VOTRE_CONSUMER_KEY
EOF
sudo chmod 600 /etc/letsencrypt/secrets/ovh.ini

sudo certbot certonly \
  --dns-ovh \
  --dns-ovh-credentials /etc/letsencrypt/secrets/ovh.ini \
  -d "VOTREDOMAINE.COM" -d "*.VOTREDOMAINE.COM" \
  --agree-tos -m admin@VOTREDOMAINE.COM --non-interactive
```

Résultat : `/etc/letsencrypt/live/VOTREDOMAINE.COM/fullchain.pem` et `privkey.pem`, valables
pour **tous** les sous-domaines clients (actuels et futurs). Certbot installe un timer de
renouvellement automatique — vérifier après coup avec `sudo systemctl list-timers | grep certbot`
et tester le renouvellement à blanc avec `sudo certbot renew --dry-run`.

### Étape 3 — Basculer la config nginx du domaine de test vers le vrai domaine

Éditer les **fichiers source dans le dépôt** (pas directement `/etc/`, pour garder le dépôt
comme référence à jour — même logique que le dossier `service/` existant) :

- [`nginx/sageagent_clients.conf`](/opt/SageAgent/nginx/sageagent_clients.conf) : remplacer
  chaque `*.sageagent.test` par `*.VOTREDOMAINE.COM`.
- [`nginx/sageagent.conf`](/opt/SageAgent/nginx/sageagent.conf) : remplacer
  `\.sageagent\.test$` par `\.VOTREDOMAINE\.COM$` (2 occurrences, dans les deux blocs
  `server_name`), et remplacer les 2 lignes de certificat :
  ```nginx
  ssl_certificate     /etc/nginx/ssl/sageagent-selfsigned.crt;
  ssl_certificate_key /etc/nginx/ssl/sageagent-selfsigned.key;
  ```
  par :
  ```nginx
  ssl_certificate     /etc/letsencrypt/live/VOTREDOMAINE.COM/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/VOTREDOMAINE.COM/privkey.pem;
  ```

Puis redéployer :
```bash
sudo cp /opt/SageAgent/nginx/sageagent_clients.conf /etc/nginx/conf.d/sageagent_clients.conf
sudo cp /opt/SageAgent/nginx/sageagent.conf /etc/nginx/sites-available/sageagent.conf
sudo nginx -t && sudo systemctl reload nginx
```

Tester (depuis n'importe où, plus besoin de `/etc/hosts` ni de `-k`) :
```bash
curl -I https://cross.VOTREDOMAINE.COM
openssl s_client -connect cross.VOTREDOMAINE.COM:443 -servername cross.VOTREDOMAINE.COM \
  | openssl x509 -noout -dates   # vérifier la validité du certificat réel
```

### Étape 4 — Décider du sort de l'ancien service (port 8505)

Depuis la phase 1, `SageAgent_dashbi.service` (port 8505, `0.0.0.0`, accessible directement
sans passer par nginx) tourne toujours en parallèle. Une fois la bascule validée pour les 5
clients, deux options :
- **Le retirer** : `sudo systemctl disable --now SageAgent_dashbi.service` si plus aucun
  client n'y accède directement (tout le monde passe par son sous-domaine dédié).
- **Le garder** comme accès de secours/interne, mais alors le repasser en loopback
  (`--server.address=127.0.0.1` dans son unit) pour qu'il ne soit plus exposé publiquement
  sans passer par nginx.
À trancher selon l'usage réel constaté après la bascule — pas de raccourci à prendre à la
légère puisque ce service sert peut-être encore des utilisateurs actifs au moment du switch.

### Étape 5 — Durcissement pare-feu (maintenant que la bascule est faite)

Avant la bascule, `ufw` n'était pas activé pour ne rien casser (8505/8585 étaient encore les
seuls points d'accès). Une fois nginx confirmé comme unique point d'entrée public :

```bash
sudo ufw allow OpenSSH        # a faire EN PREMIER, sous peine de perdre l'accès SSH
sudo ufw allow 'Nginx Full'   # 80 + 443
sudo ufw enable
sudo ufw status verbose
```
Puis, seulement après avoir confirmé que SSH fonctionne toujours dans une session séparée :
```bash
sudo ufw deny 8506:8510/tcp   # defense en profondeur (deja en 127.0.0.1, donc deja inaccessibles de l'exterieur)
sudo ufw deny 8585/tcp        # dashboard_ops interne, ne doit plus etre public
# 8505 : voir Etape 4 - ne fermer que si le service est retire ou repasse en loopback
```
**Prudence** : `ufw enable` sur un serveur distant peut couper l'accès SSH en cas d'erreur —
garder une session SSH ouverte en parallèle pendant cette étape, au cas où il faille corriger
une règle avant de se déconnecter.

---

## Partie 2 — Ajouter un nouveau client (procédure répétable)

À suivre pour le 6e client et tous les suivants, une fois la bascule (Partie 1) faite. Aucune
étape DNS n'est nécessaire grâce au wildcard.

1. **Choisir le port** : le prochain libre après le dernier attribué (voir tableau dans
   `1st_implementation/README.md`, à tenir à jour ici aussi). Ex. 6e client → 8511.
2. **Fichier d'environnement** : créer `service/clients/<client>.env` dans le dépôt avec
   `PORT=<port choisi>`, puis :
   ```bash
   sudo cp service/clients/<client>.env /etc/sageagent/clients/<client>.env
   ```
3. **Démarrer son instance Streamlit** :
   ```bash
   sudo systemctl enable --now sageagent-dashbi@<client>
   ```
   (réutilise l'unit template déjà installée en phase 1, aucune nouvelle unit à écrire).
4. **Ajouter la ligne dans la map nginx** — éditer `nginx/sageagent_clients.conf` dans le
   dépôt (garder l'extension `.conf`, sinon nginx ignore le fichier — voir l'incident
   documenté dans `1st_implementation/README.md`), ajouter `<client>.VOTREDOMAINE.COM  <port>;`, puis :
   ```bash
   sudo cp nginx/sageagent_clients.conf /etc/nginx/conf.d/sageagent_clients.conf
   sudo nginx -t && sudo systemctl reload nginx
   ```
5. **Créer les identifiants du client** dans
   [`data_Client/reference/auth.json`](/opt/SageAgent/data_Client/reference/auth.json), en
   suivant le même format que les entrées existantes (`shema`, `login`, `pswd`, `role`,
   `port`) — le `port` doit correspondre à celui choisi à l'étape 1.
6. **Créer/confirmer l'utilisateur en base** (`auth.users`, `allowed_schemas`) pour que le
   login JWT autorise ce client sur son schema — mécanisme existant, indépendant de ce plan
   réseau (voir le service d'auth dans `app/src/api/auth/`).
7. **Tester** :
   ```bash
   curl -I https://<client>.VOTREDOMAINE.COM
   ```
   puis se connecter avec le compte du client et vérifier l'accès à ses données uniquement.
8. **Mettre à jour le registre** (tableau des clients/ports dans la documentation) pour que
   le prochain onboarding parte du bon port.
