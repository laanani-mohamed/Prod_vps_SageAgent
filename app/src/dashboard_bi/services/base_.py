"""
Dash/services/base.py
Singleton API Client and base service classes.

Améliorations prod :
  - Refresh automatique du token sur 401 (via /api/auth/refresh)
  - Protection contre la boucle infinie sur double-401
  - Messages d'erreur réseau explicites (ConnectError vs Timeout)
  - AuthError propagée jusqu'aux pages (pas swallowed dans call_api)
"""
import logging
import httpx
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed
import streamlit as st

from config import API_BASE_URL, SOURCE_TYPE
from core.exceptions import APIError, AuthError

logger = logging.getLogger("dashboard.api_client")

class APIClient:
    _instance = None
    _client: Optional[httpx.Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = httpx.Client(timeout=30.0)
        return cls._instance

    @property
    def client(self) -> httpx.Client:
        return self._client

    def _get_headers(self) -> dict:
        headers = {}
        if "access_token" in st.session_state:
            headers["Authorization"] = f"Bearer {st.session_state.access_token}"
        return headers

    def _extract_detail(self, error: httpx.HTTPStatusError) -> str:
        try:
            body = error.response.json()
            return body.get("detail", str(error))
        except Exception:
            return str(error)

    def _try_refresh(self) -> None:
        """
        Tente de renouveler le access_token via le refresh_token.
        Met à jour session_state si le renouvellement réussit.
        Lève AuthError si le refresh_token est absent ou si le renouvellement échoue.
        """
        refresh_token = st.session_state.get("refresh_token", "")
        if not refresh_token:
            raise AuthError("Session expirée. Veuillez vous reconnecter.")

        try:
            resp = self._client.post(
                f"{API_BASE_URL}/api/auth/refresh",
                json={"refresh_token": refresh_token},
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.access_token  = data["access_token"]
                st.session_state.refresh_token = data["refresh_token"]
                logger.info("[AUTH] Token renouvelé automatiquement.")
                return
        except Exception as e:
            logger.warning(f"[AUTH] Échec du refresh token : {e}")

        raise AuthError("Session expirée. Veuillez vous reconnecter.")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True)
    def post(self, endpoint: str, payload: dict) -> dict:
        payload = dict(payload)
        payload["source_type"] = SOURCE_TYPE
        
        # Injection du schéma
        if not payload.get("client_schema") and "client_schema" in st.session_state:
            payload["client_schema"] = st.session_state.client_schema
            
        url = f"{API_BASE_URL}{endpoint}"
        logger.info(f"POST {url} — payload={payload}")

        try:
            headers = self._get_headers()
            resp = self.client.post(url, json=payload, headers=headers)

            # --- Token expiré : tentative de refresh automatique ---
            if resp.status_code == 401:
                self._try_refresh()  # Lève AuthError si ça échoue
                headers = self._get_headers()  # Nouveau token en session
                resp = self.client.post(url, json=payload, headers=headers)
                # Protection boucle infinie : double 401 = session morte
                if resp.status_code == 401:
                    raise AuthError("Session invalide après renouvellement. Veuillez vous reconnecter.")

            resp.raise_for_status()
            return resp.json()

        except AuthError:
            raise  # Laisser remonter sans transformation

        except httpx.HTTPStatusError as e:
            detail = self._extract_detail(e)
            logger.error(f"API Error [{e.response.status_code}] on {endpoint}: {detail}")
            if e.response.status_code == 403:
                raise AuthError("Accès refusé à cette ressource.") from e
            raise APIError(f"API Error: {detail}") from e

        except httpx.ConnectError as e:
            logger.error(f"Connection Error on {endpoint}: {e}")
            raise APIError("🚨 Impossible de joindre le serveur API. Vérifiez que le service est démarré.") from e

        except httpx.TimeoutException as e:
            logger.error(f"Timeout on {endpoint}: {e}")
            raise APIError("⏱️ Le serveur API met trop de temps à répondre. Réessayez dans un instant.") from e

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True)
    def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        params = dict(params) if params else {}
        params["source_type"] = SOURCE_TYPE
        
        # Injection du schéma
        if not params.get("client_schema") and "client_schema" in st.session_state:
            params["client_schema"] = st.session_state.client_schema
            
        url = f"{API_BASE_URL}{endpoint}"
        logger.info(f"GET {url} — params={params}")

        try:
            headers = self._get_headers()
            resp = self.client.get(url, params=params, headers=headers)

            # --- Token expiré : tentative de refresh automatique ---
            if resp.status_code == 401:
                self._try_refresh()
                headers = self._get_headers()
                resp = self.client.get(url, params=params, headers=headers)
                if resp.status_code == 401:
                    raise AuthError("Session invalide après renouvellement. Veuillez vous reconnecter.")

            resp.raise_for_status()
            return resp.json()

        except AuthError:
            raise

        except httpx.HTTPStatusError as e:
            detail = self._extract_detail(e)
            logger.error(f"API Error [{e.response.status_code}] on {endpoint}: {detail}")
            if e.response.status_code == 403:
                raise AuthError("Accès refusé à cette ressource.") from e
            raise APIError(f"API Error: {detail}") from e

        except httpx.ConnectError as e:
            logger.error(f"Connection Error on {endpoint}: {e}")
            raise APIError("🚨 Impossible de joindre le serveur API. Vérifiez que le service est démarré.") from e

        except httpx.TimeoutException as e:
            logger.error(f"Timeout on {endpoint}: {e}")
            raise APIError("⏱️ Le serveur API met trop de temps à répondre. Réessayez dans un instant.") from e


# Instantiate the singleton client
api_client_instance = APIClient()

def call_api(endpoint: str, payload: dict) -> dict:
    """
    Wrapper POST. Propage AuthError jusqu'à la page appelante.
    Affiche les APIError directement dans l'interface.
    """
    try:
        return api_client_instance.post(endpoint, payload)
    except AuthError:
        raise  # La page appelante gère la déconnexion via handle_auth_error()
    except APIError as e:
        st.error(f"❌ {str(e)}")
        return {}

def call_api_get(endpoint: str, params: Optional[dict] = None) -> dict:
    """
    Wrapper GET. Propage AuthError jusqu'à la page appelante.
    Affiche les APIError directement dans l'interface.
    """
    try:
        return api_client_instance.get(endpoint, params)
    except AuthError:
        raise
    except APIError as e:
        st.error(f"❌ {str(e)}")
        return {}

def check_api_health() -> bool:
    try:
        resp = api_client_instance.client.get(f"{API_BASE_URL}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False
