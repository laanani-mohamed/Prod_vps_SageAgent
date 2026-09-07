import os
import re
import argparse

def clean_null_values(folder_path):
    """
    Parcourt tous les fichiers du dossier et remplace les mots textuels 'NULL' 
    par des vides afin que PostgreSQL les interprète correctement lors du COPY.
    """
    if not os.path.exists(folder_path):
        print(f"Le dossier {folder_path} n'existe pas.")
        return

    for filename in os.listdir(folder_path):
        filepath = os.path.join(folder_path, filename)
        
        if os.path.isfile(filepath):
            # Lire le fichier
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Remplace le mot entier 'NULL' par une chaîne vide
            # \b garantit qu'on ne coupe pas un mot qui s'appellerait par ex "MANUELLE"
            new_content = re.sub(r'\bNULL\b', '', content)
            
            # Réécrire si des changements ont été faits
            if content != new_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Fichier nettoyé : {filename}")
            else:
                print(f"Aucun changement nécessaire pour : {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nettoyer les 'NULL' textuels d'un dossier de fichiers TSV.")
    parser.add_argument("dossier", help="Chemin vers le dossier contenant les fichiers de données (ex: /opt/SageAgent/app/storage_srv/client_01)")
    
    args = parser.parse_args()
    clean_null_values(args.dossier)
