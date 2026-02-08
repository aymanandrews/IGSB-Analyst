"""Macro Data Fetcher — Retrieves macroeconomic indicators from the FRED API.

Fetches key series: Treasury yields, credit spreads, GDP, CPI, VIX,
Fed Funds rate, and yield curve data. Computes a simple risk-environment
assessment based on current market conditions.

Usage:
    fetcher = MacroDataFetcher()
    snapshot = fetcher.fetch_macro_snapshot()
    series = fetcher.fetch_series("DGS10", limit=12)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from scripts.base_fetcher import BaseFetcher
from scripts.config import FRED_API_KEY

logger = logging.getLogger(__name__)

# FRED API base URL
_FRED_BASE = "https://api.stlouisfed.org/fred"

# Cache TTL for macro data (hours)
_CACHE_HOURS = 6

# Key FRED series IDs mapped to snapshot field names
_SERIES_MAP: Dict[str, str] = {
    "DGS10": "treasury_10y",
    "BAMLH0A0HYM2": "high_yield_spread",
    "GDP": "gdp_growth",
    "CPIAUCSL": "cpi_yoy",
    "VIXCLS": "vix",
    "FEDFUNDS": "fed_funds_rate",
    "T10Y2Y": "yield_curve_spread",
}


class MacroDataFetcher(BaseFetcher):
    """Fetches macroeconomic data from the Federal Reserve FRED API."""

    source_name: str = "fred"

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def fetch_series(
        self,
        series_id: str,
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        """Fetch recent observations for a single FRED series.

        Args:
            series_id: FRED series identifier (e.g. "DGS10", "VIXCLS").
            limit: Maximum number of observations to return (most recent first).

        Returns:
            List of {"date": "YYYY-MM-DD", "value": float | None} dicts,
            sorted descending by date.  FRED uses "." for missing data;
            those are converted to None.
        """
        if not FRED_API_KEY:
            logger.warning("FRED_API_KEY not set — returning empty series for %s", series_id)
            return []

        cache_key = self._cache_key("series", series_id, str(limit))
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for FRED series %s", series_id)
            return cached  # type: ignore[return-value]

        url = f"{_FRED_BASE}/series/observations"
        params: Dict[str, Any] = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }

        try:
            data = self.fetch_json(url, params=params)
        except Exception:
            logger.exception("Failed to fetch FRED series %s", series_id)
            return []

        observations = data.get("observations", [])
        results: List[Dict[str, Any]] = []
        for obs in observations:
            raw_value = obs.get("value")
            value = _parse_fred_value(raw_value)
            results.append({
                "date": obs.get("date", ""),
                "value": value,
            })

        self._set_cached(cache_key, results)  # type: ignore[arg-type]
        return results

    def fetch_macro_snapshot(self) -> Dict[str, Any]:
        """Fetch latest values for all key macro series and assess risk.

        Returns a dict with current macro indicators and a risk_environment
        classification ("low_risk", "neutral", "elevated", "high_risk").
        Returns an empty dict if FRED_API_KEY is not configured.
        """
        if not FRED_API_KEY:
            logger.warning("FRED_API_KEY not set — returning empty macro snapshot")
            return {}

        cache_key = self._cache_key("macro_snapshot")
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for macro snapshot")
            return cached

        snapshot: Dict[str, Any] = {}

        for series_id, field_name in _SERIES_MAP.items():
            obs = self.fetch_series(series_id, limit=1)
            if obs and obs[0].get("value") is not None:
                snapshot[field_name] = {
                    "value": obs[0]["value"],
                    "date": obs[0]["date"],
                }
            else:
                snapshot[field_name] = {
                    "value": None,
                    "date": None,
                }

        snapshot["risk_environment"] = self._assess_risk_environment(snapshot)

        self._set_cached(cache_key, snapshot)
        return snapshot

    # ------------------------------------------------------------------ #
    #  Risk Assessment                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _assess_risk_environment(data: Dict[str, Any]) -> str:
        """Classify the current risk environment from macro indicators.

        Heuristic based on VIX level, yield curve, and credit spreads:
            - VIX > 25 OR inverted yield curve OR spreads > 5%  -> "high_risk"
            - VIX > 20 OR spreads > 4%                         -> "elevated"
            - VIX < 15 AND spreads < 3%                        -> "low_risk"
            - Otherwise                                        -> "neutral"

        Args:
            data: Macro snapshot dict with nested {"value", "date"} entries.

        Returns:
            One of "low_risk", "neutral", "elevated", "high_risk".
        """
        vix = _extract_value(data, "vix")
        yield_curve = _extract_value(data, "yield_curve_spread")
        hy_spread = _extract_value(data, "high_yield_spread")

        inverted_curve = yield_curve is not None and yield_curve < 0

        # High risk: VIX spike, inverted curve, or very wide credit spreads
        if (vix is not None and vix > 25) or inverted_curve or (hy_spread is not None and hy_spread > 5):
            return "high_risk"

        # Elevated: moderately high VIX or widening spreads
        if (vix is not None and vix > 20) or (hy_spread is not None and hy_spread > 4):
            return "elevated"

        # Low risk: calm VIX and tight spreads
        if (vix is not None and vix < 15) and (hy_spread is not None and hy_spread < 3):
            return "low_risk"

        return "neutral"


# ------------------------------------------------------------------ #
#  Module-level helpers                                               #
# ------------------------------------------------------------------ #

def _parse_fred_value(raw: Any) -> Optional[float]:
    """Convert a FRED observation value to float.

    FRED uses "." to represent missing or unavailable data points.
    Returns None for missing values, otherwise a rounded float.
    """
    if raw is None or raw == ".":
        return None
    try:
        return round(float(raw), 4)
    except (TypeError, ValueError):
        return None


def _extract_value(data: Dict[str, Any], key: str) -> Optional[float]:
    """Safely extract a numeric value from a snapshot entry.

    Each entry in the snapshot dict is {"value": float | None, "date": str}.
    Returns the float value or None.
    """
    entry = data.get(key)
    if entry is None or not isinstance(entry, dict):
        return None
    val = entry.get("value")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
