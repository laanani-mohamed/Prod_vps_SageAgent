"""
file_stats.py — Volumétrie d'un fichier Sage (TSV sans en-tête) : lignes, colonnes, taille.
Partagé par l'archiveur (écrit dans le log d'archivage) et le dashboard_ops (fallback
pour les runs archivés avant l'ajout de ces chiffres au log).
"""
import os


def file_stats(filepath: str) -> dict:
    """
    {"fichier", "lignes", "colonnes", "taille"} :
      lignes   = lignes non vides (lecture en flux, fichier jamais chargé en mémoire)
      colonnes = tabulations de la 1re ligne non vide + 1 (0 si fichier vide)
      taille   = octets
    """
    lignes, colonnes = 0, 0
    with open(filepath, "rb") as f:
        for line in f:
            if not line.strip():
                continue
            if lignes == 0:
                colonnes = line.removeprefix(b"\xef\xbb\xbf").count(b"\t") + 1
            lignes += 1
    return {
        "fichier": os.path.basename(filepath),
        "lignes": lignes,
        "colonnes": colonnes,
        "taille": os.path.getsize(filepath),
    }
