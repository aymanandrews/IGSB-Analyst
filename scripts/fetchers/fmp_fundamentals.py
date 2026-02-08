"""FMP Fundamentals Fetcher — Company profile, ratios, metrics, and estimates.

Uses the Financial Modeling Prep (FMP) API to fetch fundamental data,
financial ratios, key metrics, analyst estimates, and enterprise values.

Usage:
    fetcher = FMPFetcher()
    profile = fetcher.fetch_profile("APPF")
    metrics = fetcher.fetch_key_metrics("APPF", period="annual", limit=5)
    all_data = fetcher.fetch_all("APPF")
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from scripts.base_fetcher import BaseFetcher
from scripts.config import FMP_API_KEY

logger = logging.getLogger(__name__)

# FMP API v3 base URL
_BASE_URL = "https://financialmodelingprep.com/api/v3"

# Cache TTL for fundamental data (hours) — doesn't change intraday
_CACHE_HOURS = 12


class FMPFetcher(BaseFetcher):
    """Fetches fundamental data from Financial Modeling Prep API."""

    source_name: str = "fmp"

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def fetch_profile(self, ticker: str) -> Dict[str, Any]:
        """Fetch company profile — name, sector, industry, market cap, etc.

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").

        Returns:
            Dict with profile fields, or empty dict if unavailable.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return {}

        cache_key = self._cache_key("profile", ticker)
        data = self._fmp_fetch(
            f"/profile/{ticker}",
            cache_key=cache_key,
        )

        # /profile returns a list with one element
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return {}

    def fetch_key_metrics(
        self,
        ticker: str,
        period: str = "annual",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Fetch key metrics — revenue per share, PE, PB, ROIC, ROE, dividend yield, etc.

        Args:
            ticker: Company stock ticker symbol.
            period: "annual" or "quarter".
            limit: Number of periods to return.

        Returns:
            List of metric dicts (one per period), or empty list if unavailable.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return []

        cache_key = self._cache_key("key_metrics", ticker, period, str(limit))
        data = self._fmp_fetch(
            f"/key-metrics/{ticker}",
            params={"period": period, "limit": limit},
            cache_key=cache_key,
        )

        if isinstance(data, list):
            return data
        return []

    def fetch_ratios(
        self,
        ticker: str,
        period: str = "annual",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Fetch financial ratios — profitability, liquidity, leverage, efficiency.

        Args:
            ticker: Company stock ticker symbol.
            period: "annual" or "quarter".
            limit: Number of periods to return.

        Returns:
            List of ratio dicts (one per period), or empty list if unavailable.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return []

        cache_key = self._cache_key("ratios", ticker, period, str(limit))
        data = self._fmp_fetch(
            f"/ratios/{ticker}",
            params={"period": period, "limit": limit},
            cache_key=cache_key,
        )

        if isinstance(data, list):
            return data
        return []

    def fetch_analyst_estimates(self, ticker: str) -> List[Dict[str, Any]]:
        """Fetch analyst estimates — estimated revenue, EPS, growth for upcoming periods.

        Args:
            ticker: Company stock ticker symbol.

        Returns:
            List of estimate dicts, or empty list if unavailable.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return []

        cache_key = self._cache_key("analyst_estimates", ticker)
        data = self._fmp_fetch(
            f"/analyst-estimates/{ticker}",
            cache_key=cache_key,
        )

        if isinstance(data, list):
            return data
        return []

    def fetch_enterprise_value(self, ticker: str) -> Dict[str, Any]:
        """Fetch enterprise value — market cap, EV, shares outstanding.

        Args:
            ticker: Company stock ticker symbol.

        Returns:
            Dict with enterprise value fields, or empty dict if unavailable.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return {}

        cache_key = self._cache_key("enterprise_value", ticker)
        data = self._fmp_fetch(
            f"/enterprise-values/{ticker}",
            params={"limit": 1},
            cache_key=cache_key,
        )

        # /enterprise-values returns a list; take the most recent entry
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return {}

    def fetch_all(self, ticker: str) -> Dict[str, Any]:
        """Fetch all FMP fundamental data for a ticker in one call.

        Convenience method that calls every individual fetcher and combines
        results into a single dict.

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").

        Returns:
            Dict with keys: profile, key_metrics, ratios,
            analyst_estimates, enterprise_value.
        """
        ticker = ticker.upper().strip()
        return {
            "profile": self.fetch_profile(ticker),
            "key_metrics": self.fetch_key_metrics(ticker),
            "ratios": self.fetch_ratios(ticker),
            "analyst_estimates": self.fetch_analyst_estimates(ticker),
            "enterprise_value": self.fetch_enterprise_value(ticker),
        }

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _check_api_key() -> bool:
        """Verify FMP_API_KEY is set. Log a warning and return False if not."""
        if not FMP_API_KEY:
            logger.warning(
                "FMP_API_KEY is not set. Skipping FMP fetch. "
                "Set the FMP_API_KEY environment variable or add it to .env."
            )
            return False
        return True

    def _fmp_fetch(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        cache_key: Optional[str] = None,
    ) -> Any:
        """Build the full FMP URL and fetch JSON with caching and error handling.

        Args:
            endpoint: API path (e.g. "/profile/APPF").
            params: Extra query parameters (period, limit, etc.).
            cache_key: Cache key string for BaseFetcher caching.

        Returns:
            Parsed JSON response (list or dict), or empty list on error.
        """
        url = f"{_BASE_URL}{endpoint}"

        # Merge apikey into query params
        query_params: Dict[str, Any] = {"apikey": FMP_API_KEY}
        if params:
            query_params.update(params)

        try:
            data = self.fetch_json(
                url,
                params=query_params,
                cache_key=cache_key,
                cache_hours=_CACHE_HOURS,
            )
            return data

        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (401, 403):
                logger.error(
                    "FMP API authentication failed (HTTP %s). "
                    "Check your FMP_API_KEY — it may be invalid or exhausted.",
                    status,
                )
            else:
                logger.error("FMP API HTTP error for %s: %s", endpoint, exc)
            return []

        except requests.exceptions.RequestException as exc:
            logger.error("FMP API request failed for %s: %s", endpoint, exc)
            return []
