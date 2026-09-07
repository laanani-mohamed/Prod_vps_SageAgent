"""
api/bi/repositories/base_bi_repo.py

Interface abstraite commune à tous les repositories BI.
Miroir de BaseStockRepository pour le module BI.

Chaque use case a son propre type de retour, donc fetch() retourne
des données brutes (List[Dict]) qui seront ensuite traitées
par la business_logic correspondante.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseBIRepository(ABC):
    """
    Interface commune pour l'accès aux données brutes BI.
    Implémentée par :
      - Les repos archive (lecture fichiers .txt)
      - Les repos PG (requêtes PostgreSQL en temps réel)
    """

    @abstractmethod
    def fetch(self, req: Any) -> List[Dict[str, Any]]:
        """
        Retourne les données brutes sous forme de liste de dictionnaires.
        Le nom des clés doit correspondre aux noms de colonnes Polars
        attendus par la business_logic.
        """
        pass
