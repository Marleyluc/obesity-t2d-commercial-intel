"""A polite, resilient HTTP client shared by every data source.

- Retries automatically on temporary failures (429 Too Many Requests, 5xx server errors)
  with exponential backoff, so one hiccup doesn't kill a 20-minute pull.
- Waits a short delay between requests so we never hammer a public API.
- Sends an identifying User-Agent, which public APIs ask for.
"""

from __future__ import annotations

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from obesity_ci import config


class PoliteSession:
    def __init__(self, delay_s: float = 0.5):
        st = config.settings()["http"]
        self.timeout = st["timeout_s"]
        self.delay_s = delay_s
        self._last_call = 0.0

        retry = Retry(
            total=st["max_retries"],
            backoff_factor=2,  # waits 2s, 4s, 8s between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=True,
        )
        self.session = requests.Session()
        self.session.headers["User-Agent"] = st["user_agent"]
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get_json(self, url: str, params: dict | None = None) -> dict:
        """GET a URL and return parsed JSON. Raises a readable error on failure."""
        wait = self.delay_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        r = self.session.get(url, params=params, timeout=self.timeout)
        self._last_call = time.monotonic()
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code} for {r.url}\nServer said: {r.text[:500]}")
        return r.json()
