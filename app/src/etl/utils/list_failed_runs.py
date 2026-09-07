import os
import json
import sys
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from config.etl_config import STORAGE_ROOT

STATE_DIR = os.path.join(STORAGE_ROOT, "storage_srv", "state")

def get_folders_to_scan(filter_type, start_date=None, end_date=None):
    if not os.path.exists(STATE_DIR):
        return []
    
    all_folders = [f for f in os.listdir(STATE_DIR) if os.path.isdir(os.path.join(STATE_DIR, f))]
    valid_folders = []

    for folder in all_folders:
        try:
            folder_date = datetime.strptime(folder, "%Y-%m-%d").date()
        except ValueError:
            continue # Ignore les dossiers qui ne respectent pas le format AAAA-MM-JJ (ex: .DS_Store)
        
        if filter_type == 1: # Date précise
            if folder_date == start_date:
                valid_folders.append(folder)
        elif filter_type == 2: # Intervalle
            if start_date <= folder_date <= end_date:
                valid_folders.append(folder)
        else: # Tout (3)
            valid_folders.append(folder)
            
    return sorted(valid_folders)

def main():
    print("=== Outil d'Analyse des Runs ETL en Échec ===")
    print("1: Date précise")
    print("2: Intervalle de dates")
    print("3: Scanner toutes les dates (défaut)")
    
    choix = input("Choisissez une option de filtrage : ").strip()
    
    filter_type = 3
    start_date, end_date = None, None
    
    try:
        if choix == "1":
            filter_type = 1
            date_str = input("  Entrez la date (AAAA-MM-JJ) : ").strip()
            start_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        elif choix == "2":
            filter_type = 2
            start_str = input("  Entrez la date de début (AAAA-MM-JJ) : ").strip()
            end_str = input("  Entrez la date de fin (AAAA-MM-JJ) : ").strip()
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            if start_date > end_date:
                print("\n[!] Erreur : La date de début doit être antérieure ou égale à la date de fin.")
                sys.exit(1)
        elif choix in ("3", ""):
            filter_type = 3
        else:
            print("\n[!] Option invalide. Utilisation du scan total par défaut.")
    except ValueError:
        print("\n[!] Format de date invalide. Veuillez utiliser le format AAAA-MM-JJ.")
        sys.exit(1)

    folders_to_scan = get_folders_to_scan(filter_type, start_date, end_date)
    
    if not folders_to_scan:
        print("\nAucun dossier d'état correspondant aux critères de date n'a été trouvé.")
        sys.exit(0)

    failed_runs = []

    for folder in folders_to_scan:
        folder_path = os.path.join(STATE_DIR, folder)
        for filename in os.listdir(folder_path):
            if not filename.endswith('.json'):
                continue
                
            filepath = os.path.join(folder_path, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    
                if state.get("status") == "FAILED":
                    failed_runs.append({
                        "run_id": state.get("run_id", "N/A"),
                        "client": state.get("client", "N/A"),
                        "error_code": state.get("error_code", "N/A"),
                        "current_step": state.get("current_step", "N/A"),
                        "finished_at": state.get("finished_at", "N/A")
                    })
            except Exception:
                # Lecture seule: ignorer silencieusement les fichiers JSON corrompus ou invalides
                pass

    print("\n")
    if not failed_runs:
        print("Aucun run ETL en échec détecté")
    else:
        # Affichage du tableau
        print(f"| {'Run ID':<36} | {'Client':<15} | {'Étape':<15} | {'Code Erreur':<25} | {'Date de Fin':<26} |")
        print("-" * 131)
        for run in failed_runs:
            print(f"| {run['run_id']:<36} | {run['client']:<15} | {run['current_step']:<15} | {str(run['error_code']):<25} | {run['finished_at']:<26} |")
        
        print(f"\n=> Total des erreurs détectées : {len(failed_runs)}")

if __name__ == "__main__":
    main()
