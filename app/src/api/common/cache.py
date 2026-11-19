"""
api/common/cache.py — Cache en mémoire des chargements lourds de l'API (un seul processus uvicorn).

Les données d'un client ne changent qu'au passage de l'ETL : un résultat est gardé jusqu'à ce que
api/common/prechauffage.py constate une nouvelle ingestion du client et appelle vider(schema)
(il le fait aussi chaque nuit), au plus DUREE secondes par sécurité.
La clé contient le client et la requête complète (dont co_no, imposé par secured_handle pour un
collaborateur) : pas de mélange entre clients ni entre profils. Une même clé n'est calculée qu'une
fois à la fois : les requêtes identiques simultanées attendent le premier calcul au lieu de le refaire.
Le cache se vide au redémarrage de l'API (le préchauffage le remplit aussitôt).
"""
import threading
import time
from collections import OrderedDict
from typing import Any, Callable

DUREE = 25 * 3600    # sécurité : vider() est normalement appelé avant (ETL, ou chaque nuit)
MAX_ENTREES = 300    # au-delà, les entrées les moins récemment utilisées sont retirées

_donnees: OrderedDict = OrderedDict()  # (schema, clé) → (expiration, valeur), de la moins à la plus récemment utilisée
_verrous: dict = {}                     # (schema, clé) → verrou du calcul en cours
_generation: dict = {}                  # schema → nombre de vider(schema) (calcul commencé avant : pas gardé)
_global = threading.Lock()


def _lire(k):
    trouve = _donnees.get(k)
    if trouve and trouve[0] > time.monotonic():
        _donnees.move_to_end(k)
        return True, trouve[1]
    return False, None


def memo(schema: str, cle: str, calcul: Callable[[], Any]) -> Any:
    """Valeur en cache pour (`schema`, `cle`), sinon `calcul()` (une seule fois à la fois par clé)."""
    k = (schema, cle)
    with _global:
        ok, valeur = _lire(k)
        if ok:
            return valeur
        verrou = _verrous.setdefault(k, threading.Lock())
    with verrou:
        with _global:   # calculé entre-temps par une requête identique ?
            ok, valeur = _lire(k)
            if ok:
                return valeur
            generation = _generation.get(schema, 0)
        valeur = calcul()
        with _global:
            if _generation.get(schema, 0) == generation:   # pas de vider(schema) pendant le calcul
                _donnees[k] = (time.monotonic() + DUREE, valeur)
                _donnees.move_to_end(k)
                while len(_donnees) > MAX_ENTREES:
                    ancienne, _ = _donnees.popitem(last=False)
                    _verrous.pop(ancienne, None)
        return valeur


def vider(schema: str) -> None:
    """Oublie tous les résultats du client `schema` (nouvelles données après un passage de l'ETL)."""
    with _global:
        _generation[schema] = _generation.get(schema, 0) + 1
        for k in [k for k in _donnees if k[0] == schema]:
            del _donnees[k]
            _verrous.pop(k, None)


def taille() -> int:
    return len(_donnees)
