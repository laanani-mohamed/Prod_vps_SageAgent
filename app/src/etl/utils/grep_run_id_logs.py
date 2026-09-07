import os
import sys
import json

def grep_logs(run_id):
    # Remonte au dossier racine depuis etl/utils/
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logs_dir = os.path.join(project_root, "logs")
    
    # Fichiers possibles (on peut ajouter une boucle pour lire les logs rotatifs .log.1, .log.2 si nécessaire à l'avenir)
    # Dans les consignes, seul etl.log et etl_error.log sont explicités
    log_files = [os.path.join(logs_dir, "etl.log"), os.path.join(logs_dir, "etl_error.log")]
    
    extracted_logs = []
    
    for log_file in log_files:
        if not os.path.exists(log_file):
            continue
            
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if record.get("run_id") == run_id:
                        extracted_logs.append(record)
                except json.JSONDecodeError:
                    # Sécurité si une ligne n'est pas au format JSON pur
                    continue
    
    # Assurer l'ordre chronologique attendu  (tri via le timestamp)
    extracted_logs.sort(key=lambda x: x.get("timestamp", ""))
    
    # Affichage unique sans modification
    for log in extracted_logs:
        print(json.dumps(log, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_run_id = sys.argv[1]
    else:
        target_run_id = input("Veuillez saisir le run_id à rechercher : ").strip()
        
    if not target_run_id:
        print("Erreur : le run_id ne peut pas être vide.")
        sys.exit(1)
        
    grep_logs(target_run_id)
