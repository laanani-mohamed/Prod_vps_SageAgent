# nginx — composants et configuration du projet SageAgent

Ce document explique : (1) les briques de base de nginx en général, (2) ce qui a
concrètement été configuré dans ce projet, où, et pourquoi.

---

## 1. Composants génériques de nginx (concepts)

| Composant | C'est quoi | À quoi ça sert |
|---|---|---|
| **`nginx.conf`** | Fichier de config principal (`/etc/nginx/nginx.conf`). | Définit les réglages globaux et surtout les `include` qui chargent tous les autres fichiers de config (`conf.d/*.conf`, `sites-enabled/*`). C'est le point d'entrée de toute la configuration. |
| **Contexte `http {}`** | Bloc englobant dans lequel vivent toutes les règles liées au web (HTTP/HTTPS). | Tout ce qui suit (`server`, `map`, `upstream`, ...) doit être déclaré dedans (directement ou via un fichier inclus dedans). |
| **`server { }`** | Un "virtual host" : une unité qui répond pour un ou plusieurs noms de domaine / adresses IP. | Permet de faire cohabiter plusieurs sites/domaines sur la même machine, chacun avec ses propres règles. |
| **`listen`** | Le port (et éventuellement l'IP) sur lequel un `server{}` écoute (ex. `80`, `443 ssl`). | Distingue le trafic HTTP (80) du HTTPS (443), et permet à plusieurs `server{}` de partager le même port en étant différenciés par `server_name`. |
| **`server_name`** | Le(s) nom(s) de domaine que ce bloc `server{}` doit gérer (littéral ou expression régulière avec `~`). | Route la requête entrante vers le bon `server{}` selon l'en-tête `Host` envoyé par le client. |
| **`location { }`** | Une règle qui matche un chemin d'URL (ex. `/`, `/api/`, `/static/`) à l'intérieur d'un `server{}`. | Permet de traiter différemment différentes parties d'un même site (ex. `/` vers une appli, `/static/` vers des fichiers). |
| **`map $var1 $var2 { ... }`** | Une table de correspondance : transforme la valeur d'une variable en une autre. | Évite de dupliquer des blocs `server{}` presque identiques — une seule table centralise "telle valeur d'entrée → telle sortie". |
| **`proxy_pass`** | Directive qui transmet la requête reçue vers un autre serveur (ici, une appli qui tourne en local). | C'est le cœur du **reverse proxy** : nginx reçoit la requête publique et la relaie en interne vers l'appli réelle. |
| **`proxy_set_header`** | Ajoute/modifie un en-tête HTTP avant de le transmettre au serveur interne. | Sans ça, l'appli derrière le proxy perdrait des informations utiles (nom d'hôte demandé, IP réelle du visiteur, etc.) ou ne recevrait pas la requête correctement (cas du WebSocket, voir plus bas). |
| **`upstream { }`** | Regroupe plusieurs serveurs backend sous un même nom, pour répartir la charge entre eux. | Utile pour la répartition de charge / haute dispo (**pas utilisé actuellement** dans ce projet — un seul backend par client — mais utile à connaître si un client grossit). |
| **`ssl_certificate` / `ssl_certificate_key`** | Chemins vers le certificat TLS et sa clé privée. | Permettent à nginx de chiffrer le trafic (HTTPS) pour les domaines du bloc `server{}` où ils sont déclarés. |
| **`return 301 ...` / `return 404`** | Renvoie directement une réponse (redirection ou erreur) sans contacter de backend. | Utilisé ici pour forcer HTTP→HTTPS, et pour rejeter proprement un sous-domaine inconnu. |
| **`sites-available/` + `sites-enabled/`** | Convention Debian/Ubuntu : les configs de sites sont écrites dans `sites-available/`, et seules celles qui ont un **lien symbolique** dans `sites-enabled/` sont réellement actives. | Permet d'activer/désactiver un site sans supprimer sa config (juste retirer le lien). |
| **`conf.d/`** | Dossier de fragments de config chargés automatiquement (tout fichier `*.conf`). | Pratique pour des morceaux de config transverses (comme notre `map`) qui ne sont pas un site à eux seuls. **Piège** : seuls les fichiers en `.conf` sont chargés (voir incident documenté dans `docs/nginx/1st_implementation/README.md` — un fichier nommé `.map` y était silencieusement ignoré). |

---

## 2. Ce qu'on a configuré dans SageAgent

### Vue d'ensemble

```
Client (navigateur) --HTTPS--> nginx (443) --map $host--> proxy_pass 127.0.0.1:<port> --> Streamlit du client
```

nginx sert **uniquement** de routeur d'entrée pour les dashboards Streamlit — il n'intervient
pas dans les appels internes Streamlit → API FastAPI (voir échange précédent).

### Fichiers du projet (source de vérité, dans le dépôt git)

