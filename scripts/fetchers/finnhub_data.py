"""Finnhub Data Fetcher — Peer data, news, analyst recommendations, and metrics.

Uses the Finnhub API (https://finnhub.io/api/v1) to fetch supplementary market
data including peer comparisons, company news, analyst consensus, price targets,
and basic financial metrics.

Usage:
    fetcher = FinnhubFetcher()
    peers = fetcher.fetch_peers("APPF")
    news = fetcher.fetch_company_news("APPF", days=30)
    all_data = fetcher.fetch_all("APPF")
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from scripts.base_fetcher import BaseFetcher
from scripts.config import FINNHUB_API_KEY

logger = logging.getLogger(__name__)

_BASE_URL = "https://finnhub.io/api/v1"

# Cache TTLs (hours)
_CACHE_HOURS_LONG = 24   # peers, financials, price targets, recommendations
_CACHE_HOURS_SHORT = 4   # news (more time-sensitive)


class FinnhubFetcher(BaseFetcher):
    """Fetches peer data, news, analyst recommendations, and metrics from Finnhub."""

    source_name: str = "finnhub"

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _check_api_key(self) -> bool:
        """Return True if the API key is configured, False otherwise."""
        if not FINNHUB_API_KEY:
            logger.warning(
                "FINNHUB_API_KEY is not set — skipping Finnhub fetch. "
                "Set it in your .env file to enable Finnhub data."
            )
            return False
        return True

    def _build_url(self, path: str) -> str:
        """Build a full Finnhub API URL for the given endpoint path."""
        return f"{_BASE_URL}{path}"

    def _default_params(self) -> Dict[str, str]:
        """Return the base query parameters with authentication token."""
        return {"token": FINNHUB_API_KEY}

    def _fetch(
        self,
        path: str,
        extra_params: Optional[Dict[str, str]] = None,
        cache_key: Optional[str] = None,
        cache_hours: int = _CACHE_HOURS_LONG,
    ) -> Any:
        """Fetch JSON from a Finnhub endpoint with caching and error handling.

        Handles 429 rate-limit responses by relying on BaseFetcher's retry
        logic (exponential backoff in fetch_with_retry).

        Args:
            path: API endpoint path (e.g. "/stock/peers").
            extra_params: Additional query parameters beyond the auth token.
            cache_key: Optional cache key; if provided, results are cached.
            cache_hours: Cache TTL in hours.

        Returns:
            Parsed JSON response (dict or list).
        """
        params = self._default_params()
        if extra_params:
            params.update(extra_params)

        return self.fetch_json(
            url=self._build_url(path),
            params=params,
            cache_key=cache_key,
            cache_hours=cache_hours,
        )

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def fetch_peers(self, ticker: str) -> List[str]:
        """Fetch peer/comparable company ticker symbols.

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").

        Returns:
            List of peer ticker symbols. Empty list if API key is missing
            or the request fails.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return []

        cache_key = self._cache_key("peers", ticker)

        try:
            data = self._fetch(
                "/stock/peers",
                extra_params={"symbol": ticker},
                cache_key=cache_key,
                cache_hours=_CACHE_HOURS_LONG,
            )
            # API returns a list of tickers; first element is the queried ticker itself
            if isinstance(data, list):
                return [t for t in data if t != ticker]
            return []
        except Exception:
            logger.exception("Failed to fetch peers for %s", ticker)
            return []

    def fetch_company_news(
        self, ticker: str, days: int = 90
    ) -> List[Dict[str, Any]]:
        """Fetch recent company news articles.

        Args:
            ticker: Company stock ticker symbol.
            days: Number of days of news to look back (default 90).

        Returns:
            List of up to 20 news items, each with keys: headline, summary,
            url, datetime, source. Empty list if API key is missing or the
            request fails.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return []

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        cache_key = self._cache_key("news", ticker, str(days))

        try:
            data = self._fetch(
                "/company-news",
                extra_params={
                    "symbol": ticker,
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                },
                cache_key=cache_key,
                cache_hours=_CACHE_HOURS_SHORT,
            )

            if not isinstance(data, list):
                return []

            # Normalize and limit to 20 most recent items
            # Finnhub returns news sorted newest-first by default
            articles: List[Dict[str, Any]] = []
            for item in data[:20]:
                articles.append({
                    "headline": item.get("headline", ""),
                    "summary": item.get("summary", ""),
                    "url": item.get("url", ""),
                    "datetime": item.get("datetime"),
                    "source": item.get("source", ""),
                })
            return articles

        except Exception:
            logger.exception("Failed to fetch news for %s", ticker)
            return []

    def fetch_recommendation_trends(
        self, ticker: str
    ) -> List[Dict[str, Any]]:
        """Fetch analyst recommendation trends (buy/hold/sell counts).

        Args:
            ticker: Company stock ticker symbol.

        Returns:
            List of recommendation periods, each with keys: period,
            strongBuy, buy, hold, sell, strongSell. Empty list if API key
            is missing or the request fails.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return []

        cache_key = self._cache_key("recommendations", ticker)

        try:
            data = self._fetch(
                "/stock/recommendation",
                extra_params={"symbol": ticker},
                cache_key=cache_key,
                cache_hours=_CACHE_HOURS_LONG,
            )
            if isinstance(data, list):
                return data
            return []
        except Exception:
            logger.exception("Failed to fetch recommendations for %s", ticker)
            return []

    def fetch_price_target(self, ticker: str) -> Dict[str, Any]:
        """Fetch analyst consensus price target.

        Args:
            ticker: Company stock ticker symbol.

        Returns:
            Dict with keys: targetHigh, targetLow, targetMean, targetMedian,
            lastUpdated. Empty dict if API key is missing or the request fails.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return {}

        cache_key = self._cache_key("price_target", ticker)

        try:
            data = self._fetch(
                "/stock/price-target",
                extra_params={"symbol": ticker},
                cache_key=cache_key,
                cache_hours=_CACHE_HOURS_LONG,
            )
            if isinstance(data, dict):
                return {
                    "targetHigh": data.get("targetHigh"),
                    "targetLow": data.get("targetLow"),
                    "targetMean": data.get("targetMean"),
                    "targetMedian": data.get("targetMedian"),
                    "lastUpdated": data.get("lastUpdated"),
                }
            return {}
        except Exception:
            logger.exception("Failed to fetch price target for %s", ticker)
            return {}

    def fetch_basic_financials(self, ticker: str) -> Dict[str, Any]:
        """Fetch comprehensive financial metrics (52-week high/low, beta, PE, etc.).

        Args:
            ticker: Company stock ticker symbol.

        Returns:
            Dict with a "metric" key containing all available metrics, plus
            "metricType" and "symbol". Empty dict if API key is missing or
            the request fails.
        """
        ticker = ticker.upper().strip()
        if not self._check_api_key():
            return {}

        cache_key = self._cache_key("basic_financials", ticker)

        try:
            data = self._fetch(
                "/stock/metric",
                extra_params={"symbol": ticker, "metric": "all"},
                cache_key=cache_key,
                cache_hours=_CACHE_HOURS_LONG,
            )
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            logger.exception("Failed to fetch basic financials for %s", ticker)
            return {}

    def fetch_all(self, ticker: str) -> Dict[str, Any]:
        """Convenience method to fetch all Finnhub data for a ticker.

        Calls each individual fetch method and aggregates results into a
        single dictionary. Individual failures are isolated -- a failed
        sub-fetch returns its empty default without blocking the others.

        Args:
            ticker: Company stock ticker symbol.

        Returns:
            Dict with keys: peers, news, recommendations, price_target,
            basic_financials.
        """
        ticker = ticker.upper().strip()

        return {
            "peers": self.fetch_peers(ticker),
            "news": self.fetch_company_news(ticker),
            "recommendations": self.fetch_recommendation_trends(ticker),
            "price_target": self.fetch_price_target(ticker),
            "basic_financials": self.fetch_basic_financials(ticker),
        }
