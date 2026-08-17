"""Generic HTTP client for consuming external REST APIs.

Every data source this portal will ever use (resultats today; cens and
admin in the future) is reached exclusively through an instance of
BaseApiClient. This is the single seam where HTTP concerns live: base URL
composition, headers (including Authorization once a token exists),
timeouts, retries and error translation. Adding a brand-new API later is
just creating one small ``xxx_client.py`` that builds a BaseApiClient
pointed at its base URL — nothing else in the project needs to change.

Nothing in this module (or anywhere in the project) persists data to disk
or to a local database: it only ever makes outbound HTTP calls and returns
their response to the caller.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    """Base class for every error raised while talking to an external API."""


class ApiConnectionError(ApiClientError):
    """The external API could not be reached at all (DNS/timeout/network)."""


class ApiResponseError(ApiClientError):
    """The external API responded, but with an HTTP error status."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class BaseApiClient:
    """Thin, reusable wrapper around `requests` for calling a REST API."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 10,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        auth_token: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.timeout = timeout
        self.auth_token = auth_token

        retry = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST", "PUT", "DELETE"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _build_headers(self, extra_headers: Optional[dict] = None) -> dict:
        headers = {"Accept": "application/json, text/csv, text/plain, */*"}
        if self.auth_token:
            # Not used by the Resultats API today (public/read-only), but
            # every future client shares this same code path so wiring up
            # Authorization for cens/admin later needs no new plumbing.
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Any = None,
        raw: bool = False,
    ):
        url = self._build_url(path)
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=self._build_headers(),
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            logger.warning("Timeout calling %s %s", method, url)
            raise ApiConnectionError(f"Temps d'espera exhaurit en contactar amb {url}") from exc
        except requests.exceptions.RequestException as exc:
            logger.warning("Connection error calling %s %s: %s", method, url, exc)
            raise ApiConnectionError(f"No s'ha pogut connectar amb {url}") from exc

        if response.status_code >= 400:
            logger.warning("HTTP %s from %s %s", response.status_code, method, url)
            raise ApiResponseError(
                f"L'API ha retornat un error {response.status_code} per a {url}",
                status_code=response.status_code,
            )

        if raw:
            return response.text

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    def get(self, path: str = "", params: Optional[dict] = None, raw: bool = False):
        return self._request("GET", path, params=params, raw=raw)

    def post(self, path: str, json_body: Any = None):
        return self._request("POST", path, json_body=json_body)

    def put(self, path: str, json_body: Any = None):
        return self._request("PUT", path, json_body=json_body)

    def delete(self, path: str):
        return self._request("DELETE", path)
