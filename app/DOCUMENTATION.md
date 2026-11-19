# SageAgent — Documentation de l'application (`app/`)

> Document de prise en main. Il suit **la même arborescence que `app/`** : chaque dossier a sa
> section, chaque fichier sa ligne (rôle + caractéristiques). Lisez d'abord les parties 1 à 4
> (vue d'ensemble, flux, démarrage, règles métier), puis consultez la partie 5 comme un plan
> du code.
>
> Sources : lecture du code (état du dépôt au 27/10/2026, commit `91d897c`) et graphe de
> dépendances produit par graphify (`/opt/SageAgent/.claude/graphify-out/`).

---

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Flux de données de bout en bout](#2-flux-de-données-de-bout-en-bout)
3. [Démarrer et exploiter l'application](#3-démarrer-et-exploiter-lapplication)
4. [Règles métier transverses](#4-règles-métier-transverses)
5. [Arborescence commentée de `app/`](#5-arborescence-commentée-de-app)
6. [Carte des dépendances (graphify)](#6-carte-des-dépendances-graphify)
7. [Autour de `app/` : dossiers du projet](#7-autour-de-app--dossiers-du-projet)
8. [Points d'attention et dette connue](#8-points-dattention-et-dette-connue)
9. [Recettes : tâches courantes](#9-recettes--tâches-courantes)

---

## 1. Vue d'ensemble

SageAgent est une plateforme de **Business Intelligence pour des clients qui utilisent l'ERP
Sage**. Chaque client exporte régulièrement 11 tables Sage en fichiers texte. La plateforme les
charge dans PostgreSQL (un schéma par client), puis les expose via une API et des tableaux de
bord.

L'application `app/` contient **6 briques**, qui partagent la même configuration et la même base :

| Brique | Dossier | Techno | Rôle | Lancement |
|---|---|---|---|---|
| **ETL** | `src/etl/` | Python, Polars, psycopg2 | Surveille les dépôts SFTP des clients, valide les fichiers et les charge dans PostgreSQL | service `SageAgent_etl` |
| **API BI** | `src/api/` | FastAPI, Uvicorn | Expose les données (stock, référentiel, transactions, KPIs, rapports), protégée par JWT | service `SageAgent_api` (port 8000) |
| **Dashboard BI « ITBORD »** | `src/dashboard_bi/` | Streamlit, Plotly | Interface des clients finaux : tableau de bord, fichiers de base, ventes/achats, stock, règlements, rapports | `SageAgent_dashbi` (8505) ou une instance par client `sageagent-dashbi@<client>` (8506 à 8511) |
| **Front ITBORD (nouveaux dashboards)** | `src/front/` | Next.js 16, React 19, TypeScript | Remplaçant du Dashboard BI : connexion, tableau de bord, fichier de base, ventes, achats, stock (+ plan des dépôts), règlements, les 9 rapports et « Passer bon de commande » (panier gardé dans le navigateur, PDF par l'API). Le navigateur ne parle qu'au front, qui appelle l'API côté serveur (jetons dans des cookies httpOnly) ; filtres et sélections dans l'URL, aucun calcul métier dans le front | service `SageAgent_front` (port 8504) |
| **Dashboard Ops** | `src/dashboard_ops/` | Streamlit | Outil **interne** : suivi des runs ETL, investigation d'erreurs, état des services, journal d'accès API, onboarding de nouveaux clients | lancement manuel (port 8585) |
| **Rapports planifiés** | `src/reporting/` | pandas, fpdf, openpyxl, SMTP | Génère les rapports PDF/Excel de chaque client et les envoie par email | `SageAgent_rapports.timer` (tous les jours à 07:00, heure du Maroc), fourni dans `service/` mais **pas encore installé** |

**Multi-client (« multi-tenant »)** : un client = un dossier SFTP `storage_srv/upload/<CLIENT>/`
= un schéma PostgreSQL `<client>` (le nom du dossier en minuscules) = un ou plusieurs utilisateurs
API dont `allowed_schemas` contient ce schéma. Clients actuels : `cross`, `rousseau`, `mms`,
`muliparts`, `client_01`, `health` (registre : `data_Client/reference/auth.json`).

---

## 2. Flux de données de bout en bout

```
 Client Sage ──SFTP──► /var/sftp/upload/<CLIENT>/  (bind mount) = storage_srv/upload/<CLIENT>/
                                   │
                    ┌──────────────▼──────────────┐
                    │ ETL  (src/etl)              │
                    │ watcher → queue → worker    │
                    │ validation ×3 → ingestion   │
                    └───┬─────────────┬───────────┘
          succès        │             │  échec
   storage_srv/archives/│             │storage_srv/error/<CLIENT>/<date>/
   <CLIENT>/<date>/     │             │+ ERREUR_<ts>.txt dans le dossier d'upload du client
                        ▼
              PostgreSQL : schéma <client> (11 tables Sage)
              + etl_events.pipeline_events (historique des runs)
              + auth.users / auth.audit_logs
                        │
                ┌───────▼────────┐        Redis (refresh tokens, blocklist)
                │ API FastAPI    │◄──────►
                │ :8000  (JWT)   │
                └───┬────────┬───┘
     HTTP + JWT     │        │  appel Python direct (sans HTTP ni JWT)
          ┌─────────▼──┐  ┌──▼──────────────────┐
          │ Dashboard  │  │ reporting/generate  │──► storage_srv/rapport/<CLIENT>/<date>/
          │ BI ITBORD  │  │ (timer 07:00)       │──► email Gmail aux destinataires
          └─────▲──────┘  └─────────────────────┘
                │  nginx : <client>.sageagent.test → port de l'instance du client
           utilisateur final

 Dashboard Ops (:8585) ──lit──► logs/, storage_srv/, systemctl, auth.audit_logs
                       ──écrit─► auth.json, auth.users, compte SFTP (onboarding)
```

### Le cycle de vie d'un dépôt client (ETL)

1. **Détection** (`watcher.py`, toutes les 15 s) : un dossier `upload/<CLIENT>/` est « prêt » quand
   ses fichiers n'ont pas bougé depuis 5 s **et** qu'il contient exactement 11 fichiers.
   Plus de 11 → rejet `TOO_MANY_FILES`. Moins de 11 depuis plus de 10 min → rejet `TIMEOUT`.
2. **Mise en file** (`queue_manager.enqueue`) : les fichiers sont déplacés immédiatement vers
   `storage_srv/queue/<CLIENT>__<AAAAMMJJ_HHMMSS>/`, ce qui libère le dossier SFTP.
3. **Dépilage** (à chaque « heartbeat », 10 dossiers max, ordre FIFO) : un compteur `.retries` est
   incrémenté à chaque tentative. Au 3ᵉ essai, le dossier est considéré « empoisonné » et déplacé dans
   `error/<CLIENT>_POISON_<ts>`.
4. **Traitement** (`pipeline_worker.process`), avec un `run_id` (UUID) par tentative :
   - validation des **noms** de fichiers → validation des **tailles** (pas de fichier à 0 octet) →
     validation du **schéma** (nombre de colonnes, types, NOT NULL, sur toutes les lignes) ;
   - **ingestion** en une seule transaction : `TRUNCATE … CASCADE` puis `COPY` table par table dans
     l'ordre des clés étrangères (remplacement complet des données du client) ;
   - **archivage** des fichiers horodatés vers `archives/` (succès) ou `error/` (échec).
5. **Traçabilité** : chaque étape écrit un événement dans `etl_events.pipeline_events` (repli :
   `storage_srv/events/events.jsonl`) et des logs JSON dans `logs/etl.log/<CLIENT>/<date>.log`.
   En cas d'échec lié aux données, un message lisible `ERREUR_<ts>.txt` est déposé dans le dossier
   d'upload du client.
6. **Erreur d'infrastructure** (base injoignable, TRUNCATE impossible) : le worker renvoie `False`
   et l'orchestrateur **arrête de dépiler** jusqu'au prochain heartbeat. Le dossier reste dans la
   file et sera retenté.

---

## 3. Démarrer et exploiter l'application

### Prérequis

- Python 3 avec un environnement virtuel `app/.venv` (`pip install -r requirements.txt`) ;
- PostgreSQL : un schéma par client avec les 11 tables Sage, plus les schémas `auth`
  (`users`, `audit_logs`) et `etl_events` (`pipeline_events`) ;
- Redis (tokens) ; sans Redis, l'API bascule sur un cache en mémoire (dev uniquement) ;
- une paire de clés RSA `/opt/SageAgent/certs/private.pem` et `public.pem` (signature des JWT) ;
- `STORAGE_ROOT` (défaut `/opt/SageAgent`) : racine de `storage_srv/`.

### Variables d'environnement

| Fichier | Variables | Utilisé par |
|---|---|---|
| `app/.env` | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | `config/db_config.py` (toutes les briques) |
| `app/.env` | `OPS_DASHBOARD_PASSWORD` | `dashboard_ops/ops_config.py` |
| `app/.env.mail` | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (mot de passe d'application Google) | `reporting/envoi.py` |
| environnement | `STORAGE_ROOT`, `API_URL` (défaut `http://localhost:8000`), `PRIVATE_KEY_PATH`, `PUBLIC_KEY_PATH` | ETL, dashboard BI, API |

### Commandes de lancement (depuis `/opt/SageAgent/app`)

```bash
# ETL
.venv/bin/python src/etl/orchestration/main.py

# API (Swagger : http://localhost:8000/docs)
.venv/bin/uvicorn api.main:app --app-dir src --host 0.0.0.0 --port 8000

# Dashboard BI (instance unique)
cd src/dashboard_bi && ../../.venv/bin/python -m streamlit run app.py --server.port 8505
# Dashboard BI (instance d'un client, derrière nginx)
.venv/bin/streamlit run src/dashboard_bi/app.py --server.port=8506 --server.address=127.0.0.1

# Front Next.js (Node 22 : /home/amohamed/.hermes/node/bin dans le PATH)
cd src/front && npm ci && npm run build && npm start      # http://<IP>:8504 ; développement : npm run dev

# Dashboard Ops (interne)
nohup .venv/bin/streamlit run src/dashboard_ops/app.py --server.port 8585 --server.headless true > /tmp/dashboard_ops.log 2>&1 &

# Rapports (génération et envoi immédiats)
.venv/bin/python src/reporting/generate.py
```

En production, ces commandes sont encapsulées dans les unités systemd de `/opt/SageAgent/service/`
(voir partie 7).

---

## 4. Règles métier transverses

Ces règles s'appliquent dans tous les calculs (API, dashboard, rapports). Respectez-les si vous
ajoutez un indicateur.

| Règle | Détail |
|---|---|
| **Chiffre d'affaires en HT** | Tout CA est calculé hors taxes (`do_totalht`). Exceptions en TTC : soldes/créances (encours, balance, reste à payer), DSO et module `transactions`. |
| **Commercial = celui de la pièce** | Le commercial d'une vente est `F_DOCENTETE.co_no` (pas celui de la fiche tiers). `co_no = 0` ou vide → « Non identifié ». Jointure ligne ↔ entête sur `(do_domaine, do_type, do_piece)`. |
| **Région = `ct_coderegion`** | La région d'un client vient de `F_COMPTET.ct_coderegion`, jamais de `ct_ville`. Vide → « NON RENSEIGNÉE ». |
| **Domaines Sage** (`do_domaine`) | 0 = Ventes, 1 = Achats, 2 = Stock. |
| **Types de documents** (`do_type`) | Ventes : 0 Devis, 1 BC, 2 Prépa. livraison, 3 BL, 4 Retour, 5 Avoir, **6 Facture, 7 Facture comptabilisée**. Achats : 10 à 17 (16/17 = factures). Stock : 20 à 23. |
| **Types de tiers** (`ct_type`) | 0 Client, 1 Fournisseur, 2 Salarié, 3 Autre. |
| **Avoirs** | Sage enregistre les avoirs dans les types facture avec des montants négatifs ; ils sont déduits automatiquement. Une évolution en % se calcule sur la valeur absolue de la période de référence. |
| **Évolution N-1** | Même période un an plus tôt (le 29 février devient le 28 février). |
| **Valeur du stock** | `Σ F_ARTSTOCK.as_montsto` (montant du stock Sage), vide → 0 ; prix de revient = valeur ÷ quantité. |
| **Coût de revient (marge)** | En cascade : prix de revient unitaire de la ligne → CMUP → prix d'achat article. |
| **Montants affichés** | Séparateur de milliers et 2 décimales partout (dashboard, PDF, Excel). |

Les 11 tables Sage chargées (référence détaillée des colonnes :
`data_Client/reference/Structure de la Base de donnee Interne.md`) :

| Table | Contenu |
|---|---|
| `F_COMPTET` | Comptes tiers (clients, fournisseurs…) |
| `F_COLLABORATEUR` | Collaborateurs (commerciaux, acheteurs) |
| `F_FAMILLE` | Familles d'articles |
| `F_ARTICLE` | Articles |
| `F_ARTSTOCK` | Stock par article et par dépôt |
| `F_LOTSERIE` | Lots / séries (péremption) |
| `P_UNITE` | Unités de vente |
| `F_DOCENTETE` | Entêtes de documents (devis, BC, BL, factures…) |
| `F_DOCLIGNE` | Lignes de documents |
| `F_REGLECH` | Règlements / échéances |
| `F_DEPOT` | Dépôts |

Format des fichiers : TSV (séparateur tabulation), **sans en-tête**, UTF-8 avec ou sans BOM,
colonnes **positionnelles** (l'ordre est défini dans `map_data/reference/columns_order_number.py`).

---

## 5. Arborescence commentée de `app/`

### 5.0 Vue d'ensemble

```
app/
├── .env, .env.mail, .token, .gitignore, .streamlit/   configuration locale et secrets
├── requirements.txt                                   dépendances Python
├── clean_nulls.py                                     script CLI historique (nettoyage des "NULL")
├── config/          configuration partagée (chemins, base, logs, rapports planifiés)
├── map_data/        référentiel fichier → table et ordre des colonnes Sage
├── logs/            logs JSON de l'ETL, rangés par client puis par date (généré)
├── utils/           scripts d'administration (création d'utilisateur, SFTP, migrations, purge)
└── src/
    ├── etl/             pipeline d'ingestion
    ├── api/             API FastAPI (auth, bi, stock, referentiel, transactions)
    ├── dashboard_bi/    application Streamlit des clients (ITBORD)
    ├── dashboard_ops/   application Streamlit interne d'observabilité
    ├── front/           nouveaux dashboards Next.js (proxy.ts : session ; app/ : une page par section ; components/ : menu, cadre, tableaux, graphiques ; lib/ : API, formats, paramètres d'URL)
    └── reporting/       mise en forme des rapports (API + tâche planifiée) et envoi par email
```

**Imports** : il n'y a pas de package installé. Chaque point d'entrée ajoute lui-même `app/` et
`app/src/` au `sys.path`. On importe donc `config.…`, `map_data.…`, `etl.…`, `api.…`,
`reporting.…`. Les dashboards ajoutent aussi leur propre dossier, ce qui explique les imports
locaux du type `from services.base import …` ou `from components.… import …`.

---

### 5.1 Racine de `app/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `.env` | Secrets de la base PostgreSQL et mot de passe du Dashboard Ops | Lu par `config/db_config.py` et `dashboard_ops/ops_config.py`. **Actuellement versionné dans git** (voir partie 8). |
| `.env.mail` | Identifiants SMTP Gmail pour l'envoi des rapports | Ignoré par git (règle `.env.*`). Lu par `reporting/envoi.py`. |
| `.token` | Jeton stocké en fichier | **N'est utilisé par aucun code.** Versionné dans git : à supprimer du dépôt. |
| `.gitignore` | Exclusions git propres à `app/` | Ignore `.venv/`, `__pycache__`, `*.log`, `.env.*`, `storage_srv`. Attention : `.env` (sans suffixe) **n'est pas** ignoré. |
| `.streamlit/config.toml` | Configuration Streamlit par défaut | Port 8505, mode headless, protection XSRF activée, télémétrie désactivée. Les commandes systemd forcent le port. |
| `requirements.txt` | Dépendances Python | psycopg2, polars, pyarrow, pandas, fastapi, uvicorn, openpyxl et fpdf (exports de l'API et des rapports planifiés), streamlit, plotly, httpx, tenacity, python-jose, passlib[bcrypt], slowapi, redis, pydantic-settings, watchdog. Contient aussi langgraph, langchain, mcp et pytest, qui ne sont **pas utilisés** pour l'instant (Agent BI prévu). Les dépendances du front sont dans `src/front/package.json`. |
| `clean_nulls.py` | Script CLI : remplace les mots `NULL` par du vide dans les fichiers d'un dossier | Historique. L'ETL utilise sa propre version, `src/etl/utils/null_cleaner.py`. Usage : `python clean_nulls.py <dossier>`. |
| `DOCUMENTATION.md` | Ce document | — |

---

### 5.2 `config/` — Configuration partagée

Point central : **toute valeur qui dépend de l'environnement est définie ici**, jamais dans les
modules métier. D'après graphify, `config.etl_config` est importé par 19 modules : c'est le 3ᵉ
nœud le plus central du code.

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `__init__.py` | Marque le package | Vide. |
| `etl_config.py` | Chemins et paramètres de l'ETL | `STORAGE_ROOT` (env), `UPLOAD_BASE_PATH`, `ARCHIVE_BASE_PATH`, `ERROR_BASE_PATH`, `REPORT_BASE_PATH`, `QUEUE_DIR` (tous sous `storage_srv/`) ; `LOGS_DIR`, `ETL_LOG_DIR`, `ETL_ERROR_LOG_DIR`, `CLIENT_MESSAGE_LOG_DIR` ; watcher : stabilité 5 s, scan 15 s, timeout 600 s, `MIN_EXPECTED_FILES` = 11 ; `MAX_QUEUE_LIMIT` = 10 ; rapports d'erreur client : préfixe `ERREUR_`, rétention 30 jours, `error_report_filename()`. |
| `db_config.py` | Connexion PostgreSQL | Charge `app/.env` et expose `DB_CONFIG` (host, port, database, user, password, `connect_timeout` = 10). Utilisé par l'ETL, l'API (pool), le dashboard Ops et les scripts. |
| `logging_config.py` | Logs JSON de l'ETL | `setup_logging()` (appelé une fois par `etl/orchestration/main.py`) : console (INFO+), `logs/etl.log/<CLIENT>/<date>.log` (INFO+) et `logs/etl_error.log/<CLIENT>/<date>.log` (ERROR+). Le client est lu dans `extra={"client": …}` ; sans client, les logs vont dans `_general`. `CustomJSONFormatter` écrit une ligne JSON par log, avec les champs `extra` (`run_id`, `step`, `error_code`…). |
| `rapports_config.py` | Rapports planifiés par client | `RAPPORTS_CLIENTS = {CLIENT: {"destinataires": [...], "rapports": [{"rapport": nom, "filtres": {...}}]}}`. La docstring en tête liste **tous les rapports, leurs filtres et leurs valeurs par défaut**. Les périodes relatives (`annee_en_cours`, `mois_en_cours`, `mois_precedent`, `annee_precedente`) sont calculées le jour de la génération. Clients configurés aujourd'hui : `CROSS`, `health`. |
| `dash_config.py` | Constantes d'un ancien dashboard (couleurs, types de documents, URL API) | **Non utilisé** : le dashboard BI lit sa propre copie, `src/dashboard_bi/config.py`. |

---

### 5.3 `map_data/` — Référentiel des fichiers Sage

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `__init__.py`, `reference/__init__.py` | Packages | Vides. |
| `reference/file_table_map.py` | Correspondance fichier ↔ table | `FILE_TABLE_MAP` : les 11 fichiers attendus (`F_COMPTET.txt` → `F_COMPTET`…). Sa longueur définit le nombre de fichiers attendu par le watcher. `INSERTION_ORDER` : ordre de chargement qui respecte les clés étrangères (`P_UNITE`, `F_COLLABORATEUR`, `F_COMPTET`, `F_DEPOT`, `F_FAMILLE`, `F_ARTICLE`, `F_ARTSTOCK`, `F_LOTSERIE`, `F_DOCENTETE`, `F_DOCLIGNE`, `F_REGLECH`). |
| `reference/columns_order_number.py` | Ordre exact des colonnes de chaque table | `COLUMNS_ORDER[table]` : liste ordonnée des colonnes PostgreSQL (les fichiers n'ont pas d'en-tête). `COLUMNS_COUNT` : nombre attendu. `COLONNES_FIN_AJOUTEES` : colonnes ajoutées en fin de table après coup (ex. `as_montsto`) et tolérées absentes dans les anciennes archives. **À modifier en même temps que la table PostgreSQL** si Sage ajoute une colonne. |

---

### 5.4 `logs/` — Journaux (générés, non versionnés)

| Chemin | Contenu |
|---|---|
| `etl.log/<CLIENT>/<AAAA-MM-JJ>.log` | Tous les logs ETL (INFO+), une ligne JSON par événement. `_general/` regroupe les logs sans client (démarrage, heartbeat). |
| `etl_error.log/<CLIENT>/<AAAA-MM-JJ>.log` | Uniquement les erreurs (ERROR+). |
| `message_client/<CLIENT>/<AAAA-MM-JJ>/ERREUR_*.txt` | Copie de chaque message d'erreur déposé chez le client (conservée même si le client supprime le fichier). |

Ces fichiers sont lus par le Dashboard Ops (`services/log_reader.py`, `run_status.py`). L'API et le
dashboard BI écrivent sur la sortie standard, donc dans `journalctl -u <service>`.

---

### 5.5 `utils/` — Scripts d'administration

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `auth/create_user.py` | Création d'un utilisateur de l'API | CLI interactive : nom d'utilisateur, mot de passe (`getpass`), schémas autorisés, rôles (défaut `vendeur`). La fonction `create_api_user()` hache le mot de passe (bcrypt) et fait l'`INSERT` dans `auth.users`. Elle est réutilisée par l'onboarding du Dashboard Ops. **Pour accéder aux endpoints métier, il faut le rôle `analyst`.** |
| `client_sftp/sftp_onboard.sh` | Création de l'accès SFTP d'un client | À lancer en root : `sudo SFTP_PASSWORD=… ./sftp_onboard.sh <client>`. Crée le groupe `sftp_users`, un utilisateur Linux sans shell, chrooté dans `/var/sftp/upload/<client>`, et ajuste `sshd_config`. Monte `/var/sftp/upload` sur `storage_srv/upload` (bind mount, ajouté à `/etc/fstab`) et donne l'accès au groupe `etl_watchers`. Appelé par le Dashboard Ops via une règle sudoers restreinte (`service/sudoers-sftp-onboard`). |
| `migrations/add_as_montsto.sql` | Migration : ajoute la colonne `as_montsto` à `f_artstock` | Idempotente (`ADD COLUMN IF NOT EXISTS`), boucle sur les schémas `cross`, `rousseau`, `muliparts`, `health`, `mms`. Exécution : `psql -d <base> -f add_as_montsto.sql`. **Pour un nouveau client, ajoutez son schéma dans la liste.** |
| `purge/purge_archives.py` | Purge des archives et erreurs de plus de 30 jours, avec un événement `ArchivePurged` | ⚠️ Calcule `storage_srv` à partir de `app/utils/`, donc vise `app/utils/storage_srv` et non le vrai stockage. Son import `etl.…` échoue aussi sans `PYTHONPATH=src`. La page « Services & stockage » du Dashboard Ops signale le problème. |
| `purge/purge_archives.sh` | Même purge en bash (`find -mtime +30`) | ⚠️ Vise l'ancien chemin `/opt/etl_sage/storage_srv`. |

> La seule purge qui pointe sur les bons chemins est `src/etl/utils/purge_archives.py`, car elle
> utilise `config/etl_config.py`. Voir partie 8.

---

### 5.6 `src/etl/` — Pipeline d'ingestion

Point d'entrée : `orchestration/main.py`. Toute la configuration vient de
`config/etl_config.py` et `map_data/`. Les logs passent par `config/logging_config.py`.

#### `src/etl/orchestration/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `main.py` | **Orchestrateur** (boucle infinie) | Consomme le générateur `watch()`. Selon le statut reçu : `TIMEOUT` ou `TOO_MANY_FILES` → événement + archivage en erreur + rapport client ; `READY` → `enqueue()` ; `HEARTBEAT` → dépile `get_queue(10)` et appelle `process()` sur chaque dossier, en s'arrêtant au premier `False` (panne d'infrastructure). |
| `event_store.py` | **Event sourcing** des runs | `append_event(run_id, client, event_type, payload)` : `INSERT` dans `etl_events.pipeline_events`, avec repli dans `storage_srv/events/events.jsonl` si la base est indisponible. `get_events(run_id)` relit l'historique. `rebuild_state(run_id)` reconstruit l'état courant (réducteur). Jamais d'`UPDATE` ni de `DELETE`. La liste des types d'événements est dans la docstring. |
| `pipeline_state.py` | Couche de compatibilité | `init_state`, `update_step`, `fail_state`, `complete_state` délèguent à `event_store` (événements `RunInitialized`, `PipelineFailed`, `PipelineCompleted`…). `PipelineCompleted` sert à l'API pour afficher la « dernière mise à jour ». |

#### `src/etl/watcher/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `watcher.py` | Détection des dépôts | Scrute `UPLOAD_BASE_PATH` toutes les 15 s (scrutation périodique, pas inotify). Ignore les fichiers cachés et les `ERREUR_*`. Émet `(dossier, client, statut)` avec le statut `READY`, `TOO_MANY_FILES`, `TIMEOUT` ou `HEARTBEAT` (à chaque tour). |

#### `src/etl/broker/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `queue_manager.py` | File d'attente sur disque | `enqueue()` déplace le **contenu** (pas le dossier, pour préserver les droits SFTP) vers `storage_srv/queue/<CLIENT>__<ts>/`. `get_queue(limit)` : FIFO par tri alphabétique ; compteur `.retries` ; au bout de 3 essais → `error/<CLIENT>_POISON_<ts>` (file de rejet). |

#### `src/etl/worker/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `pipeline_worker.py` | Traitement d'un dossier de la file | `process(folder, client)` enchaîne validation des noms → tailles → schéma → ingestion → archivage, en émettant les événements à chaque étape. Renvoie `True` pour une erreur de données (le dossier part en erreur et on continue) et `False` pour une erreur d'infrastructure (on arrête de dépiler). Purge les `ERREUR_*` de plus de 30 jours du dossier d'upload. |

#### `src/etl/validation/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `__init__.py` | Description du package | Liste les 3 validateurs. |
| `val_files_names.py` | Présence des fichiers attendus | Compare aux clés de `FILE_TABLE_MAP`, sans tenir compte de la casse. Erreur : `INVALID_INPUT_FILES`. |
| `val_files_sizes.py` | Aucun fichier vide | Rejette tout fichier de 0 octet (`EMPTY_FILES`). Un fichier qui ne contient qu'un BOM passe : l'ingestion insère alors une ligne NULL de repli. |
| `val_schema_quality.py` | Qualité des données (le plus gros module de l'ETL, ~770 lignes) | Pour chaque fichier : nettoyage préalable (`sage_cleaner`), schéma attendu lu dans `information_schema`, puis 3 phases qui s'arrêtent à la première erreur et portent sur **toutes les lignes** : (1) nombre de colonnes, (2) compatibilité des types (via Polars, `PG_TYPE_MAP`, avec tolérance des formats français), (3) contraintes NOT NULL. Renvoie le détail (table, colonne, lignes) pour le rapport client. Erreur : `SCHEMA_QUALITY_FAILED`. |

#### `src/etl/ingestion/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `ingestor.py` | Chargement dans PostgreSQL | `ingest()` (décoré par `@db_retry(3, 5 s)`) : nettoie les `NULL` textuels, ouvre **une seule transaction**, `SET search_path` sur le schéma du client (en minuscules), désactive les clés étrangères (`session_replication_role = replica`), `TRUNCATE … CASCADE` des tables, puis `COPY` dans l'ordre `INSERTION_ORDER` (le BOM est sauté). Ajoute les lignes techniques `f_collaborateur.co_no = 0` (« Aucun Collaborateur ») et `f_article.ar_ref = 'NULL'`. `ROLLBACK` en cas d'échec, avec le code d'erreur : `DB_CONNECTION_FAILED` et `TRUNCATE_FAILED` (infrastructure) ; `FK_VIOLATION`, `DATA_TYPE_ERROR` et `COPY_FAILED` (données). |

#### `src/etl/archive/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `archiver.py` | Rangement après traitement | `archive_folder(folder, client, success, run_id)` déplace chaque fichier vers `archives/<CLIENT>/<date>/` ou `error/<CLIENT>/<date>/` en le renommant `<NOM>_<AAAAMMJJ_HHMMSS>.txt`. Écrit dans le log la volumétrie (lignes, colonnes, taille) de chaque fichier, pour qu'elle survive à la purge. Supprime le dossier temporaire de la file. **Les archives servent aussi de source « snapshot » à l'API** (`source_type = "archive"`). |

#### `src/etl/reporting/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `error_report.py` | Message d'erreur pour le client | `write_error_report()` écrit `ERREUR_<ts>.txt` en français simple dans `upload/<CLIENT>/`, avec une copie dans `logs/message_client/`. N'interrompt jamais le pipeline. `purge_old_error_reports()` applique la rétention de 30 jours. |
| `investigate_error.py` | Investigation d'un fichier en erreur, à la demande | Sans dépendance à Streamlit. Copies **volontairement séparées** des validateurs, en mode « collecter toutes les erreurs » au lieu de s'arrêter à la première. Retrouve le fichier archivé, relit les lignes fautives, compare le nombre de colonnes, refait le cast de la colonne en cause et contrôle les NOT NULL. Point d'entrée : `build_investigation_report()`, utilisé par le Dashboard Ops. |

#### `src/etl/utils/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `db_safe.py` | Sécurité SQL et reprise | `validate_identifier()` (noms de schéma et de table sûrs), `safe_search_path()`, `safe_truncate()`, `safe_copy()` (identifiants entre guillemets, `COPY … FROM STDIN` en mode texte, séparateur tabulation, NULL = ''). Décorateur `db_retry()` : réessaie sur perte de connexion PostgreSQL. |
| `sage_cleaner.py` | Correction des exports Sage, modifie le fichier sur place | Fusionne les tabulations excédentaires dans la colonne texte ciblée ; normalise les décimaux français (`10592,23` → `10592.23`) et les dates `JJ/MM/AAAA` ; tronque les décimaux tombés dans une colonne entière (ex. `co_no = 204.1`) ; supprime une ligne d'en-tête ajoutée par erreur (cas MULIPARTS). |
| `null_cleaner.py` | Remplace les mots `NULL` par du vide | Appelé au début de `ingest()`. |
| `file_stats.py` | Volumétrie d'un fichier | `file_stats(path)` → `{fichier, lignes, colonnes, taille}`. Partagé par l'archiveur et le Dashboard Ops. |
| `purge_archives.py` | Purge des archives et erreurs de plus de 30 jours | Utilise les bons chemins (`etl_config`). Prévu pour cron ; aucune tâche planifiée n'est livrée pour l'instant. |
| `grep_run_id_logs.py` | Recherche des logs d'un `run_id` (CLI) | **Obsolète** : lit `logs/etl.log` comme un fichier unique alors que c'est désormais un dossier par client et par date. Le Dashboard Ops le remplace. |

---

### 5.7 `src/api/` — API FastAPI

**Architecture de chaque module métier** (stock, référentiel, bi) :

```
router.py      → déclare l'endpoint, impose le rôle analyst, appelle secured_handle()
service.py     → répartiteur : endpoint → use case
use_cases/     → orchestre : repository (données brutes) → business_logic → schéma de réponse
business_logic/→ calculs purs en Polars (aucun accès base ni fichier)
repositories/  → factory_repo.py choisit l'implémentation selon source_type :
                   "db_latest" → pg_repo/      (SQL sur PostgreSQL, valeur par défaut)
                   "archive"   → archive_repo/ (fichiers de storage_srv/archives, snapshot
                                               le plus proche de snapshot_datetime)
schemas.py     → modèles Pydantic des requêtes et réponses
```

Toutes les requêtes métier portent un `client_schema` (validé par l'expression
`^[a-zA-Z0-9_]+$`). Le schéma demandé doit figurer dans les `allowed_schemas` du JWT, sinon → 403.

#### Fichiers du noyau `src/api/`

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `__init__.py` | Package | Vide. |
| `main.py` | **Point d'entrée** de l'API | Ajoute `src/` et `app/` au `sys.path`. Au démarrage (`lifespan`), ouvre le pool de connexions et le thread d'audit ; il les ferme à l'arrêt. Configure CORS (`ALLOWED_ORIGINS`), le limiteur slowapi et les routeurs `auth`, `stock`, `transactions`, `referentiel`, `bi`. Monte une **sous-application `/telegram`** qui reprend les mêmes routeurs **sans JWT** (utilisateur fictif `telegram_agent`, tous les schémas). Expose `GET /` (liste d'endpoints, en partie obsolète) et `GET /health`. Swagger : `/docs`, ReDoc : `/redoc`. |
| `db.py` | Pool de connexions PostgreSQL | `ThreadedConnectionPool` (1 à 20 connexions). `get_db()` est une dépendance FastAPI ; `get_db_connection()` est un gestionnaire de contexte pour les repositories (`rollback` automatique en cas d'erreur). |
| `_base_router.py` | Garde commune à tous les endpoints métier | `secured_handle(service_func, endpoint, request, current_user, client_schema, …)` : contrôle d'accès au schéma (403 et audit `ACCESS_DENIED`), injection de `client_schema` et `endpoint` si la fonction les attend, audit `API_CALL` avec la durée, et traduction des erreurs (`FileNotFoundError` → 404, toute autre erreur → 500 générique). |
| `rate_limiter.py` | Limitation de débit | slowapi. La clé est l'IP réelle (`CF-Connecting-IP` > `X-Forwarded-For` > `X-Real-IP` > IP directe). Les appels `/telegram` reçoivent une clé aléatoire, ce qui les exempte de la limite. |

#### `src/api/auth/` — Authentification et audit

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `__init__.py` | Package | — |
| `config.py` | Paramètres d'authentification (`AuthSettings`, pydantic-settings) | JWT **RS256** signé avec `certs/private.pem` et vérifié avec `public.pem` ; access token 30 min, refresh token 7 jours ; `ALLOWED_ORIGINS` ; `REDIS_HOST`/`REDIS_PORT` (IP en dur par défaut). Sans clé, le service plante au démarrage (comportement sûr par défaut), sauf si `ENV=development` (HS256 factice). |
| `schemas.py` | Modèles Pydantic | `Token`, `RefreshTokenRequest`, `UserInDB` (username, hashed_password, allowed_schemas, roles, is_active), `TokenData` (username, roles, allowed_schemas). |
| `service.py` | Logique des tokens | bcrypt (`passlib`) ; `create_access_token` (sub, roles, schemas, jti, type `access`) ; `create_refresh_token` (jti stocké dans Redis : `refresh:<jti>`) ; `verify_access_token` (vérifie aussi la blocklist `access:blocklist:<jti>`) ; fonctions de révocation. `_DUMMY_HASH` protège contre les attaques temporelles sur un utilisateur inexistant. |
| `router.py` | Endpoints `/api/auth/*` | `POST /token` (formulaire OAuth2, 5 requêtes/min), `POST /refresh` (rotation : l'ancien refresh token est consommé de façon atomique avec `GETDEL` ; une réutilisation donne 401, 10 requêtes/min), `POST /logout` (révoque les deux tokens). Chaque action est auditée. |
| `dependencies.py` | Dépendances FastAPI | `get_current_user` (Bearer → `TokenData`, sinon 401) et `require_role(*roles)` (sinon 403). |
| `redis_client.py` | Client Redis | Connexion à partir de `auth_settings`. Repli `LocalMemoryCache` en mémoire, sans expiration, réservé au développement. |
| `audit.py` | Journal d'audit asynchrone | `log_audit_event(...)` place l'événement dans une file thread-safe ; un thread de fond l'insère dans `auth.audit_logs`. Démarré et arrêté par `main.py`. Consulté par la page « Accès API » du Dashboard Ops. |

#### `src/api/common/` — Utilitaires partagés

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `pg_executor.py` | Exécuteur SQL générique | `execute_query(builder_fn, req, schema, logger, prefix)` : appelle `builder_fn(req, schema)` → `(sql, params, alias)`, exécute avec le pool et renvoie `List[dict]`. Les modules métier l'utilisent via leur fichier `pg_repo/_executor.py`. |
| `cache.py` | Cache en mémoire des chargements lourds (`memo(schema, cle, calcul)`, `vider(schema)`) | Gardé jusqu'au prochain passage de l'ETL du client (vidé par `prechauffage.py`, et chaque nuit), 25 h au plus ; 300 entrées au plus (les moins récemment utilisées sont retirées) ; un seul calcul à la fois par clé. Clé = client + requête complète (dont `co_no`) : pas de mélange entre clients ni profils. Utilisé par `bi/vues.py` (tables du référentiel, alertes, valeur du stock), les rapports, le tableau de bord et l'analytique. Vidé au redémarrage de l'API, puis rempli aussitôt par le préchauffage. |
| `prechauffage.py` | Fil lancé au démarrage de l'API (`lifespan` de `main.py`) | Toutes les minutes, pour chaque client des comptes actifs déjà passé par l'ETL : si sa dernière ingestion (`etl_events.pipeline_events`, `PipelineCompleted`) ou la date du jour a changé, vide son cache puis rend les 24 pages par défaut du front (`FRONT_URL`, défaut `http://127.0.0.1:8504`) avec un jeton directeur interne (utilisateur `prechauffage` dans l'audit). Le premier clic d'un directeur est ainsi déjà en cache ; un collaborateur (filtré sur son `co_no`) calcule au premier clic. |
| `archive_tsv.py` | Lecture d'un fichier d'archive Sage | `read_archive_tsv(contenu, colonnes)` (Polars, tout lu en texte, `NULL`/'' → null). Tolère l'absence des colonnes de `COLONNES_FIN_AJOUTEES` dans les anciennes archives. |

#### `src/api/bi/` — Tableau de bord et rapports (`/api/bi`)

Endpoints (tous `analyst`) :

| Méthode et chemin | Use case | Ce qu'il renvoie |
|---|---|---|
| `POST /dashboard` | `dashboard_uc` | 4 KPIs : CA HT (et N-1), achats, stock, encours, évolution mensuelle |
| `GET /dashboard/last-update` | `last_update_uc` | Date du dernier `PipelineCompleted` du client (insensible à la casse) |
| `GET /dashboard/objectifs` | `objectifs_uc` | Axes stratégiques et objectifs calculés |
| `GET /dashboard/analytique` | `analytique_uc` | Marge brute, DSO, taux d'impayés, de retour, de conversion devis → facture, tops clients, fournisseurs, familles, articles par famille |
| `POST /rapport/ca` | `rapport_ca_uc` | CA HT groupé par mois, client, région ou commercial |
| `POST /top-clients` / `POST /top-articles` | `top_clients_uc` / `top_articles_uc` | Top N par CA HT |
| `POST /rapport/balance` | `balance_uc` | Balance client : À nouveau, un mois par colonne, En cours, Total (filtre par commercial) |
| `POST /rapport/balance-agee` | `balance_agee_uc` | Encours par tranche d'ancienneté en jours |
| `POST /rapport/visite-client` | `rapport_visite_uc` | Rapport « avant visite » en 7 sections : BC en cours, factures impayées, articles par mois (6 mois glissants), familles actives, dormantes ou jamais achetées, CA N vs N-1 |
| `POST /rapport/valeur-stock` | `valeur_stock_uc` | Σ `as_montsto` par dépôt, famille et article |
| `POST /rapport/consommation` | `consommation_uc` | Consommation par article (colonnes mois en cours + M1 à M6, total, moyenne mensuelle calculée sur les 6 mois complets) et récapitulatif par famille ; les lignes à zéro sont exclues |
| `POST /stats-tiers` | `stats_tiers_uc` | Statistiques d'un client (`ct_type=0`) ou d'un fournisseur (`ct_type=1`) sur une période, comparée à N-1 |
| `POST /vues/{nom}` | `api/bi/vues.py` | Données prêtes à afficher des pages du front (filtrées, totalisées, paginées par 50) : `reglements`, `documents`, `document`, `compteurs`, `articles` (une ou plusieurs familles), `article`, `tiers`, `clients` (codes et noms, liste de choix du bon de commande), `depots`, `familles`, `stock_etat`, `stock_alertes`, `plan_depots`. Reprend les calculs pandas des pages Streamlit en passant par les services existants. Collaborateur : ses documents ; stock, achats, fournisseurs → 403 |
| `POST /bon-commande` | `api/bi/vues.bon_commande` | PDF d'un bon de commande client (page « Passer bon de commande ») : client, lignes (référence, quantité, remise %) et remise globale saisis ; prix de vente, désignation et famille relus dans Sage ; totaux HT, TVA 20 % et TTC, mêmes colonnes que la page 9 de Streamlit. Rien n'est écrit en base. Client ou article inconnu → 400. Directeur et collaborateur |
| `POST /rapports/{nom}?format=json\|pdf\|xlsx` | `reporting/generate.construire` | Les 9 rapports de l'onglet Rapports, mis en forme par `reporting/rapports.py` (même résultat que la tâche planifiée) : sections (`colonnes`, `lignes`), `totaux` (ligne Total), `repartition` (valeur par dépôt, ancienneté des dormants), ou le fichier PDF / Excel. `filtres` = clés de `config/rapports_config.py` (inconnu ou invalide → 400). Collaborateur : ses chiffres ; rapports de stock → 403 |

| Fichier / dossier | Rôle | Caractéristiques |
|---|---|---|
| `__init__.py` | Package | — |
| `router.py` | Déclaration des 15 endpoints ci-dessus | Chacun passe par `secured_handle`. |
| `schemas.py` | Modèles Pydantic | `BaseBIRequest` (`client_schema`, `source_type` = `db_latest` par défaut, `snapshot_datetime`), une requête par rapport, `RapportResponse` (enveloppe générique `data` + métadonnées), `DashboardResponse`, `KpiAnalytiqueResponse`… Importé par 14 modules (nœud central d'après graphify). |
| `service.py` | Répartiteur | Une fonction `get_*` par endpoint, qui appelle `<use_case>.execute(req)`. **Également appelé directement par `reporting/generate.py`.** |
| `use_cases/*.py` | Un fichier par endpoint (13 fichiers) | Orchestration repository → calculs → réponse. `rapport_visite_uc.py` (le plus gros) et `consommation_uc.py` contiennent les tableaux croisés articles × mois glissants. `balance_agee_uc.py` réutilise le repository de `balance_uc.py`. |
| `business_logic/kpi_calculations.py` | KPIs du tableau de bord | CA (factures de vente type 6, domaine 0), CA N-1, évolution sur 6 mois, encours, dettes fournisseurs (16/17), achats, clients actifs. |
| `business_logic/analytique_calculations.py` | KPIs analytiques | DSO, impayés (> 1 MAD restant), retours, conversion, marge brute avec coût en cascade, tops. |
| `business_logic/rapport_calculations.py` | Rapports CA et tops | Filtres de période, regroupements (mois, client, commercial, **région = `ct_coderegion`**), jointures tiers et collaborateur, ratios (facture moyenne, % du CA). Détecte aussi le « mode archive » (`do_type` toujours à 0). |
| `business_logic/balance_calculations.py` | Balances | `calculate_balance_client` (colonnes par mois) et `calculate_balance_agee` (tranches en jours). |
| `business_logic/stats_tiers_calculations.py` | Statistiques d'un tiers | Montant net HT, nombre de factures et d'avoirs, taux d'avoir, facture moyenne, série mensuelle N vs N-1, répartitions (famille, article, commercial), prix moyen payé par article (fournisseur). |
| `repositories/base_bi_repo.py` | Interface abstraite `BaseBIRepository` | `fetch()` renvoie des données brutes. Hérité par 16 classes. |
| `repositories/factory_repo.py` | `get_bi_repo(resource, source_type)` | Ressources disponibles dans les deux modes : `dashboard`, `analytique`, `rapport_ca`, `top_clients`, `top_articles`. Les autres rapports ne lisent que PostgreSQL. |
| `repositories/pg_repo/_executor.py` | Délègue à `common/pg_executor` | — |
| `repositories/pg_repo/sql_helpers.py` | Construction des clauses SQL | `validate_schema`, `add_in`/`add_eq`/`add_gte`/`add_lte`, `add_date_range`, `sage_vente_filter`, `sage_achat_filter`. |
| `repositories/pg_repo/bi_*_repo.py` | Requêtes SQL par rapport | `bi_dashboard_repo`, `bi_analytique_repo`, `bi_rapport_ca_repo` (+ tiers et collaborateur), `bi_top_clients_repo`, `bi_top_articles_repo`, `bi_balance_repo` (factures + tiers, commercial de la pièce), `bi_visite_client_repo` (7 jeux de données d'un `do_tiers`), `bi_valeur_stock_repo`, `bi_consommation_repo`, `bi_stats_tiers_repo` (une méthode par jeu de données). |
| `repositories/archive_repo/base_bi_archive.py` | Accès aux archives pour la BI | `get_bi_archive_dir`, `find_bi_snapshot`, `load_bi_table`, `safe_float_col`. S'appuie sur le loader du module référentiel. |
| `repositories/archive_repo/bi_*_archive.py` | Variantes « archive » | Pour dashboard, analytique, rapport CA, top clients, top articles. |

#### `src/api/stock/` — Stock (`/api/stock`)

| Endpoint | Use case | Ce qu'il fait |
|---|---|---|
| `GET /health` | — | Vérification de santé du module |
| `POST /availability` | `availability_uc` | Stock et disponibilité d'un ou plusieurs articles (option par dépôt), avec avertissement pour les références introuvables |
| `POST /details` | `article_details_uc` | Fiche détaillée d'un article (libellés lisibles) |
| `POST /catalog` | `catalog_search_uc` | Recherche catalogue par attributs |
| `POST /insights` | `stock_insight_uc` | Alertes : rupture, stock bas, dormant avec stock, lots proches de la péremption |
| `POST /snapshot` | `stock_snapshot_uc` | État du stock à une date passée (**archive uniquement**) |
| `POST /compare` | `stock_compare_time_uc` | Écart de stock entre deux dates (archive ↔ archive, ou archive ↔ base) |

| Fichier / dossier | Rôle | Caractéristiques |
|---|---|---|
| `router.py`, `service.py`, `schemas.py` | Même organisation que le module BI | `service.RESOURCE_HANDLERS` fait la correspondance endpoint → use case. Les requêtes héritent de `BaseStockRequest`. La réponse `StockResponse` porte `data`, `source` et `warnings`. |
| `use_cases/*.py` | 6 use cases | Voir le tableau ci-dessus. |
| `business_logic/aggregations.py` | Agrégations Polars | Par article, par article et dépôt, catalogue, fiche détaillée. |
| `business_logic/alerts.py` | Détection d'alertes | `detect_stock_alerts(type, seuil)` et `detect_expiring_lots(jours)`. |
| `business_logic/comparison.py` | Comparaison dans le temps | `calculate_time_delta` (gère la division par zéro). |
| `business_logic/valuations.py` | Données financières unitaires | `add_unit_financials`. |
| `business_logic/source_meta.py` | Métadonnées de réponse | Source (`db_latest` ou `archive:<ts>`), références demandées mais absentes. |
| `repositories/base_repo.py`, `factory_repo.py` | Interface et factory | `RESOURCE_MAP` : `availability`, `details`, `catalog`, `insight`, `snapshot`, `compare` × `db_latest`/`archive`. |
| `repositories/pg_repo/*` | SQL | `stock_snapshot_repo` et `stock_compare_repo` lèvent `NotImplementedError` (pas d'historique dans la base « live »). `sql_helpers.py` et `_executor.py` reprennent le même modèle que les autres modules. |
| `repositories/archive_repo/*` | Lecture des archives | `base_archive.py` (~200 lignes) charge et joint les fichiers du snapshot ; les autres fichiers sont de petites spécialisations. |

#### `src/api/referentiel/` — Données de référence (`/api/referentiel`)

| Endpoint | Table principale | Particularités |
|---|---|---|
| `POST /comptes-tiers` | `F_COMPTET` | 10 filtres, 20 colonnes |
| `POST /collaborateurs` | `F_COLLABORATEUR` | Filtres vendeur, acheteur, recherche ILIKE sur le matricule |
| `POST /articles/detail` | `F_ARTICLE` | Options `with_stock`, `with_lots` ; marge catalogue |
| `POST /familles` | `F_FAMILLE` | Option `with_articles_count` |
| `POST /lots-series` | `F_LOTSERIE` | Jours avant péremption, `only_active` |
| `POST /documents-entete` | `F_DOCENTETE` | `reste_a_payer = TTC − réglé` calculé |
| `POST /documents-ligne` | `F_DOCLIGNE` | Option `with_entete` ; volume limité pour ménager la mémoire |
| `POST /stock-depot` | `F_ARTSTOCK` | `valeur_stock` calculée (`as_montsto`) |
| `POST /reglements` | `F_REGLECH` | Règlements et échéances enrichis |
| `POST /date-range` | `F_DOCENTETE` | Dates min et max de `do_date` (bornes des filtres de date du dashboard) |
| `GET /types-tiers`, `GET /types-documents` | — | Dictionnaires `CT_Type` et `DO_Type` |

| Fichier / dossier | Rôle | Caractéristiques |
|---|---|---|
| `router.py` (~400 lignes), `service.py`, `schemas.py` (~470 lignes) | Même organisation que les autres modules | `BaseReferentielRequest` (`client_schema`, `source`, `limit`) et une requête par ressource. Réponse `ReferentielResponse`. |
| `use_cases/*_uc.py` | 10 use cases courts | Repository → enrichissements → sérialisation. |
| `business_logic/enrichments.py` | Calculs purs | `add_reste_a_payer`, `add_valeur_stock`, `add_jours_avant_peremption`, `add_marge_catalogue`. |
| `business_logic/serializers.py` | Conversion JSON | Decimal, date, etc. → types JSON. |
| `business_logic/validators.py` | Garde-fous | `require_filter`, `hard_limit`. |
| `repositories/base_repo.py` | Interface `BaseReferentielRepository` | **Nœud le plus importé du code (21 modules)** d'après graphify. |
| `repositories/factory_repo.py` | `get_repo(resource, source)` | Hub principal du graphe (31 liaisons). Toute nouvelle ressource s'enregistre ici. |
| `repositories/pg_repo/*_repo.py` | Une classe SQL par ressource | + `sql_helpers.py` et `_executor.py`. |
| `repositories/archive_repo/_loader.py` | Chargement des archives | `get_archive_dir`, `resolve_target_dt`, `find_closest_snapshot` (fichier `{TABLE}_{ts}.txt` le plus proche de la date demandée), `load_archive_file`, `require_snapshot`. **Réutilisé par le module BI.** |
| `repositories/archive_repo/*_archive.py` | Une classe « archive » par ressource | Même contrat que la version PostgreSQL. |

#### `src/api/transactions/` — Transactions (`/api/transactions`)

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `router.py` | `POST /ventes`, `POST /achats`, `POST /documents` | Rôle `analyst`, via `secured_handle`. |
| `schemas.py` | `TransactionsRequest` | `period`, `source` (`db_latest`/`archive`), `filters`, `output` (dimensions de regroupement, métriques). |
| `query_builder.py` | Générateur SQL dynamique | `build_select`, `build_joins`, `build_where`, `build_group_by` → `build_transactions_query`. Agrégations sur entêtes et lignes. **Montants en TTC** (exception à la règle du HT). |
| `service.py` | Exécution | `_from_db` (SQL) ou `_from_archive` (Polars sur le snapshot le plus proche). Message explicite si le résultat est vide. |

---

### 5.8 `src/dashboard_bi/` — Application des clients « ITBORD »

Application Streamlit multipage. **Elle ne parle jamais directement à la base** : tout passe par
l'API avec le JWT de l'utilisateur.

**Fonctionnement** : l'écran de connexion appelle `POST /api/auth/token`, garde `access_token` et
`refresh_token` dans `st.session_state`, puis décode le JWT pour fixer
`client_schema = schemas[0]` (**un utilisateur voit un seul client**, le premier de sa liste).
La navigation est déclarée dans `app.py` (`st.navigation`).

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `app.py` | Point d'entrée | Configuration de la page (titre « ITBORD »), CSS, formulaire de connexion, barre latérale, bouton de déconnexion (appelle `/api/auth/logout`), menu : Global, Fichier de Base, Transactions, Stock, Finance, Passer bon de commande. |
| `config.py` | Configuration du dashboard | `API_BASE_URL` (env `API_URL`), `SOURCE_TYPE = "db_latest"`, couleurs, types de documents et de tiers, pagination (500). |
| `api_client.py` | Alias de compatibilité | Réexporte `services.base`. |

#### `pages/`

| Fichier | Page | Contenu |
|---|---|---|
| `1_Tableau_de_Bord.py` | Tableau de Bord | KPIs (`/bi/dashboard`), indicateurs analytiques (`/bi/dashboard/analytique`), classements en onglets : Top Clients, Fournisseurs, Familles. |
| `2_Fichier_de_Base.py` | Fichier de Base | Onglets Articles (fiche, top clients, stock par dépôt et lot, évolution CA et marge), Clients et Fournisseurs (recherche + statistiques via `/bi/stats-tiers`), Dépôts, Familles. |
| `3_Gestion_Ventes.py` | Gestion Ventes | Délègue à `components/gestion_documents.py` (domaine 0) : un onglet par type de document + Archive. |
| `4_Gestion_Achats.py` | Gestion Achats | Même composant, domaine 1. |
| `5_Mouvements_Stock.py` | Stock & Mouvements | État des stocks, mouvements entrants et sortants (domaine 2) avec le détail des lignes, alertes et insights. |
| `6_Reglements.py` | Règlements | Encaissements clients et décaissements fournisseurs, avec le document associé. |
| `7_Rapports.py` | Rapports BI (le plus gros fichier, ~1 100 lignes) | 9 onglets : CA, Comparaison CA, Balance, Valeur du stock, Avant visite client, Produits dormants, Lots en péremption, Consommation par produit, Balance âgée. Chaque onglet a ses filtres, son tableau et ses boutons d'export **Excel / PDF**. La mise en forme est reproduite dans `reporting/rapports.py` : **toute modification doit être faite aux deux endroits.** |
| `8_Agent_BI.py` | Agent BI | Page vide (« en cours de développement — Phase 7 »). **Absente du menu.** |
| `9_Nouveau_Bon_Commande.py` | Passer bon de commande | Saisie d'un BC client en session (**aucune écriture en base**), TVA 20 %, récapitulatif PDF. Reprise dans le front : `/bon-de-commande` (PDF par `POST /api/bi/bon-commande`). |

#### `components/` — Éléments d'interface réutilisables

| Fichier | Rôle |
|---|---|
| `auth_guard.py` | `require_auth()` (renvoie vers la connexion), `require_api_health()`, `handle_auth_error()` (déconnexion propre sur `AuthError`). Importé par 9 modules. |
| `sidebar.py` | Barre latérale : titre `ITBORD-<schéma>`, date de dernière mise à jour des données. |
| `metrics.py` | Les 4 cartes KPI (`st.metric`). |
| `charts.py` | Graphiques Plotly : évolution du CA, top clients et articles, courbes, évolution produit (CA + marge). |
| `data_tables.py` | `show_df` / `show_table` : format numérique commun (milliers, 2 décimales, suffixe %), dates tronquées. |
| `date_filters.py` | Filtre de dates unique, borné aux dates réelles (`/referentiel/date-range`) et contrôlé (fin ≥ début). |
| `gestion_documents.py` | Rendu partagé des pages Ventes et Achats : filtres, onglets par type, détail de la pièce, libellé du commercial de la pièce. |
| `tiers_stats.py` | Affichage des statistiques d'un client ou fournisseur (cartes, graphique mensuel, tableaux). |
| `styles_initiale.py`, `styles_fichier_base.py`, `styles_sidebar.py` | CSS injectés (thème, cartes KPI, barres de défilement des tableaux). |
| `__init__.py` | Réexports. |

#### `services/` — Appels à l'API

| Fichier | Rôle |
|---|---|
| `base.py` | `APIClient` (singleton `httpx`, délai d'attente 60 s) : ajoute le Bearer, **rafraîchit le token automatiquement sur 401** (un seul essai, pour éviter une boucle), traduit les erreurs réseau ; `call_api` (POST), `call_api_get`, `check_api_health`. Utilise `tenacity`. |
| `bi_service.py` | `/api/bi/*` (KPIs, dernière mise à jour, objectifs, analytique, rapport CA, stats tiers, top clients) ; cache de 300 s. |
| `referentiel_service.py` | Articles, tiers, dépôts, familles, lots, collaborateurs. |
| `documents_service.py` | Entêtes et lignes de documents, bornes de dates, `commercial_label()` (0 → « Non identifié »), mise en forme ventes/achats. Importé par 11 modules. |
| `sales_service.py` | Calculs ventes, achats, CA net, mensuel, encours, clients actifs côté dashboard. |
| `stock_service.py` | Disponibilité, insights, mouvements entrants et sortants. |
| `reglements_service.py` | Règlements mis en forme. |
| `article_service.py` | Top clients d'un article, stock par dépôt et lot, KPIs article. |
| `tiers_service.py` | Recherche de tiers. |
| `depot_service.py` | Résumé des dépôts (nombre d'articles). |
| `top_client_service.py` | Top clients calculé à partir de `F_DOCENTETE`. |
| `__init__.py` | Réexports. |

#### `core/` et `utils/`

| Fichier | Rôle |
|---|---|
| `core/constants.py` | Énumérations Sage (domaine, types de documents, tiers, règlement), `TAUX_TVA = 20.0`. |
| `core/exceptions.py` | `DashboardError` → `APIError`, `AuthError`, `DataError`, `ValidationError`. |
| `core/formatters.py` | Formats monétaires (MAD, MMAD) et de dates (`JJ/MM/AAAA HH:MM`). |
| `core/validators.py` | `is_archive_mode`, `filter_factures`, `safe_float`. |
| `utils/cache.py` | Alias de `st.cache_data`. |
| `utils/exports.py` | Exports PDF/Excel : **réutilise `src/reporting/exports.py`** en ajoutant la ligne « Dernière mise à jour » du client. |

---

### 5.9 `src/dashboard_ops/` — Observabilité interne

Outil réservé à l'équipe, **à ne pas exposer aux clients**. Accès par un mot de passe partagé
(`OPS_DASHBOARD_PASSWORD`), sans JWT. Il lit directement les logs, le stockage, systemd et la base.

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `app.py` | Point d'entrée | Menu : **Observabilité** (Synthèse, Historique des runs, Investigation), **Exploitation** (Services & stockage, Accès API), **Administration** (Onboarding client). Les commandes d'arrêt et de relance sont dans la docstring. |
| `ops_config.py` | Configuration | Charge `app/.env` : `OPS_DASHBOARD_PASSWORD`, `PAGE_TITLE`. |
| `auth.py` | Écran de mot de passe | `require_auth()`, `logout_button()`. |

| `views/` | Page | Contenu |
|---|---|---|
| `0_Synthese.py` | Synthèse | Dépôts par jour et par client : succès, échecs, taille déposée. |
| `1_Runs.py` | Historique des runs | Runs d'un client pour un jour donné (statut, fichiers, volumétrie, message envoyé au client), avec l'investigation affichée sur place en cas d'échec. |
| `2_Investigation.py` | Investigation | Accès direct à l'analyse d'un fichier en erreur. |
| `3_Onboarding.py` | Onboarding client | Formulaire : compte SFTP (script via sudo), utilisateur API (`auth.users`), entrée dans le registre `auth.json` (prochain port libre proposé). |
| `4_Services.py` | Services & stockage | État des services systemd SageAgent, taille des files, disque, dossiers de `storage_srv`, **contrôle de la purge** (dernier `ArchivePurged`, chemin réellement visé par chaque script). |
| `5_Acces_API.py` | Accès API | Journal `auth.audit_logs` : compteurs par action, courbe journalière, détail filtrable. |

| `services/` | Rôle |
|---|---|
| `log_reader.py` | Liste des clients et dates présents dans `logs/etl.log/`, lecture des lignes JSON. |
| `run_status.py` | Regroupement des logs par `run_id` et calcul du statut (SUCCESS si archivé dans `/archives/`, FAILED si dans `/error/` ou en présence d'une ERROR, sinon RUNNING). |
| `run_volumes.py` | Volumétrie par fichier d'un run (lue dans le log d'archivage, sinon recalculée avec `file_stats`) et synthèse journalière. |
| `client_message.py` | Retrouve le `ERREUR_*.txt` envoyé au client pour un run. |
| `system_status.py` | `systemctl list-units/show` (lecture seule), files d'attente, disque, dossiers de stockage, état de la purge. |
| `audit_reader.py` | Requêtes SQL paramétrées sur `auth.audit_logs`. |
| `onboarding.py` | Lecture et écriture de `data_Client/reference/auth.json`, test SFTP, `provision_sftp()` (`sudo -n` + `SFTP_PASSWORD`), `create_db_user()` (réutilise `utils/auth/create_user.py`), `next_available_port()`. |

| `components/` | Rôle |
|---|---|
| `investigation_view.py` | Rendu de l'investigation (tableau par champ Sage) et du message envoyé au client. |
| `status_badge.py` | Badge coloré du statut d'un run. |
| `formatting.py` | `fmt_taille` (Ko/Mo), `fmt_entier` (séparateur de milliers). |

---

### 5.10 `src/reporting/` — Rapports planifiés et email

Génère **les mêmes rapports que l'onglet « Rapports BI » du dashboard**, sans Streamlit, pour
chaque client déclaré dans `config/rapports_config.py`. Les données passent directement par les
`service.py` de l'API, en Python, **sans HTTP ni JWT** : le script tourne sur le serveur.

| Fichier | Rôle | Caractéristiques |
|---|---|---|
| `generate.py` | Point d'entrée (`main`) | Ouvre le pool de connexions, puis pour chaque client : `_config_client` (contrôle de la configuration), `generate_report()` pour chaque rapport (données → `rapports.py` → `exports.py`), dépôt dans `storage_srv/rapport/<CLIENT>/<AAAA-MM-JJ>/<nom>.pdf/.xlsx/.json`. Un nom déjà utilisé le même jour devient `<nom>_2`. Le `.json` décrit les filtres, la période, la date et le nombre de lignes. Envoie ensuite les emails. **Code de sortie 1** si au moins un rapport échoue. Rapports disponibles : `chiffre_affaire`, `comparaison_ca`, `balance`, `balance_agee`, `valeur_stock`, `visite_client`, `produits_dormants`, `lots_peremption`, `consommation`. |
| `rapports.py` | Mise en forme | Classe `Rapport` (nom, titre, sous-titre, sections `[(libellé, DataFrame)]`, un PDF par section ou non) et une fonction par rapport. Reproduit la logique des onglets de `7_Rapports.py`. |
| `exports.py` | PDF et Excel | Excel (openpyxl) : vrais nombres au format `#,##0.00`, plusieurs feuilles possibles. PDF (fpdf) : nombres au format français, largeurs de colonnes proportionnelles, un tableau par section pour les rapports multi-sections. **Partagé avec le dashboard BI.** |
| `envoi.py` | Envoi des emails | SMTP SSL Gmail (`app/.env.mail`). **Un seul email par destinataire** avec tous les PDF et Excel du client. Le résultat (envoyé ou échec + erreur) est ajouté à la clé `"envois"` de chaque `.json`. `adresse_valide()` contrôle le format des adresses. |
| `__init__.py` | Package | — |

---

## 6. Carte des dépendances (graphify)

Le graphe `/opt/SageAgent/.claude/graphify-out/graph.json` (ouvrable dans `graph_viewer.html`)
compte 822 nœuds (236 modules, 119 classes, 409 fonctions) et 1 686 liens (dont 1 015 imports).
Pour le régénérer : `extract_graph.py` puis `analyze_graph.py`.

> ⚠️ Le graphe date du 30/09. Ce qui a été ajouté depuis n'y figure pas : `src/reporting/*`,
> `config/rapports_config.py`, la partie « stats-tiers » de l'API et du dashboard, les pages
> `dashboard_ops/views/*` et les services `audit_reader`, `run_volumes`, `system_status`. Relancez
> graphify pour le mettre à jour.

**Taille des groupes de modules** : `api.bi` 44, `api.referentiel` 43, `dashboard_bi` 42,
`api.stock` 33, `etl` 28, `dashboard_ops` 14, `api.auth` 8, `config` 5, `api.transactions` 5,
`map_data` 4, `api.core` 4, `api.common` 3, `utils` 2.

**Nœuds centraux**, à modifier avec précaution car beaucoup de modules en dépendent :

| Module | Liens | Pourquoi c'est central |
|---|---|---|
| `api.referentiel.repositories.factory_repo` | 31 | Enregistre toutes les implémentations PostgreSQL et archive |
| `api.referentiel.repositories.base_repo` | 21 entrants | Interface de tous les repositories du référentiel |
| `config.etl_config` | 19 entrants | Chemins de stockage utilisés par l'ETL, l'API, le dashboard Ops et les rapports |
| `api.stock.repositories.factory_repo` / `api.bi.repositories.factory_repo` | 20 / 18 | Factories des deux autres modules |
| `api.bi.repositories.base_bi_repo` | 16 entrants | Interface des repositories BI |
| `dashboard_bi.services.documents_service` | 15 | Service le plus utilisé par les pages |
| `api.bi.schemas` / `api.referentiel.schemas` | 14 / 12 entrants | Contrats des requêtes et réponses |
| `api.referentiel.repositories.archive_repo._loader` | 14 | Lecture des archives, partagée avec la BI |
| `dashboard_bi.components.auth_guard` | 11 entrants | Protège toutes les pages |

**Liens entre groupes** : le seul vrai couplage transversal est le stockage. `etl`, `api.stock`,
`api.referentiel`, `api.transactions` et `dashboard_ops` lisent tous `config.etl_config`, et
`map_data` est partagé par l'ETL (écriture) et l'API (lecture des archives). L'API passe toujours
par `api.auth` (via `_base_router`). Le dashboard BI n'importe aucun module de l'API en Python :
il passe uniquement par HTTP. Le graphe du 30/09 montre encore un import de `api.auth.config`,
supprimé depuis. `reporting` importe directement les `service.py` de l'API.

---

## 7. Autour de `app/` : dossiers du projet

| Dossier (`/opt/SageAgent/…`) | Rôle |
|---|---|
| `storage_srv/` (non versionné) | `upload/<CLIENT>/` (dépôts SFTP, bind mount de `/var/sftp/upload`), `queue/` (file d'attente de l'ETL), `broker_queue/` (ancienne file, vide), `archives/<CLIENT>/<date>/` (succès, sert aussi de snapshots à l'API), `error/<CLIENT>/<date>/` (échecs), `events/events.jsonl` (repli de l'event store), `rapport/<CLIENT>/<date>/` (rapports générés). |
| `service/` | Unités systemd à copier dans `/etc/systemd/system/` (mode d'emploi en bas de chaque fichier) : `SageAgent_etl`, `SageAgent_api` (port 8000), `SageAgent_front` (port 8504, nouveaux dashboards Next.js), `SageAgent_dashbi` (port 8505, instance unique), `sageagent-dashbi@` (une instance par client, port lu dans `/etc/sageagent/clients/<client>.env`, modèles dans `service/clients/*.env`), `SageAgent_rapports` + `.timer` (oneshot à 07:00, heure de `Africa/Casablanca`, `Persistent=true`), `sudoers-sftp-onboard` (permet à l'utilisateur du Dashboard Ops de lancer **uniquement** `sftp_onboard.sh` en root). |
| `nginx/` | Reverse proxy : `<client>.sageagent.test` → port local de l'instance du client (`map $host $sageagent_port` dans `sageagent_clients.conf`), HTTP → HTTPS. `README.md` explique les notions et la configuration ; `docs/nginx/` décrit les phases 1 (domaine de test) et 2 (vrai domaine). |
| `certs/` | Clés RSA de signature des JWT (`private.pem`, `public.pem`). |
| `data_Client/reference/` | `auth.json` : **registre des clients** (clé client → schéma, identifiant, rôle, port du dashboard), lu par `reporting/generate.py` et le Dashboard Ops. Description des tables Sage (`.md`, `.xlsx`, `db_struct.txt`). |
| `data_Client/files/` | Jeux de fichiers Sage d'exemple (`Client_test`, `muliparts`) pour les tests manuels. |
| `hermes/`, `hermes-docker/` | Agent IA externe (Hermes, Nous Research) en Docker, et documentation de ses outils API (`TOOLS_API.md`). Il consomme l'API via `/telegram`. Indépendant de `app/`. |
| `.claude/graphify-out/` | Graphe de dépendances (partie 6). |

**Ports utilisés** : API 8000 · Dashboard BI 8505 (instance unique) · par client : cross 8506,
rousseau 8507, mms 8508, muliparts 8509, client_01 8510, health 8511 · Dashboard Ops 8585 ·
Redis 6379 · PostgreSQL 5432.

---

## 8. Points d'attention et dette connue

Constatés à la lecture du code. À traiter avant ou pendant la reprise du projet.

**Sécurité**

1. **Secrets versionnés dans git** : `app/.env` (accès base + mot de passe Ops), `app/.token`,
   `certs/private.pem` (clé de signature des JWT), `data_Client/reference/auth.json` (contient des
   mots de passe) et `data_Client/shema_psw.txt` (d'après son nom, des mots de passe de schémas).
   Il faut les retirer de l'historique, **changer
   toutes ces valeurs** et ajouter ces fichiers au `.gitignore`.
2. **Sous-application `/telegram` sans authentification** : elle donne accès à toutes les
   données de tous les clients, sans limite de débit. Le code prévoit un secret en en-tête mais
   ne le vérifie pas. Il faut au minimum restreindre son accès réseau.
3. Le `REDIS_HOST` et les `ALLOWED_ORIGINS` contiennent une IP publique en dur
   (`api/auth/config.py`) : il vaut mieux les définir par variable d'environnement.

**Exploitation**

4. **Aucune purge des archives ne fonctionne** : `utils/purge/purge_archives.py` et `.sh` visent
   de mauvais chemins (§ 5.5), et rien ne lance la version correcte,
   `src/etl/utils/purge_archives.py` (pas de crontab pour `amohamed`, pas de timer). La page
   « Services & stockage » du Dashboard Ops le signale.
5. **Les rapports planifiés ne tournent pas encore** : `SageAgent_rapports.service` et `.timer`
   ne sont pas installés dans `/etc/systemd/system/`. Les unités ETL, API et dashboard le sont.
6. Le Dashboard Ops n'a pas de service systemd : il est lancé à la main avec `nohup`, sous
   l'utilisateur `amohamed`. La règle sudoers dépend de cet utilisateur. Les unités systemd
   utilisent `amohamed` ou `ubuntu` selon le fichier.
7. `utils/migrations/add_as_montsto.sql` contient une liste de schémas écrite en dur, à compléter
   pour chaque nouveau client.

**Code**

8. `requirements.txt` : il manque `tenacity` (importé par le dashboard BI) ; langgraph, langchain,
   mcp et pytest sont listés mais pas encore utilisés.
9. Code mort ou en double : `config/dash_config.py` (copie de `dashboard_bi/config.py`),
   `app/clean_nulls.py` (copie de `etl/utils/null_cleaner.py`), `etl/utils/grep_run_id_logs.py`
   (format de logs dépassé), `pages/8_Agent_BI.py` (absente du menu).
10. `GET /` de l'API liste des endpoints qui n'existent pas (`/api/analytics/*`,
   `/api/recouvrement/*`, `/api/performance/*`, `/ai/ask*`). Seul Swagger `/docs` fait foi.
11. La mise en forme des rapports existe en deux exemplaires (`dashboard_bi/pages/7_Rapports.py`
    et `reporting/rapports.py`) : chaque modification doit être reportée dans les deux.
12. Aucun test automatisé n'est présent dans `app/`.

---

## 9. Recettes : tâches courantes

### Ajouter un nouveau client

1. **Dashboard Ops → Onboarding → « Créer le schéma d'un client »** : crée le schéma PostgreSQL
   `<client>` et ses 11 tables vides (`utils/migrations/create_client_schema.sql`, en une transaction ;
   la cause est affichée en cas d'erreur). En ligne de commande : voir l'en-tête du fichier SQL.
2. **Dashboard Ops → Onboarding → « Ajouter un nouveau client »** : crée le compte SFTP, l'utilisateur
   API (profil `directeur`, ou `collaborateur` avec son identifiant `co_no` Sage) et l'entrée dans
   `auth.json` avec un port. En ligne de commande, l'équivalent est `sftp_onboard.sh` +
   `utils/auth/create_user.py`.
3. Dashboard dédié : copier `service/clients/<client>.env` (`PORT=…`) dans
   `/etc/sageagent/clients/`, puis `sudo systemctl enable --now sageagent-dashbi@<client>`.
4. nginx : ajouter la ligne `<client>.sageagent.test <port>;` dans `sageagent_clients.conf`,
   puis `sudo nginx -t && sudo systemctl reload nginx`.
5. (Facultatif) Rapports planifiés : ajouter une entrée dans `config/rapports_config.py`.
6. Test : déposer les 11 fichiers dans le dossier SFTP et suivre le run dans
   « Historique des runs ».

### Ajouter un rapport planifié à un client

Ajoutez `{"rapport": "<nom>", "filtres": {...}}` dans `RAPPORTS_CLIENTS["<CLIENT>"]["rapports"]`
(noms et filtres listés en tête de `config/rapports_config.py`). Pour tester tout de suite :
`sudo systemctl start SageAgent_rapports.service`, puis vérifiez `storage_srv/rapport/<CLIENT>/<date>/`.

### Ajouter un endpoint à l'API

1. `schemas.py` : modèle de requête (hérite de la requête de base du module) ;
2. `repositories/pg_repo/<x>_repo.py` (+ `archive_repo/` si besoin) et enregistrement dans `factory_repo.py` ;
3. `business_logic/` : calcul pur en Polars ;
4. `use_cases/<x>_uc.py` : `execute(req)` ;
5. `service.py` : fonction `get_<x>` ;
6. `router.py` : route avec `Depends(require_role("analyst"))` et `secured_handle(...)` ;
7. côté dashboard : fonction dans `dashboard_bi/services/` puis affichage dans une page.

### Une table Sage gagne une colonne

1. `ALTER TABLE` dans chaque schéma client (créer une migration dans `utils/migrations/`) ;
2. ajouter la colonne **à sa position** dans `COLUMNS_ORDER` (`map_data/reference/columns_order_number.py`) ;
3. si elle est ajoutée en fin de table, l'ajouter aussi à `COLONNES_FIN_AJOUTEES` pour que les
   anciennes archives restent lisibles ;
4. adapter l'export Sage côté client.

### Diagnostiquer un dépôt client en échec

Dashboard Ops → **Historique des runs** → choisir le client et la date → le run en échec affiche
l'étape, le code d'erreur, le message envoyé au client et l'investigation ligne par ligne.
Sans le Dashboard : `logs/etl_error.log/<CLIENT>/<date>.log`, les fichiers dans
`storage_srv/error/<CLIENT>/<date>/` et la table `etl_events.pipeline_events` (filtrer sur `run_id`).
