# --- LAYER: API ---
import functools

import streamlit as st


def _perimetre() -> tuple:
    """Périmètre de données de la session : schéma client, rôle et co_no du jeton."""
    s = st.session_state
    return s.get("client_schema"), tuple(s.get("roles", [])), s.get("co_no")


def cache_data(*cache_args, **cache_kwargs):
    """st.cache_data dont la clé inclut le périmètre de la session.

    Le cache Streamlit est partagé par toutes les sessions d'une instance (un directeur et ses
    collaborateurs) : sans le périmètre dans la clé, un profil recevrait les données obtenues
    avec le jeton d'un autre. S'utilise comme st.cache_data, `.clear()` compris.
    """
    def decorateur(func):
        def _avec_perimetre(perimetre, *args, **kwargs):
            return func(*args, **kwargs)
        # Clé de fonction Streamlit = module + qualname : une entrée de cache distincte par fonction
        _avec_perimetre.__module__, _avec_perimetre.__qualname__ = func.__module__, func.__qualname__
        cache = st.cache_data(*cache_args, **cache_kwargs)(_avec_perimetre)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return cache(_perimetre(), *args, **kwargs)
        wrapper.clear = cache.clear
        return wrapper
    return decorateur
