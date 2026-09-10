"""
api/stock/business_logic/source_meta.py

Métadonnées communes aux réponses stock : résolution de la source
(db_latest vs archive:<timestamp>) et détection des références article
demandées mais absentes du résultat.
"""
from typing import Any, List, Tuple


def extract_source_and_warnings(data: list, req: Any) -> Tuple[str, List[str]]:
    """
    Extrait le `__source_timestamp__` éventuel de `data` (le retire de chaque
    ligne, en place) pour construire le libellé de source, puis calcule les
    warnings pour les `req.ar_ref` demandés mais absents du résultat.
    """
    source = req.source_type
    if data and "__source_timestamp__" in data[0]:
        source = f"archive:{data[0].pop('__source_timestamp__')}"
        for row in data:
            row.pop("__source_timestamp__", None)

    warnings = []
    ar_ref = getattr(req, "ar_ref", None)
    if ar_ref:
        found_refs = {str(row.get("ar_ref", "")).strip() for row in data}
        source_label = "la base de données" if "db_latest" in source else "les archives"
        for ref in ar_ref:
            if ref not in found_refs:
                warnings.append(f"La référence '{ref}' n'existe pas dans {source_label}.")

    return source, warnings
