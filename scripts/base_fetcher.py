"""Base Fetcher — Retry logic, caching, and rate limiting for data fetchers."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests

from scripts.config import CACHE_DIR, RATE_LIMITS


class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.max_rate = RATE_LIMITS.get(name, 5)
        self._last_call = 0.0

    def wait(self) -> None:
        """Block until enough time has passed since the last call."""
        min_interval = 1.0 / self.max_rate
        elapsed = time.time() - self._last_call
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call = time.time()


class BaseFetcher:
    """Base class for all data fetchers with retry, caching, and rate limiting."""

    source_name: str = "base"

    def __init__(self) -> None:
        self.rate_limiter = RateLimiter(self.source_name)
        self.cache_dir = CACHE_DIR / self.source_name
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()

    def _cache_key(self, *args: str) -> str:
        """Generate a deterministic cache key from arguments."""
        raw = "|".join(str(a) for a in args)
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_cached(self, key: str, max_age_hours: int = 24) -> dict[str, Any] | None:
        """Return cached result if fresh enough, else None."""
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours > max_age_hours:
            return None
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _set_cached(self, key: str, data: dict[str, Any]) -> None:
        """Write data to cache."""
        cache_file = self.cache_dir / f"{key}.json"
        cache_file.write_text(json.dumps(data, indent=2, default=str))

    def fetch_with_retry(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        max_retries: int = 3,
        backoff: float = 1.0,
    ) -> requests.Response:
        """Fetch URL with rate limiting and exponential backoff retry."""
        for attempt in range(max_retries):
            self.rate_limiter.wait()
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=30)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                wait = backoff * (2 ** attempt)
                print(f"[{self.source_name}] Retry {attempt + 1}/{max_retries} after {wait:.1f}s: {e}")
                time.sleep(wait)
        raise RuntimeError("Unreachable")  # pragma: no cover

    def fetch_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_key: str | None = None,
        cache_hours: int = 24,
    ) -> dict[str, Any]:
        """Fetch JSON with optional caching."""
        if cache_key:
            cached = self._get_cached(cache_key, cache_hours)
            if cached is not None:
                return cached

        resp = self.fetch_with_retry(url, params=params, headers=headers)
        data = resp.json()

        if cache_key:
            self._set_cached(cache_key, data)

        return data
