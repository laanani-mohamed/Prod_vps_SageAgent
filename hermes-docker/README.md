# 🤖 Hermes Agent - Installation Docker

> Agent IA open-source par [Nous Research](https://nousresearch.com)

## 📁 Structure des fichiers

```
/opt/hermes-docker/
├── Dockerfile          # Image Docker Ubuntu 22.04 + Hermes
├── docker-compose.yml  # Orchestration du conteneur
├── entrypoint.sh       # Script de démarrage
├── .env.example        # Modèle de configuration des clés API
└── .env                # Vos clés API (à créer, ne pas committer)
```

## 🚀 Démarrage rapide

### 1. Copier et configurer les clés API
```bash
cp .env.example .env
nano .env   # Remplissez vos clés API
```

### 2. Construire l'image Docker
```bash
docker build -t hermes-agent:latest .
```

### 3. Lancer avec Docker Compose (recommandé)
```bash
docker compose up -d
```

### 4. Se connecter au conteneur (mode interactif)
```bash
docker exec -it hermes-agent hermes
```

## 🔧 Commandes utiles

| Commande | Description |
|----------|-------------|
| `docker compose up --build` | Rebuild + démarrage |
| `docker compose down` | Arrêt du conteneur |
| `docker compose logs -f` | Voir les logs |
| `docker exec -it hermes-agent bash` | Shell dans le conteneur |
| `docker exec -it hermes-agent hermes` | Lancer Hermes |

## 📦 Volumes persistants

Les données Hermes (sessions, config, logs) sont stockées dans le volume Docker `hermes-agent-data`, monté sur `/root/.hermes` dans le conteneur.

Pour inspecter les données :
```bash
docker volume inspect hermes-agent-data
```

## 🔑 Clés API supportées

Hermes supporte plusieurs fournisseurs — au moins une clé est nécessaire :
- **Anthropic** : `ANTHROPIC_API_KEY`
- **OpenAI** : `OPENAI_API_KEY`
- **OpenRouter** : `OPENROUTER_API_KEY`
- **Gemini** : `GEMINI_API_KEY`

## 🔄 Mise à jour

Pour mettre à jour Hermes vers la dernière version :
```bash
docker exec -it hermes-agent hermes update
# OU reconstruire l'image
docker compose build --no-cache && docker compose up -d
```
