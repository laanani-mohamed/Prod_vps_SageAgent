"""
Dash/services/top_client_service.py
Service pour encapsuler la récupération des top clients basée sur F_DOCENTETE.
"""
from services.documents_service import get_documents_entete

# --- LAYER: BUSINESS ---

def get_top_clients_from_docentete(client_schema: str, date_from: str, date_to: str, limit: int = 5) -> list:
    """
    Récupère les données de F_DOCENTETE avec do_domaine = 0 (Ventes),
    puis groupe et somme par client (do_tiers / ct_intitule) pour retourner les top clients de la dernière année.
    """
    filters = {
        "date_from": date_from,
        "date_to": date_to
    }
    docs = get_documents_entete(client_schema, domaine=[0], limit=100000000, filters=filters)
    
    if not docs:
        return []
        
    all_zero_types = all(str(doc.get("do_type")) in ["0", "None"] for doc in docs)
        
    client_totals = {}
    for doc in docs:
        d_date = doc.get("do_date")
        if not d_date:
            continue        
        dtype = doc.get("do_type")
        try:
            dtype_int = int(dtype) if dtype is not None else 0
        except ValueError:
            dtype_int = 0
            
        if not all_zero_types and dtype_int not in [6]:
            continue
            
        tiers = doc.get("do_tiers")
        name = doc.get("ct_intitule") or tiers or "Inconnu"
        amount = float(doc.get("do_totalttc") or 0.0)

        if tiers not in client_totals:
            client_totals[tiers] = {
                "do_tiers": tiers,
                "ct_intitule": name,
                "ca_ttc": 0.0,
                "nb_factures": 0
            }
        client_totals[tiers]["ca_ttc"] += amount
        client_totals[tiers]["nb_factures"] += 1

    sorted_clients = sorted(client_totals.values(), key=lambda x: x["ca_ttc"], reverse=True)
    return sorted_clients
