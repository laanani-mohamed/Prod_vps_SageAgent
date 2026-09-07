"""
Dash/services/base.py
Singleton API Client and base service classes.
"""
import logging
import httpx
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import streamlit as st

from config import API_BASE_URL, SOURCE_TYPE
from core.exceptions import APIError

logger = logging.getLogger("dashboard.api_client")

class APIClient:
    _instance = None
    _client: Optional[httpx.Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = httpx.Client(timeout=120.0)  # 120s pour les requêtes stock complexes
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

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
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
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            detail = self._extract_detail(e)
            logger.error(f"API Error [{e.response.status_code}] on {endpoint}: {detail}")
            raise APIError(f"API Error: {detail}") from e
        except httpx.RequestError as e:
            logger.error(f"Connection Error: {e}")
            raise APIError(f"Connection Error to API") from e

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
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
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            detail = self._extract_detail(e)
            logger.error(f"API Error [{e.response.status_code}] on {endpoint}: {detail}")
            raise APIError(f"API Error: {detail}") from e
        except httpx.RequestError as e:
            logger.error(f"Connection Error: {e}")
            raise APIError(f"Connection Error to API") from e

# Instantiate the singleton client
api_client_instance = APIClient()

def call_api(endpoint: str, payload: dict) -> dict:
    try:
        return api_client_instance.post(endpoint, payload)
    except APIError as e:
        st.error(f"❌ {str(e)}")
        return {}

def call_api_get(endpoint: str, params: Optional[dict] = None) -> dict:
    try:
        return api_client_instance.get(endpoint, params)
    except APIError as e:
        st.error(f"❌ {str(e)}")
        return {}

def check_api_health() -> bool:
    try:
        resp = api_client_instance.client.get(f"{API_BASE_URL}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False
