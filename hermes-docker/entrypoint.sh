#!/bin/bash
# ============================================================================
# Hermes Agent - Entrypoint Docker
# ============================================================================
set -e

# S'assurer que hermes est dans le PATH
export PATH="/root/.local/bin:/usr/local/bin:$PATH"
export HERMES_HOME="${HERMES_HOME:-/root/.hermes}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🤖  Hermes Agent - Démarrage"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  HERMES_HOME : $HERMES_HOME"
echo "  Commande    : $@"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Charger les clés API depuis le fichier .env si présent
if [ -f "$HERMES_HOME/.env" ]; then
    echo "→ Chargement des variables depuis $HERMES_HOME/.env"
    set -a
    source "$HERMES_HOME/.env"
    set +a
fi

# Vérifier la configuration minimale
if [ -z "${ANTHROPIC_API_KEY:-}" ] && \
   [ -z "${OPENAI_API_KEY:-}" ] && \
   [ -z "${OPENROUTER_API_KEY:-}" ] && \
   [ -z "${GEMINI_API_KEY:-}" ]; then
    echo ""
    echo "⚠  ATTENTION : Aucune clé API détectée !"
    echo "   Créez le fichier : $HERMES_HOME/.env"
    echo "   Exemple de contenu :"
    echo "     ANTHROPIC_API_KEY=sk-ant-..."
    echo "     OPENAI_API_KEY=sk-..."
    echo "     OPENROUTER_API_KEY=sk-or-..."
    echo ""
fi

# Exécuter la commande passée en argument
exec "$@"
