from enum import IntEnum
from typing import Final, Dict, List, Tuple

class Domaine(IntEnum):
    VENTE = 0
    ACHAT = 1
    STOCK = 2

class TypeDocumentVente(IntEnum):
    DEVIS = 0; BON_COMMANDE = 1; PREP_LIVRAISON = 2
    BON_LIVRAISON = 3; BON_RETOUR = 4; BON_AVOIR = 5
    FACTURE = 6; FACTURE_COMPTABILISEE = 7; ARCHIVE = 8

class TypeDocumentAchat(IntEnum):
    DEMANDE_ACHAT = 10; PREP_COMMANDE = 11; BON_COMMANDE = 12
    BON_LIVRAISON = 13; BON_RETOUR = 14; BON_AVOIR = 15
    FACTURE = 16; FACTURE_COMPTABILISEE = 17; ARCHIVE = 18

class TypeDocumentStock(IntEnum):
    ENTREE = 20; SORTIE = 21; TRANSFERT_DEPOT = 22; TRANSFERT = 23

class TypeTiers(IntEnum):
    CLIENT = 0; FOURNISSEUR = 1; SALARIE = 2; AUTRE = 3

class TypeReglement(IntEnum):
    REGLEMENT = 0; ACOMPTE = 1; FOND_CAISSE = 2
    REMISE_BANQUE = 3; SORTIE_CAISSE = 4; ENTREE_CAISSE = 5
    REMISE_A_ZERO = 6; CONTROLE_CAISSE = 7; BON_ACHAT = 8

# Mapping centralisé
FACTURE_TYPES: Final[Dict[Domaine, List[int]]] = {
    Domaine.VENTE: [TypeDocumentVente.FACTURE, TypeDocumentVente.FACTURE_COMPTABILISEE],
    Domaine.ACHAT: [TypeDocumentAchat.FACTURE, TypeDocumentAchat.FACTURE_COMPTABILISEE],
}

TYPE_REGLEMENT_LABEL: Final[Dict[int, str]] = {
    0: "Règlement", 1: "Acompte", 2: "Fond de caisse",
    3: "Remise en banque", 4: "Sortie de caisse", 5: "Entrée en caisse",
    6: "Remise à 0", 7: "Contrôle de caisse", 8: "Bon d'achat"
}

DOC_TYPES_VENTE: Final[Dict[int, str]] = {
    0: "Devis", 1: "Bon de commande", 2: "Préparation livraison",
    3: "Bon de livraison", 4: "Bon de retour", 5: "Bon d'avoir",
    6: "Facture", 7: "Facture comptabilisée",
}

DOC_TYPES_ACHAT: Final[Dict[int, str]] = {
    10: "Demande d'achat", 11: "Préparation de commande", 12: "Bon de commande",
    13: "Bon de livraison", 14: "Bon de retour", 15: "Bon d'avoir",
    16: "Facture", 17: "Facture comptabilisée",
}

DOC_TYPES_STOCK: Final[Dict[int, str]] = {
    20: "Mouvement d'entrée", 21: "Mouvement de sortie",
    22: "Mouvement de dépôt à dépôt", 23: "Transfert",
}

# Seuils métier
SEUIL_DSO_BON: Final[int] = 60
SEUIL_DSO_ALERTE: Final[int] = 90
SEUIL_LITIGE_BON: Final[float] = 10.0
SEUIL_LITIGE_ALERTE: Final[float] = 25.0
SEUIL_RETOUR_BON: Final[float] = 3.0
SEUIL_RETOUR_ALERTE: Final[float] = 8.0
SEUIL_CONVERSION_BON: Final[float] = 50.0
SEUIL_CONVERSION_ALERTE: Final[float] = 30.0