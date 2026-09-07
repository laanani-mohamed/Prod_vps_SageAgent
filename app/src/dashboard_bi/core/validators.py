from typing import List, Dict
from core.constants import Domaine, FACTURE_TYPES

def is_archive_mode(docs: List[Dict]) -> bool:
    """Détecte si les données proviennent des archives."""
    if not docs:
        return False
    return all(str(d.get("do_type")) in ("0", "None") for d in docs)

def filter_factures(docs: List[Dict], domaine: Domaine) -> List[Dict]:
    """Filtre les documents pour ne garder que les factures."""
    if is_archive_mode(docs):
        return docs
    types = FACTURE_TYPES[domaine]
    return [d for d in docs if int(d.get("do_type", -1)) in types]

def safe_float(value, default: float = 0.0) -> float:
    """Conversion sécurisée en float avec log."""
    try:
        return float(value or default)
    except (ValueError, TypeError):
        return default