| Fichier dans le dépôt | Installé vers (sur le serveur) | Utilité |
|---|---|---|
| [`nginx/sageagent_clients.conf`](/opt/SageAgent/nginx/sageagent_clients.conf) | `/etc/nginx/conf.d/sageagent_clients.conf` | La table `map` : associe chaque sous-domaine client (`cross.sageagent.test`, ...) à son port local dédié (8506-8510). C'est le fichier qu'on édite à chaque onboarding d'un nouveau client. |
| [`nginx/sageagent.conf`](/opt/SageAgent/nginx/sageagent.conf) | `/etc/nginx/sites-available/sageagent.conf` (activé via lien symbolique dans `sites-enabled/`) | Les 2 blocs `server{}` : redirection HTTP→HTTPS, et le bloc HTTPS générique qui fait le reverse proxy réel vers le port du client. Ne change quasiment jamais, même en ajoutant des clients. |
| *(généré directement sur le serveur, non versionné)* | `/etc/nginx/ssl/sageagent-selfsigned.{crt,key}` | Certificat TLS auto-signé, phase de test uniquement. Jamais mis dans git (une clé privée ne doit jamais être versionnée). Remplacé par un vrai certificat Let's Encrypt en phase 2. |

### Détail des directives utilisées dans `nginx/sageagent_clients.conf`

```nginx
map $host $sageagent_port {
    default                     0;
    cross.sageagent.test        8506;
    ...
}
```
- `$host` : variable nginx = le nom de domaine demandé par le client (en-tête `Host`).
- `$sageagent_port` : variable **créée par nous** via ce `map`, utilisée ensuite dans `sageagent.conf`.
- `default 0` : toute valeur de `$host` non listée reçoit `0` → sert de garde-fou (voir plus bas, `if ($sageagent_port = 0)`), empêche qu'un domaine non prévu tombe sur un port par défaut.

### Détail des directives utilisées dans `nginx/sageagent.conf`

**Bloc 1 — redirection HTTP → HTTPS :**
```nginx
server {
    listen 80;
    server_name ~^(?<sub>.+)\.sageagent\.test$;
    return 301 https://$host$request_uri;
}
```
- `server_name` en expression régulière (`~^...$`) : matche **n'importe quel** sous-domaine de `sageagent.test`, sans avoir à lister chaque client ici (contrairement au `map`, qui lui liste chaque client — la regex sert juste à capter tout le trafic HTTP entrant sur ce domaine, le routage précis se fait plus loin).
- `return 301` : redirection permanente vers la même URL en HTTPS.

**Bloc 2 — reverse proxy HTTPS :**
```nginx
server {
    listen 443 ssl;
    server_name ~^(?<sub>.+)\.sageagent\.test$;
    ssl_certificate     /etc/nginx/ssl/sageagent-selfsigned.crt;
    ssl_certificate_key /etc/nginx/ssl/sageagent-selfsigned.key;

    if ($sageagent_port = 0) { return 404; }

    location / {
        proxy_pass http://127.0.0.1:$sageagent_port;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```
- `listen 443 ssl` : ce bloc gère le HTTPS (termine le chiffrement TLS ici, avant de transmettre en clair au backend en interne — normal, le trajet nginx→Streamlit reste sur la machine, `127.0.0.1`).
- `if ($sageagent_port = 0) { return 404; }` : le garde-fou — si le sous-domaine demandé n'est pas dans la `map`, on renvoie 404 tout de suite, sans jamais essayer de proxifier vers un port au hasard.
- `location /` : s'applique à toute l'URL (Streamlit gère lui-même ses propres sous-chemins internes, pas besoin de découper ici).
- `proxy_pass http://127.0.0.1:$sageagent_port` : **le cœur du reverse proxy** — transmet la requête vers l'instance Streamlit du bon client, en utilisant le port trouvé par la `map`.
- `proxy_http_version 1.1` + `proxy_set_header Upgrade`/`Connection "upgrade"` : **indispensables pour Streamlit**, qui utilise une connexion WebSocket permanente pour rafraîchir l'interface en direct. Sans ces lignes, le dashboard se chargerait mais resterait figé (pas de mise à jour dynamique).
- `proxy_set_header Host $host` : transmet le vrai nom de domaine demandé à Streamlit (sinon il verrait toujours `127.0.0.1` comme si tout le monde tapait la même URL).
- `proxy_set_header X-Real-IP` / `X-Forwarded-For` : transmettent l'IP réelle du visiteur (sinon Streamlit verrait toujours l'IP de nginx, `127.0.0.1`, dans ses logs).
- `proxy_set_header X-Forwarded-Proto $scheme` : indique au backend que la requête d'origine était en HTTPS (utile si l'appli a besoin de le savoir, ex. générer des liens absolus corrects).
- `proxy_read_timeout 86400` : évite que nginx ne coupe la connexion WebSocket après le timeout par défaut (assez court) — la session Streamlit doit pouvoir rester ouverte des heures.

### Ce qui n'est PAS géré par nginx dans ce projet

- L'appel Streamlit → API FastAPI (`http://localhost:8000`) : interne au serveur, ne passe jamais par nginx.
- Le service `dashboard_ops` (port 8585, outil interne) : pas de sous-domaine, pas de bloc nginx — reste en dehors de ce périmètre.
- Le service historique `SageAgent_dashbi.service` (port 8505) : toujours accessible directement, pas encore basculé derrière nginx (voir `docs/nginx/2st_implementation/README.md`).
