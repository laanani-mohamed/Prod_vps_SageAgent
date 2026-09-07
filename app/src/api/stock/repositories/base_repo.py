from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseStockRepository(ABC):
    """
    Interface commune pour l'accès aux données de stock brutes.
    """

    @abstractmethod
    def fetch(self, req: Any) -> List[Dict[str, Any]]:
        """
        Retourne les données brutes sous forme de liste de dictionnaires.
        """
        pass
