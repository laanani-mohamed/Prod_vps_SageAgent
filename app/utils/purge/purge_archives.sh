#!/bin/bash
# Script de maintenance ETL : Purge automatique des dossiers de stockage
# Exécution recommandée : Quotidiennement via Cronjob

# Chemins absolus sur le serveur
BASE_DIR="/opt/etl_sage/storage_srv"
ARCHIVES_DIR="${BASE_DIR}/archives"
ERROR_DIR="${BASE_DIR}/error"

# Nombre de jours de rétention
RETENTION_DAYS=30

echo "Début de la purge des archives ETL (Rétention : ${RETENTION_DAYS} jours) - $(date)"

# Purge des archives réussies
if [ -d "$ARCHIVES_DIR" ]; then
    find "$ARCHIVES_DIR" -type f -mtime +${RETENTION_DAYS} -exec rm -f {} \;
    echo "Purge terminée pour $ARCHIVES_DIR"
else
    echo "Le dossier $ARCHIVES_DIR n'existe pas."
fi

# Purge des dossiers en erreur
if [ -d "$ERROR_DIR" ]; then
    find "$ERROR_DIR" -type f -mtime +${RETENTION_DAYS} -exec rm -f {} \;
    echo "Purge terminée pour $ERROR_DIR"
else
    echo "Le dossier $ERROR_DIR n'existe pas."
fi

echo "Purge terminée avec succès - $(date)"
