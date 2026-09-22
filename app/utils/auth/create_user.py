import sys
import os
import getpass
from passlib.context import CryptContext
import psycopg2


current_dir = os.path.dirname(os.path.abspath(__file__))
# Remonte : auth -> src (1 niveaux) -> RACINE (2 niveaux)
script_path = os.path.dirname(current_dir)
project_path = os.path.dirname(script_path)
config_path = os.path.join(project_path, "config")

for path in [project_path, config_path]:
    if path not in sys.path:
        sys.path.insert(0, path)

from config.db_config import DB_CONFIG


def create_api_user(username: str, password: str, allowed_schemas: list, roles: list) -> None:
    """
    Hache le mot de passe et insère l'utilisateur dans auth.users.
    Réutilisable depuis un script CLI ou depuis la page d'onboarding du dashboard ops.
    Lève psycopg2.IntegrityError si le username existe déjà.
    """
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash(password)

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.users (username, hashed_password, allowed_schemas, roles, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            """,
            (username, hashed_password, allowed_schemas, roles),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def create_user():
    print("=== CRÉATION D'UN NOUVEL UTILISATEUR API ===")

    # 1. Saisie des informations
    username = input("Nom d'utilisateur : ").strip()
    if not username:
        print("Erreur : Le nom d'utilisateur ne peut pas être vide.")
        return

    password = getpass.getpass("Mot de passe : ")
    if not password:
        print("Erreur : Le mot de passe ne peut pas être vide.")
        return

    schemas_input = input("Schémas autorisés (séparés par une virgule ,) : ").strip()
    allowed_schemas = [s.strip().lower() for s in schemas_input.split(',')] if schemas_input else []

    roles_input = input("Rôles (séparés par une virgule, ex: analyst,vendeur) [défaut: vendeur] : ").strip()
    roles = [r.strip().lower() for r in roles_input.split(',')] if roles_input else ["vendeur"]

    # 2. Hashage + insertion (logique commune, voir create_api_user)
    print("\n[1/3] Hachage du mot de passe en cours...")
    print("[2/3] Connexion à la base de données...")
    try:
        print(f"[3/3] Insertion de l'utilisateur '{username}'...")
        create_api_user(username, password, allowed_schemas, roles)
        print("\n✅ SUCCÈS : L'utilisateur a été créé et inséré dans la base de données !")
        print(f"-> Username : {username}")
        print(f"-> Schémas  : {allowed_schemas}")
        print(f"-> Rôles    : {roles}")

    except psycopg2.IntegrityError:
        print(f"\n❌ ERREUR : L'utilisateur '{username}' existe déjà dans la base de données.")
    except Exception as e:
        print(f"\n❌ ERREUR LORS DE L'INSERTION : {e}")

if __name__ == "__main__":
    create_user()
