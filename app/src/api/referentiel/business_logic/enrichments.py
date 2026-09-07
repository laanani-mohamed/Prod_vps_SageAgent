"""
bi/referentiel/business_logic/enrichments.py

Calculs métier purs appliqués sur les données brutes retournées par les repositories.

Règles :
  - Toutes les fonctions sont stateless (pas d'IO, pas de DB, pas de fichiers)
  - Input = List[dict], Output = List[dict]
  - Testables unitairement sans infrastructure
"""
from __future__ import annotations
import datetime
from typing import List, Dict, Any, Optional


def add_reste_a_payer(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calcule reste_a_payer = DO_TotalTTC - DO_MontantRegle.
    Utilisé par : doc_entete_uc, doc_ligne_uc (with_entete=True)
    """
    for row in rows:
        ttc = _to_float(row.get("do_totalttc"))
        regle = _to_float(row.get("do_montantregle"))
        row["reste_a_payer"] = round(ttc - regle, 4)
    return rows


def add_valeur_stock(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calcule valeur_stock_achat et valeur_stock_vente.
    Utilisé par : stock_depot_uc
    """
    for row in rows:
        qte = _to_float(row.get("as_qtesto"))
        prix_ach = _to_float(row.get("ar_prixach"))
        prix_ven = _to_float(row.get("ar_prixven"))
        row["valeur_stock_achat"] = round(qte * prix_ach, 4)
        row["valeur_stock_vente"] = round(qte * prix_ven, 4)
    return rows


def add_jours_avant_peremption(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calcule jours_avant_peremption = ls_peremption - aujourd'hui.
    Valeur négative = lot déjà périmé.
    Utilisé par : lot_serie_uc
    """
    today = datetime.date.today()
    for row in rows:
        peremption = row.get("ls_peremption")
        if peremption is None:
            row["jours_avant_peremption"] = None
            continue
        try:
            if isinstance(peremption, str):
                peremption = datetime.date.fromisoformat(peremption[:10])
            elif isinstance(peremption, datetime.datetime):
                peremption = peremption.date()
            row["jours_avant_peremption"] = (peremption - today).days
        except (ValueError, TypeError):
            row["jours_avant_peremption"] = None
    return rows


def add_marge_catalogue(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calcule marge_catalogue_pct = (prix_ven - prix_ach) / prix_ven * 100.
    Utilisé par : article_detail_uc (optionnel)
    """
    for row in rows:
        ven = _to_float(row.get("ar_prixven"))
        ach = _to_float(row.get("ar_prixach"))
        if ven and ven != 0:
            row["marge_catalogue_pct"] = round((ven - ach) / ven * 100, 2)
        else:
            row["marge_catalogue_pct"] = None
    return rows


# ---------------------------------------------------------------------------
# Helper interne
# ---------------------------------------------------------------------------

def _to_float(value) -> float:
    """Conversion sécurisée vers float (None / str / Decimal / int → float)."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
