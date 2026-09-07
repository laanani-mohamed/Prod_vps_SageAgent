import os
import logging
from map_data.reference.columns_order_number import COLUMNS_COUNT

logger = logging.getLogger("etl.sage_cleaner")

# Dictionnaire de configuration : { 'nom_de_la_table': index_de_la_colonne_texte (0-indexed) }
# On cible les colonnes "désignation" / "intitulé" qui sont le plus sujettes aux tabulations accidentelles.
CLEANER_CONFIG = {
    "F_ARTICLE": 1,  # ar_design est la 2ème colonne (index 1)
}

def clean_sage_file(filepath: str, table_name: str, run_id: str = "N/A", client_schema: str = "N/A") -> int:
    """
    Lit le fichier TSV, détecte les lignes ayant trop de tabulations (colonnes),
    et tente de fusionner les colonnes excédentaires dans la colonne texte ciblée.
    Modifie le fichier sur place. Retourne le nombre de lignes corrigées.
    """
    expected_count = COLUMNS_COUNT.get(table_name)
    if not expected_count:
        return 0
        
    text_col_idx = CLEANER_CONFIG.get(table_name)
    if text_col_idx is None:
        return 0

    lines_fixed = 0
    try:
        # Lire avec encodage tolérant, Sage produit souvent des caractères spéciaux
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            
        fixed_lines = []
        for line in lines:
            if not line.strip():
                continue
                
            line_clean = line.rstrip('\r\n')
            cols = line_clean.split('\t')
            
            diff = len(cols) - expected_count
            
            if diff > 0:
                # Il y a des tabulations en trop
                # On fusionne la colonne texte avec les 'diff' colonnes suivantes
                end_idx = text_col_idx + diff
                
                # Fusionner et nettoyer (remplacer les multiples espaces par un seul)
                merged_text = " ".join(cols[text_col_idx : end_idx + 1])
                merged_text = " ".join(merged_text.split()) 
                
                # Reconstruire la liste des colonnes
                new_cols = cols[:text_col_idx] + [merged_text] + cols[end_idx + 1:]
                
                # Rendre la ligne avec tabulations
                fixed_lines.append("\t".join(new_cols) + "\n")
                lines_fixed += 1
            else:
                fixed_lines.append(line)
                
        # Si on a corrigé des lignes, on réécrit le fichier
        if lines_fixed > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(fixed_lines)
                
            logger.warning(
                f"[Nettoyage Auto] {lines_fixed} lignes avec tabulations excessives corrigées dans {table_name}.",
                extra={
                    "run_id": run_id,
                    "client": client_schema,
                    "table": table_name,
                    "step": "sage_cleaner"
                }
            )
            
        return lines_fixed

    except Exception as e:
        logger.error(
            f"[Nettoyage Auto] Erreur lors du nettoyage de {filepath}: {e}",
            extra={
                "run_id": run_id,
                "client": client_schema,
                "table": table_name,
                "step": "sage_cleaner"
            }
        )
        return 0
