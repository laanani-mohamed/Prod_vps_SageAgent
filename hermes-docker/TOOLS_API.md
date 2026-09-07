# 🤖 SageAgent — API Tools Reference pour Agent IA

> Ce fichier documente **chaque endpoint de l'API SageAgent** comme un **outil (tool)** utilisable directement par un agent IA (ex: Hermes).
> Pour chaque tool, tu trouveras : la méthode HTTP, l'URL, le corps JSON complet, et la structure de réponse.

---

## 🔗 Base URL

```
http://localhost:8000
```

> **Sous-application Telegram (sans auth JWT)** : `http://localhost:8000/telegram`
> Tous les endpoints existent aussi sous `/telegram/` **sans avoir besoin du header `Authorization`**.

Astuce : Pour que Hermes utilise les APIs sans avoir besoin du JWT, il doit appeler les endpoints sous /telegram/ (ex: http://localhost:8000/telegram/api/stock/availability) — ça bypass l'auth complètement.
---

## 🔑 Étape 0 — Authentification

> Si tu utilises la base URL `/telegram`, **saute cette étape**.
> Pour la base URL principale, tu dois d'abord obtenir un token JWT.

### TOOL : `auth_login`

```
POST /api/auth/token
Content-Type: application/x-www-form-urlencoded

username=mon_utilisateur&password=MonMotDePasse1
```

**Réponse :**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

Ajoute ensuite le header `Authorization: Bearer <access_token>` à toutes les requêtes.

---

### TOOL : `auth_refresh`

```
POST /api/auth/refresh
Content-Type: application/json
Authorization: Bearer <access_token>

{ "refresh_token": "eyJ..." }
```

---

### TOOL : `auth_logout`

```
POST /api/auth/logout
Content-Type: application/json
Authorization: Bearer <access_token>

{ "refresh_token": "eyJ..." }
```

---

## 📦 MODULE STOCK

> Champs communs à tous les endpoints stock :
> - `client_schema` *(requis)* : schéma PostgreSQL, ex: `"client_01"`
> - `source_type` : `"db_latest"` (défaut) ou `"archive"`
> - `snapshot_datetime` : requis si `source_type="archive"`, ex: `"2026-01-15T08:00:00"`
> - `limit` : nombre max de lignes (défaut : illimité)

---

### TOOL : `stock_availability`

**Vérifier la disponibilité et le stock d'articles**

```
POST /api/stock/availability
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source_type": "db_latest",
  "ar_ref": ["REF001", "REF002"],
  "search_terms": ["cable", "connecteur"],
  "fa_codefamille": ["ELECT"],
  "depot_ids": [1, 2],
  "with_financials": false,
  "by_depot": false,
  "ar_sommeil": 0,
  "limit": 100
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `ar_ref` | `list[str]` | Références article exactes |
| `search_terms` | `list[str]` | Mots-clés dans la désignation (OR) |
| `fa_codefamille` | `list[str]` | Codes famille |
| `depot_ids` | `list[int]` | Filtrer sur dépôts spécifiques |
| `with_financials` | `bool` | Ajouter prix achat et marge |
| `by_depot` | `bool` | Ventiler par dépôt |

**Réponse :**
```json
{
  "endpoint": "/api/stock/availability",
  "client_schema": "client_01",
  "source": "db_latest",
  "total_rows": 2,
  "columns": ["ar_ref", "ar_design", "qte_stock_totale"],
  "data": [{"ar_ref": "REF001", "ar_design": "Cable XLR", "qte_stock_totale": 150}],
  "warnings": []
}
```

---

### TOOL : `stock_details`

**Fiche technique détaillée d'un article**

```
POST /api/stock/details
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "ar_ref": ["REF001"],
  "ar_design": "cable",
  "fa_codefamille": [],
  "depot_ids": [],
  "source_type": "db_latest"
}
```

> ⚠️ Au moins `ar_ref` ou `ar_design` est obligatoire.

---

### TOOL : `stock_catalog`

**Recherche catalogue par attributs techniques**

```
POST /api/stock/catalog
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "ar_ref": [],
  "fa_codefamille": ["ELECT"],
  "depot_ids": [],
  "ar_nature": [2],
  "ar_type": [0],
  "ar_suivistock": [5],
  "only_available": true,
  "sort_by": "stock",
  "source_type": "db_latest"
}
```

Valeurs de référence :
- `ar_nature` : `0`=Composant, `1`=Pièce, `2`=Produit fini, `3`=Semi-fini
- `ar_type` : `0`=Standard, `1`=Gamme, `2`=Prestation, `3`=Location
- `ar_suivistock` : `0`=Aucun, `1`=Sérialisé, `2`=CMUP, `3`=FIFO, `4`=LIFO, `5`=Lot
- `sort_by` : `"stock"`, `"price"`, `"name"`

---

### TOOL : `stock_insights`

**Détection d'anomalies de stock**

```
POST /api/stock/insights
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "insight_type": "rupture",
  "threshold": null,
  "expiry_days": null,
  "dormant_days": 90,
  "fa_codefamille": [],
  "depot_ids": [],
  "source_type": "db_latest"
}
```

| `insight_type` | Description |
|----------------|-------------|
| `"rupture"` | Stock ≤ 0 |
| `"stock_bas"` | Stock < `threshold` (obligatoire) |
| `"dormant"` | Sans mouvement depuis `dormant_days` jours |
| `"sommeil"` | Articles désactivés |
| `"expiration"` | Lots expirant dans `expiry_days` jours (obligatoire) |
| `"jamais_vendu"` | Jamais vendus |

---

### TOOL : `stock_snapshot`

**État du stock à une date passée**

```
POST /api/stock/snapshot
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source_type": "archive",
  "snapshot_datetime": "2026-01-15T08:00:00",
  "ar_ref": ["REF001"],
  "fa_codefamille": [],
  "by_depot": false
}
```

> ⚠️ `source_type` DOIT être `"archive"` et `snapshot_datetime` est obligatoire.

---

### TOOL : `stock_compare`

**Comparer l'évolution du stock entre deux dates**

```
POST /api/stock/compare
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source_type": "archive",
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "ar_ref": [],
  "fa_codefamille": []
}
```

---

## 💸 MODULE TRANSACTIONS

---

### TOOL : `transactions_ventes`

**Requêter les ventes (domaine=0 forcé)**

```
POST /api/transactions/ventes
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source": {
    "type": "db_latest",
    "period": {
      "mode": "range",
      "start_date": "2026-01-01",
      "end_date": "2026-06-30"
    }
  },
  "filters": {
    "do_domaine": [0],
    "do_type": [6],
    "ar_ref": ["REF001"],
    "client_refs": ["CLT001"],
    "collaborateur_ids": [3]
  },
  "metrics": ["ca_ht", "ca_ttc", "quantite_vendue", "marge_brute", "nb_documents"],
  "group_by": ["ar_ref", "ct_num"],
  "output": {
    "format": "table",
    "limit": 1000
  }
}
```

**`source.period.mode` :**
| Valeur | Description |
|--------|-------------|
| `"none"` | Pas de filtre temporel |
| `"snapshot"` | Un snapshot à `snapshot_datetime` |
| `"range"` | Entre `start_date` et `end_date` |

**Métriques disponibles :**
`ca_ht`, `ca_ttc`, `ca_ht_net`, `quantite_vendue`, `prix_unitaire_moyen`, `montant_regle`, `marge_brute`, `nb_documents`

**Types documents vente (`do_type`) :**
`0`=Devis, `1`=BC, `2`=PL, `3`=BL, `4`=Retour, `5`=Avoir, `6`=Facture, `7`=Facture comptab.

---

### TOOL : `transactions_achats`

**Requêter les achats (domaine=1 forcé)**

```
POST /api/transactions/achats
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source": {"type": "db_latest", "period": {"mode": "range", "start_date": "2026-01-01", "end_date": "2026-06-30"}},
  "filters": {"do_domaine": [1], "do_type": [16]},
  "metrics": ["ca_ht", "nb_documents"],
  "group_by": ["ct_num"],
  "output": {"format": "table", "limit": 500}
}
```

**Types documents achat (`do_type`) :**
`10`=DA, `11`=PC, `12`=BC, `13`=BL, `14`=Retour, `15`=Avoir, `16`=Facture, `17`=Facture comptab.

---

### TOOL : `transactions_documents`

**Tous les documents (sans domaine forcé)**

```
POST /api/transactions/documents
Authorization: Bearer <token>
Content-Type: application/json
```

Même structure que `transactions_ventes`, mais sans domaine forcé.

---

## 📚 MODULE RÉFÉRENTIEL

> Champs communs : `client_schema`, `source_type`, `snapshot_datetime`, `limit`.

---

### TOOL : `referentiel_comptes_tiers`

**Rechercher clients, fournisseurs, salariés**

```
POST /api/referentiel/comptes-tiers
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source_type": "db_latest",
  "ct_num": ["CLT001"],
  "ct_intitule": "dupont",
  "ct_type": [0],
  "ct_sommeil": 0,
  "ct_identifiant": null,
  "ct_ville": "casa",
  "ct_qualite": "sarl",
  "ct_code_region": "SUD",
  "co_no_representant": 3,
  "cbcreation_from": "2026-01-01",
  "cbcreation_to": "2026-06-30",
  "limit": 100
}
```

| `ct_type` | Description |
|-----------|-------------|
| `0` | Client |
| `1` | Fournisseur |
| `2` | Salarié |
| `3` | Autre |

---

### TOOL : `referentiel_collaborateurs`

**Rechercher vendeurs, acheteurs, collaborateurs**

```
POST /api/referentiel/collaborateurs
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "co_no": [],
  "co_vendeur": 1,
  "co_acheteur": null,
  "co_nom": "ben",
  "co_prenom": "ali",
  "co_fonction": "directeur",
  "co_matricule": "MAT",
  "limit": 50
}
```

---

### TOOL : `referentiel_articles_detail`

**Fiche article enrichie avec stock et lots optionnels**

```
POST /api/referentiel/articles/detail
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "ar_ref": "REF",
  "ar_ref_exact": ["REF001", "REF002"],
  "ar_design": ["cable", "fil"],
  "ar_code_barre": null,
  "fa_codefamille": ["ELECT"],
  "ar_nature": [2],
  "ar_type": [0],
  "ar_suivistock": [5],
  "ar_sommeil": 0,
  "with_stock": true,
  "with_lots": true,
  "depot_ids": [1, 2],
  "limit": 200
}
```

Options d'enrichissement :
- `with_stock=true` → ajoute `qte_stock_totale`
- `with_lots=true` → ajoute `lots_actifs`, `lots_perimes`, `prochaine_peremption`

---

### TOOL : `referentiel_familles`

**Familles d'articles avec arborescence**

```
POST /api/referentiel/familles
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "fa_codefamille": [],
  "fa_intitule": "elec",
  "fa_type": [0, 2],
  "fa_central": "ELEC",
  "fa_suivistock": [],
  "with_articles_count": true,
  "with_articles_names": false
}
```

`fa_type` : `0`=Détail, `1`=Total, `2`=Centralisateur

---

### TOOL : `referentiel_lots_series`

**Traçabilité des lots et péremption**

```
POST /api/referentiel/lots-series
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "ar_ref": ["REF001"],
  "fa_codefamille": [],
  "ls_noserie": "LOT2026",
  "de_no": [],
  "only_active": true,
  "ls_lotepuise": null,
  "peremption_before": "2026-12-31",
  "peremption_after": null,
  "qte_restant_min": 10.0
}
```

> Colonne calculée : `jours_avant_peremption` (négatif = déjà périmé)

---

### TOOL : `referentiel_documents_entete`

**Entêtes de documents commerciaux**

```
POST /api/referentiel/documents-entete
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "do_domaine": [0],
  "do_type": [6],
  "do_piece": ["FA2026-001"],
  "do_tiers": ["CLT001"],
  "co_no": [3],
  "do_ref": null,
  "do_date": null,
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "do_totalttc_min": 1000.0,
  "do_totalttc_max": null,
  "montant_regle_unpaid": true,
  "limit": 500
}
```

> Colonne calculée : `reste_a_payer = DO_TotalTTC - DO_MontantRegle`

**`do_domaine` :** `0`=Vente, `1`=Achat, `2`=Stock, `3`=Ticket, `4`=Document interne

---

### TOOL : `referentiel_documents_ligne`

**Lignes de documents (niveau article)**

```
POST /api/referentiel/documents-ligne
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "do_domaine": [0],
  "do_type": [],
  "do_piece": ["FA2026-001"],
  "ar_ref": ["REF001"],
  "ct_num": ["CLT001"],
  "co_no": [],
  "dl_design": "cable",
  "pf_num": "PROJ2026-01",
  "do_date": null,
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "dl_qte_min": 5.0,
  "dl_montantht_min": 500.0,
  "dl_nonlivre": 1,
  "dl_valorise": null,
  "with_entete": true
}
```

> ⚠️ Si `with_entete=true`, un filtre fort est obligatoire (`do_piece`, `ar_ref`, `ct_num`, ou période).

---

### TOOL : `referentiel_stock_depot`

**Stock physique par article et par dépôt**

```
POST /api/referentiel/stock-depot
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "ar_ref": ["REF001"],
  "de_no": [1, 2],
  "fa_codefamille": ["ELECT"],
  "ar_suivistock": null,
  "ar_sommeil": null,
  "qte_min": 0.01,
  "qte_max": null,
  "only_rupture": false
}
```

> Colonnes calculées : `valeur_stock_achat`, `valeur_stock_vente`

---

### TOOL : `referentiel_reglements`

**Règlements et échéances**

```
POST /api/referentiel/reglements
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "do_domaine": [0],
  "do_type": [6],
  "do_piece": ["FA2026-001"],
  "rg_typereg": [],
  "date_from": "2026-01-01",
  "date_to": "2026-06-30"
}
```

---

### TOOL : `referentiel_types_tiers` *(GET)*

```
GET /api/referentiel/types-tiers
Authorization: Bearer <token>
```

Réponse : `{"0": "Client", "1": "Fournisseur", "2": "Salarié", "3": "Autre"}`

---

### TOOL : `referentiel_types_documents` *(GET)*

```
GET /api/referentiel/types-documents
Authorization: Bearer <token>
```

---

## 📊 MODULE BI — Dashboard & Rapports

---

### TOOL : `bi_dashboard`

**KPIs globaux (CA, Achats, Stock, Encours)**

```
POST /api/bi/dashboard
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source_type": "db_latest",
  "date_from": "2026-01-01",
  "date_to": "2026-06-30"
}
```

**Réponse (`kpis`) :**
```json
{
  "chiffre_affaires": 1250000.0,
  "ca_n_minus_1": 1100000.0,
  "ca_evolution_pct": 13.6,
  "total_achats": 750000.0,
  "valeur_stock": 320000.0,
  "encours_clients": 145000.0,
  "dettes_fournisseurs": 98000.0,
  "nb_clients_actifs": 87,
  "ca_evolution_monthly": [...]
}
```

---

### TOOL : `bi_dashboard_objectifs` *(GET)*

**Axes stratégiques et objectifs**

```
GET /api/bi/dashboard/objectifs?client_schema=client_01
Authorization: Bearer <token>
```

---

### TOOL : `bi_dashboard_analytique` *(GET)*

**KPIs analytiques (Marge, DSO, Taux retour, Taux conversion devis→BC)**

```
GET /api/bi/dashboard/analytique?client_schema=client_01&date_from=2026-01-01&date_to=2026-06-30
Authorization: Bearer <token>
```

**Réponse clés :**
```json
{
  "marge_brute": 420000.0,
  "taux_marge": 33.6,
  "dso_jours": 47.3,
  "taux_impayes": 4.2,
  "taux_retour": 1.8,
  "taux_conversion": 68.5,
  "top_clients": [...],
  "top_fournisseurs": [...],
  "top_familles": [...],
  "top_articles_par_famille": {}
}
```

---

### TOOL : `bi_rapport_ca`

**Rapport CA groupé**

```
POST /api/bi/rapport/ca
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source_type": "db_latest",
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "group_by": "mois",
  "limit": 1000
}
```

`group_by` : `"mois"`, `"client"`, `"famille"`, `"commercial"`, `"region"`

---

### TOOL : `bi_top_clients`

**Top N clients par CA**

```
POST /api/bi/top-clients
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source_type": "db_latest",
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "limit": 10
}
```

---

### TOOL : `bi_top_articles`

**Top N articles vendus**

```
POST /api/bi/top-articles
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source_type": "db_latest",
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "limit": 20,
  "fa_codefamille": ["ELECT"]
}
```

---

### TOOL : `bi_rapport_balance`

**Balance clients**

```
POST /api/bi/rapport/balance
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "client_schema": "client_01",
  "source_type": "db_latest"
}
```

---

## 🏗️ Structure de réponse standard

```json
{
  "endpoint": "/api/stock/availability",
  "client_schema": "client_01",
  "source": "db_latest",
  "total_rows": 42,
  "data": [{}],
  "message": null
}
```

---

## ⚡ Règles importantes pour l'agent

1. **Auth** : utilise `/telegram/...` pour bypasser le JWT, sinon appelle `auth_login` d'abord.
2. **`client_schema`** est toujours obligatoire — c'est l'identifiant du tenant (ex: `client_01`).
3. **Sources** :
   - `db_latest` → données temps réel
   - `archive` → snapshot horodaté (nécessite `snapshot_datetime`)
4. **Filtres vides** : liste vide `[]` ou `null` = pas de filtre = tout retourner.
5. **Colonnes calculées** :
   - `reste_a_payer` = TTC − Montant réglé
   - `jours_avant_peremption` (négatif = déjà périmé)
   - `valeur_stock_achat`, `valeur_stock_vente`
6. **Rate limiting** : max 5 logins/minute, 10 refresh/minute.
7. **Swagger** : `http://localhost:8000/docs`
