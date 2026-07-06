"""Thin client for the lolz.live (Zelenka) Forum API.

Only the endpoints needed by the bot are implemented:

* ``GET  /users/me``  - verify the token / find the current user id
* ``GET  /threads``   - list threads inside a forum section
* ``GET  /threads/{id}`` - fetch a single thread
* ``POST /posts``     - create a reply in a thread

The client enforces a configurable delay between requests (the API allows
roughly 20 requests per minute) and retries automatically on ``429`` and
transient ``5xx`` responses with an exponential back-off.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class ForumApiError(RuntimeError):
    """Raised when the forum API returns an error response."""

    def __init__(self, message: str, status_code: Optional[int] = None,
                 payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class LolzForumClient:
    """Minimal synchronous client for the lolz.live Forum API."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://prod-api.lolz.live",
        request_delay: float = 3.0,
        timeout: float = 30.0,
        proxy: Optional[str] = None,
        max_retries: int = 4,
        session: Optional[requests.Session] = None,
    ):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = session or requests.Session()
        if proxy:
            self._session.proxies.update({"http": proxy, "https": proxy})
        self._last_request_at = 0.0

    # -- internals ---------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _respect_rate_limit(self) -> None:
        if self.request_delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        wait = self.request_delay - elapsed
        if wait > 0:
            time.sleep(wait)

    def _request(self, method: str, path: str, *, params: Optional[dict] = None,
                 data: Optional[dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        attempt = 0
        while True:
            attempt += 1
            self._respect_rate_limit()
            try:
                response = self._session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                if attempt > self.max_retries:
                    raise ForumApiError(f"Network error calling {url}: {exc}") from exc
                backoff = min(2 ** attempt, 32)
                logger.warning("Network error (%s), retrying in %ss", exc, backoff)
                time.sleep(backoff)
                continue
            finally:
                self._last_request_at = time.monotonic()

            if response.status_code in (429, 502, 503) and attempt <= self.max_retries:
                backoff = min(2 ** attempt, 32)
                logger.warning(
                    "Got HTTP %s from %s, retrying in %ss (attempt %s/%s)",
                    response.status_code, url, backoff, attempt, self.max_retries,
                )
                time.sleep(backoff)
                continue

            return self._parse(response)

    @staticmethod
    def _parse(response: requests.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if response.status_code >= 400:
            message = None
            if isinstance(payload, dict):
                errors = payload.get("errors") or payload.get("error")
                message = payload.get("message") or (
                    "; ".join(errors) if isinstance(errors, list) else errors
                )
            raise ForumApiError(
                message or f"HTTP {response.status_code} error",
                status_code=response.status_code,
                payload=payload,
            )

        if payload is None:
            raise ForumApiError(
                "Expected JSON response but got none",
                status_code=response.status_code,
            )
        if isinstance(payload, dict) and payload.get("errors"):
            raise ForumApiError(
                "; ".join(payload["errors"]) if isinstance(payload["errors"], list)
                else str(payload["errors"]),
                status_code=response.status_code,
                payload=payload,
            )
        return payload

    # -- public API --------------------------------------------------------
    def get_me(self) -> Dict[str, Any]:
        """Return the authenticated user (``users`` section of the response)."""
        payload = self._request("GET", "/users/me")
        return payload.get("user", payload)

    def list_threads(
        self,
        forum_id: int,
        *,
        page: int = 1,
        limit: Optional[int] = None,
        order: str = "thread_create_date_reverse",
    ) -> List[Dict[str, Any]]:
        """Return the list of threads in ``forum_id``."""
        params: Dict[str, Any] = {"forum_id": forum_id, "page": page, "order": order}
        if limit:
            params["limit"] = limit
        payload = self._request("GET", "/threads", params=params)
        return payload.get("threads", [])

    def get_thread(self, thread_id: int) -> Dict[str, Any]:
        payload = self._request("GET", f"/threads/{thread_id}")
        return payload.get("thread", payload)

    def create_post(self, thread_id: int, post_body: str) -> Dict[str, Any]:
        """Create a reply (post) in ``thread_id`` and return the created post."""
        data = {"thread_id": thread_id, "post_body": post_body}
        payload = self._request("POST", "/posts", data=data)
        return payload.get("post", payload)
