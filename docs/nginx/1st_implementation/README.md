# Implémentation 1 — Base testable (reverse proxy nginx, un sous-domaine/port par client)

## Objectif

Poser une base fonctionnelle qui prouve que "un client = un sous-domaine = un port dédié via
nginx" fonctionne, **sans dépendre du vrai nom de domaine ni d'un vrai certificat TLS** (pas
encore reçus). Domaine placeholder utilisé partout : **`sageagent.test`** (TLD réservé par
l'IANA pour les tests locaux, jamais routable sur Internet — zéro risque de collision).

Clients concernés (5) : `cross`, `rousseau`, `mms`, `muliparts`, `client_01`.

## Contrainte rencontrée : pas d'accès root depuis cette session

La session qui a préparé cette implémentation n'a **pas d'accès sudo** sur le serveur
(`sudo -n` échoue, aucune règle passwordless). Toutes les commandes qui suivent (install
nginx, écriture dans `/etc/`, `systemctl`) doivent donc être exécutées **par vous**, avec
votre mot de passe sudo. Tout est préparé pour que ce soit une seule commande :

```bash
sudo bash /opt/SageAgent/docs/nginx/1st_implementation/install_phase1.sh
```

Le détail de ce que fait ce script, étape par étape, est ci-dessous.

## Décision volontaire : le service de production existant n'est pas touché

Le service historique `SageAgent_dashbi.service` (port 8505, tourne déjà en prod, lié sur
`0.0.0.0` donc accessible publiquement tel quel aujourd'hui) **n'est pas modifié** par cette
implémentation. Les 5 nouveaux clients tournent sur des **ports neufs (8506-8510)**, en
parallèle, sans aucun risque de casser l'accès actuel. La bascule/retrait éventuel de
l'ancien service se fera à la mise en prod réelle (voir `2st_implementation`).

Autre écart avec la discussion initiale : pas besoin de toucher au pare-feu (`ufw`) pour
cette phase de test — `ufw` n'est actuellement pas actif sur ce serveur (aucune règle ne
bloque rien), donc les nouveaux ports/nginx sont testables tels quels. Le durcissement
pare-feu est repoussé à la phase 2 (au moment de la bascule finale), voir la note dédiée
dans `2st_implementation`.

## Étapes réalisées (et où en trouver le contenu exact)

| # | Étape | Fichier(s) préparé(s) | Utilité |
|---|-------|------------------------|---------|
| 1 | Fichiers d'environnement par client (port dédié) | [`service/clients/cross.env`](/opt/SageAgent/service/clients/cross.env), `rousseau.env`, `mms.env`, `muliparts.env`, `client_01.env` — chacun contient une ligne `PORT=850X` | Sépare la config réseau (le port) du code : chaque instance Streamlit lit son port via `EnvironmentFile` systemd, sans dupliquer l'unit. |
| 2 | Unit systemd **templatée** (une instance par client) | [`service/sageagent-dashbi@`](/opt/SageAgent/service/sageagent-dashbi@) → installée en `/etc/systemd/system/sageagent-dashbi@.service` | Une seule définition de service sert à N clients (`sageagent-dashbi@cross`, `sageagent-dashbi@rousseau`, ...) ; ajouter un client ne demande pas une nouvelle unit, juste un nouveau `.env`. Reprend les réglages du service prod existant (`User=ubuntu`, même chemin `.venv`), avec en plus `--server.address=127.0.0.1` : chaque instance n'écoute qu'en local, jamais exposée directement sur Internet. |
| 3 | Map nginx sous-domaine → port | [`nginx/sageagent_clients.conf`](/opt/SageAgent/nginx/sageagent_clients.conf) → `/etc/nginx/conf.d/sageagent_clients.conf` | Table de correspondance `client.sageagent.test → port local`. Ajouter un client = ajouter une ligne ici, pas un bloc nginx entier. **Doit obligatoirement avoir l'extension `.conf`** : `nginx.conf` ne charge que `conf.d/*.conf` — un fichier `.map` y est silencieusement ignoré (erreur rencontrée et corrigée lors de la 1ère installation, voir section "Incident" plus bas). |
| 4 | Site nginx (reverse proxy) | [`nginx/sageagent.conf`](/opt/SageAgent/nginx/sageagent.conf) → `/etc/nginx/sites-available/sageagent.conf` (activé via lien symbolique dans `sites-enabled/`) | Un seul bloc HTTPS générique (grâce à la map) : redirige `http→https`, termine le TLS, proxy vers `127.0.0.1:<port>`, avec les en-têtes WebSocket nécessaires à Streamlit (`Upgrade`/`Connection`) et un garde-fou `404` pour tout sous-domaine inconnu. |
| 5 | Certificat TLS auto-signé | généré directement sur le serveur dans `/etc/nginx/ssl/sageagent-selfsigned.{crt,key}` (pas versionné dans git — une clé privée ne doit jamais être commitée) | Permet de tester tout le pipeline HTTPS + WebSocket de bout en bout dès maintenant. Le navigateur affichera un avertissement "certificat non fiable" à accepter une fois ; `curl` doit utiliser `-k`. Remplacé par un vrai certificat en phase 2. |
| 6 | Résolution de noms de test | entrées ajoutées dans `/etc/hosts` du serveur (`127.0.0.1 cross.sageagent.test`, etc.) | Fait résoudre les sous-domaines de test sans DNS réel. Pour tester depuis un autre poste (navigateur), il faut ajouter les mêmes noms dans le `/etc/hosts` de CE poste, pointant vers l'IP publique du serveur (`51.255.161.55`) — indiqué en fin de script. |
| 7 | Registre des ports clients | ajouté directement dans [`data_Client/reference/auth.json`](/opt/SageAgent/data_Client/reference/auth.json) (champ `"port"` sur chaque client) | Garde une seule source de vérité déjà existante (identifiants + schema client) à jour avec le port attribué à chacun. **Note** : `CLIENT_01` n'existait pas dans ce fichier — l'entrée a été créée par analogie avec les 4 autres (même mot de passe par défaut `Azerty123!`, même structure) ; à vérifier/changer si ce n'est pas le bon identifiant pour ce client. |

## Table des ports attribués

| Client | Sous-domaine (test) | Port | Schema (`auth.json`) |
|--------|----------------------|------|------------------------|
| cross | cross.sageagent.test | 8506 | cross |
| rousseau | rousseau.sageagent.test | 8507 | rousseau |
| mms | mms.sageagent.test | 8508 | mms |
| muliparts | muliparts.sageagent.test | 8509 | multipart |
| client_01 | client_01.sageagent.test | 8510 | client_01 |

(8505 = service de production existant, non touché. 8000 = API FastAPI partagée, inchangée. 8585 = dashboard interne `dashboard_ops`, hors périmètre.)

## Comment tester après avoir lancé `install_phase1.sh`

Depuis le serveur :
```bash
sudo ss -tlnp | grep -E ':850[6-9]|:8510'      # les 5 instances doivent écouter en 127.0.0.1 uniquement
curl -k -I https://cross.sageagent.test         # doit répondre 200
curl -k -I https://inconnu.sageagent.test       # doit répondre 404
sudo nginx -t                                   # doit dire "syntax is ok" / "test is successful"
```
Puis, dans un navigateur (après avoir ajouté les entrées `/etc/hosts` sur le poste utilisé,
voir tableau ci-dessus) : ouvrir `https://cross.sageagent.test`, accepter l'avertissement de
certificat, se connecter avec les identifiants du client `CROSS` (`data_Client/reference/auth.json`)
et confirmer que le dashboard s'affiche normalement.

## Incident rencontré et corrigé (1ère installation)

Lors du premier lancement de `install_phase1.sh`, l'étape 6 (config nginx) a échoué :
```
nginx: [emerg] unknown "sageagent_port" variable
nginx: configuration file /etc/nginx/nginx.conf test failed
```
**Cause** : le fichier de map avait été nommé `sageagent_clients.map`. Or
`/etc/nginx/nginx.conf` ne charge que `include /etc/nginx/conf.d/*.conf;` — un nom se
terminant en `.map` est silencieusement ignoré, donc la directive `map $host $sageagent_port`
n'était jamais lue, et `sites-enabled/sageagent.conf` référençait une variable inexistante.

**Correctif** : le fichier a été renommé [`nginx/sageagent_clients.conf`](/opt/SageAgent/nginx/sageagent_clients.conf)
(même contenu, extension `.conf`). Le script `install_phase1.sh` a été mis à jour pour
nettoyer l'ancien fichier mal nommé et installer le bon. Les étapes 1 à 5 (nginx installé,
env files, unit systemd, les 5 instances Streamlit démarrées, certificat auto-signé généré)
s'étaient déroulées sans erreur avant ce point et n'ont pas eu besoin d'être refaites — le
script est conçu pour être relancé sans risque (chaque étape ne refait que ce qui manque).

## Ce qui n'est PAS fait dans cette phase (volontairement)

- Pas de vrai nom de domaine, pas de vrai certificat Let's Encrypt.
- Pas de modification du service de production existant (port 8505).
- Pas de changement de pare-feu (`ufw`) — inutile pour le test, prévu en phase 2.

Tout cela est traité dans `docs/nginx/2st_implementation/`.
