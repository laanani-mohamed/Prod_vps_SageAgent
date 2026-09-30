"""formatting.py — Formats d'affichage communs du dashboard_ops."""
from typing import Optional


def fmt_taille(octets: Optional[float]) -> str:
    """1536 → '1,5 Ko' ; None → '—'."""
    if octets is None:
        return "—"
    for unite, seuil in (("Go", 1e9), ("Mo", 1e6), ("Ko", 1e3)):
        if octets >= seuil:
            return f"{octets / seuil:,.1f} {unite}".replace(",", " ").replace(".", ",")
    return f"{int(octets)} o"


def fmt_entier(n: Optional[int]) -> str:
    """834884 → '834 884' ; None → '—'."""
    return "—" if n is None else f"{n:,}".replace(",", " ")
