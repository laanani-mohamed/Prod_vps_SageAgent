"""
bi/referentiel/repositories/base_repo.py

Interface commune (ABC) pour l'accès aux données du module Référentiel.
Toute implémentation concrète (PostgreSQL ou Archive CSV) doit hériter de cette classe.

Principe : les Use Cases ne savent jamais si la source est PG ou CSV.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseReferentielRepository(ABC):
    """Interface commune pour tous les repositories du module Référentiel."""

    @abstractmethod
    def fetch(self, req: Any) -> List[Dict[str, Any]]:
        """
        Retourne les données brutes sous forme de liste de dictionnaires.

        - Aucune logique métier (pas de calcul de reste_a_payer ici)
        - Aucune sérialisation JSON (pas de Decimal → float ici)
        - Applique uniquement les filtres de la requête
        - Respecte req.limit

        Args:
            req : Le schéma Pydantic spécifique (ComptesTiersRequest, DocLigneRequest, etc.)

        Returns:
            List[Dict[str, Any]] : Données brutes, prêtes pour le Use Case
        """
        pass
