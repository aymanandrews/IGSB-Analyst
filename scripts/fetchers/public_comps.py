"""Public Comps Fetcher — Build comparable company valuation tables.

Fetches financial data for a curated set of peer companies and computes
valuation multiples, growth metrics, and median benchmarks for the group.

Primary data source is FMP (profile + key_metrics). Falls back to Finnhub
basic_financials when FMP data is unavailable.

Usage:
    fetcher = PublicCompsFetcher()
    comps = fetcher.fetch_comps("APPF")
"""
from __future__ import annotations

import logging
import statistics
from typing import Any, Dict, List, Optional

from scripts.base_fetcher import BaseFetcher
from scripts.fetchers.fmp_fundamentals import FMPFetcher
from scripts.fetchers.finnhub_data import FinnhubFetcher

logger = logging.getLogger(__name__)

# Cache TTL for comp tables (hours)
_CACHE_HOURS = 12

# Curated peer groups for covered tickers
PEER_GROUPS: Dict[str, List[str]] = {
    "APPF": ["PCOR", "TTAN", "VEEV", "GWRE", "CW", "ZI", "NCNO"],
    "RBLX": ["U", "EA", "TTWO", "ZNGA", "BMBL", "MTCH"],
    "WDAY": ["NOW", "CRM", "SAP", "ORCL", "INTU", "PAYC"],
    "PCOR": ["APPF", "TTAN", "ADSK", "PTC", "ANSS", "BLDR"],
    "TTAN": ["APPF", "PCOR", "SQ", "BILL", "HUBS", "PAYC"],
    "VEEV": ["APPF", "CRM", "NOW", "MDSO", "IQVIA", "DOCS"],
}


def _median(values: List[Optional[float]]) -> Optional[float]:
    """Compute median of a list, excluding None values.

    Args:
        values: List of floats (may contain None).

    Returns:
        Median as a float rounded to 4 decimal places, or None if no
        valid values are present.
    """
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(statistics.median(clean), 4)


def _safe_float(value: Any) -> Optional[float]:
    """Coerce a value to float, returning None for non-numeric inputs."""
    if value is None:
        return None
    try:
        f = float(value)
        return f
    except (TypeError, ValueError):
        return None


class PublicCompsFetcher(BaseFetcher):
    """Builds public comparable company tables with valuation multiples."""

    source_name: str = "comps"

    def __init__(self) -> None:
        super().__init__()
        self._fmp = FMPFetcher()
        self._finnhub = FinnhubFetcher()

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def fetch_comps(self, ticker: str) -> Dict[str, Any]:
        """Build a comparable company table for the given ticker.

        Fetches financial profile and metrics for each peer in the curated
        peer group, computes derived valuation multiples, and calculates
        group medians.

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").

        Returns:
            Dict matching the PublicComps schema:
                comps: list of comp entry dicts
                median_ev_revenue: median EV/Revenue across comps
                median_ev_ebitda: median EV/EBITDA across comps
                median_revenue_growth: median revenue growth across comps
        """
        ticker = ticker.upper().strip()

        cache_key = self._cache_key("comps", ticker)
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for %s comps table", ticker)
            return cached

        peers = PEER_GROUPS.get(ticker, [])
        if not peers:
            logger.warning(
                "No curated peer group for %s. Returning empty comps.", ticker
            )
            return self._empty_result()

        logger.info(
            "Building comps table for %s with %d peers: %s",
            ticker, len(peers), ", ".join(peers),
        )

        comps: List[Dict[str, Any]] = []
        for peer_ticker in peers:
            comp = self._build_comp_metrics(peer_ticker)
            if comp is not None:
                comps.append(comp)
            else:
                logger.warning("Skipping peer %s — no data available", peer_ticker)

        # Compute group medians
        ev_revenues = [c.get("ev_revenue") for c in comps]
        ev_ebitdas = [c.get("ev_ebitda") for c in comps]
        rev_growths = [c.get("revenue_growth") for c in comps]

        result: Dict[str, Any] = {
            "comps": comps,
            "median_ev_revenue": _median(ev_revenues),
            "median_ev_ebitda": _median(ev_ebitdas),
            "median_revenue_growth": _median(rev_growths),
        }

        self._set_cached(cache_key, result)
        return result

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _build_comp_metrics(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Build a single comp entry from FMP data, falling back to Finnhub.

        Args:
            ticker: Peer company ticker symbol.

        Returns:
            Dict with comp metrics, or None if no data could be retrieved.
        """
        ticker = ticker.upper().strip()

        # Try FMP first (primary source)
        profile = self._fmp.fetch_profile(ticker)
        metrics_list = self._fmp.fetch_key_metrics(ticker, period="annual", limit=1)
        metrics = metrics_list[0] if metrics_list else {}

        if profile:
            return self._comp_from_fmp(ticker, profile, metrics)

        # Fallback to Finnhub basic_financials
        logger.info("FMP unavailable for %s, trying Finnhub fallback", ticker)
        finnhub_data = self._finnhub.fetch_basic_financials(ticker)
        if finnhub_data:
            return self._comp_from_finnhub(ticker, finnhub_data)

        return None

    def _comp_from_fmp(
        self,
        ticker: str,
        profile: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build comp entry from FMP profile and key_metrics data.

        Args:
            ticker: Peer company ticker.
            profile: FMP /profile response dict.
            metrics: Most recent entry from FMP /key-metrics response.

        Returns:
            Dict with standardized comp fields.
        """
        market_cap = _safe_float(profile.get("mktCap"))
        ev = self._compute_ev(profile, metrics)
        revenue = _safe_float(metrics.get("revenuePerShareTTM"))
        shares = _safe_float(profile.get("sharesOutstanding"))

        # Annualize revenue from per-share if both available
        total_revenue: Optional[float] = None
        if revenue is not None and shares is not None and shares > 0:
            total_revenue = round(revenue * shares, 2)
        # Prefer direct revenue if available in profile
        if profile.get("revenue"):
            total_revenue = _safe_float(profile.get("revenue"))

        revenue_growth = _safe_float(metrics.get("revenueGrowth"))
        gross_margin = _safe_float(metrics.get("grossProfitMarginTTM"))
        if gross_margin is None:
            gross_margin = _safe_float(profile.get("grossMargin"))
        operating_margin = _safe_float(metrics.get("operatingProfitMarginTTM"))
        if operating_margin is None:
            operating_margin = _safe_float(profile.get("operatingMargin"))

        pe_ratio = _safe_float(metrics.get("peRatioTTM"))
        if pe_ratio is None:
            pe_ratio = _safe_float(profile.get("peRatio"))

        fcf_margin = _safe_float(metrics.get("freeCashFlowMarginTTM"))

        # Derived multiples
        ev_revenue = self._safe_divide(ev, total_revenue)
        ev_ebitda = _safe_float(metrics.get("enterpriseValueOverEBITDATTM"))

        # Rule of 40 = revenue_growth (%) + fcf_margin (%)
        rule_of_40 = self._calc_rule_of_40(revenue_growth, fcf_margin)

        return {
            "ticker": ticker,
            "name": profile.get("companyName", ticker),
            "market_cap": market_cap,
            "ev": ev,
            "revenue": total_revenue,
            "revenue_growth": revenue_growth,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "ev_revenue": ev_revenue,
            "ev_ebitda": ev_ebitda,
            "pe_ratio": pe_ratio,
            "fcf_margin": fcf_margin,
            "rule_of_40": rule_of_40,
        }

    def _comp_from_finnhub(
        self,
        ticker: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build comp entry from Finnhub basic_financials as fallback.

        Finnhub's /stock/metric?metric=all returns a "metric" sub-dict
        with various financial ratios and values.

        Args:
            ticker: Peer company ticker.
            data: Finnhub /stock/metric response dict.

        Returns:
            Dict with standardized comp fields (many may be None).
        """
        m = data.get("metric", {})

        market_cap = _safe_float(m.get("marketCapitalization"))
        # Finnhub reports market cap in millions; convert to absolute
        if market_cap is not None:
            market_cap = market_cap * 1_000_000

        revenue = _safe_float(m.get("revenuePerShareTTM"))
        # Revenue per share without shares outstanding isn't useful for totals
        # Try annual revenue if available
        total_revenue = _safe_float(m.get("revenueTTM"))

        revenue_growth = _safe_float(m.get("revenueGrowthTTM5Y"))
        gross_margin = _safe_float(m.get("grossMarginTTM"))
        operating_margin = _safe_float(m.get("operatingMarginTTM"))
        pe_ratio = _safe_float(m.get("peTTM"))

        # Finnhub doesn't directly provide EV, approximate from market cap
        ev = _safe_float(m.get("enterpriseValueTTM"))
        if ev is not None:
            ev = ev * 1_000_000  # Finnhub reports in millions

        ev_revenue = self._safe_divide(ev, total_revenue)
        ev_ebitda = _safe_float(m.get("enterpriseValue/ebitdaTTM"))

        fcf_margin = _safe_float(m.get("freeCashFlowMarginTTM"))

        rule_of_40 = self._calc_rule_of_40(revenue_growth, fcf_margin)

        return {
            "ticker": ticker,
            "name": ticker,  # Finnhub basic_financials doesn't include name
            "market_cap": market_cap,
            "ev": ev,
            "revenue": total_revenue,
            "revenue_growth": revenue_growth,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "ev_revenue": ev_revenue,
            "ev_ebitda": ev_ebitda,
            "pe_ratio": pe_ratio,
            "fcf_margin": fcf_margin,
            "rule_of_40": rule_of_40,
        }

    @staticmethod
    def _compute_ev(
        profile: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Optional[float]:
        """Compute enterprise value from profile and metrics data.

        Prefers the direct enterprise value field. Falls back to
        market_cap + total_debt - cash approximation.

        Args:
            profile: FMP profile dict.
            metrics: FMP key_metrics dict.

        Returns:
            Enterprise value as float, or None.
        """
        # Direct EV from metrics
        ev = _safe_float(metrics.get("enterpriseValueTTM"))
        if ev is not None:
            return ev

        ev = _safe_float(metrics.get("enterpriseValue"))
        if ev is not None:
            return ev

        # Approximate: market_cap + debt - cash
        market_cap = _safe_float(profile.get("mktCap"))
        if market_cap is None:
            return None

        debt = _safe_float(metrics.get("totalDebtToEquityTTM"))
        cash = _safe_float(metrics.get("cashPerShareTTM"))
        shares = _safe_float(profile.get("sharesOutstanding"))

        # If we can't get debt/cash components, just use market cap as proxy
        if debt is None or cash is None or shares is None:
            return market_cap

        total_cash = cash * shares if shares else 0
        return market_cap - total_cash

    @staticmethod
    def _safe_divide(
        numerator: Optional[float],
        denominator: Optional[float],
    ) -> Optional[float]:
        """Safely divide two values, returning None if either is None or denominator is zero.

        Args:
            numerator: The dividend.
            denominator: The divisor.

        Returns:
            Rounded quotient, or None.
        """
        if numerator is None or denominator is None or denominator == 0:
            return None
        return round(numerator / denominator, 4)

    @staticmethod
    def _calc_rule_of_40(
        revenue_growth: Optional[float],
        fcf_margin: Optional[float],
    ) -> Optional[float]:
        """Calculate Rule of 40 score.

        Rule of 40 = revenue_growth (as %) + fcf_margin (as %).
        Both inputs are expected as decimals (e.g. 0.22 for 22%).
        Output is in percentage points (e.g. 30 means 30%).

        Args:
            revenue_growth: Revenue growth as a decimal (e.g. 0.22).
            fcf_margin: Free cash flow margin as a decimal (e.g. 0.08).

        Returns:
            Rule of 40 score in percentage points, or None.
        """
        if revenue_growth is None and fcf_margin is None:
            return None

        growth_pct = (revenue_growth * 100) if revenue_growth is not None else 0.0
        fcf_pct = (fcf_margin * 100) if fcf_margin is not None else 0.0

        return round(growth_pct + fcf_pct, 2)

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        """Return a valid but empty PublicComps-shaped dict."""
        return {
            "comps": [],
            "median_ev_revenue": None,
            "median_ev_ebitda": None,
            "median_revenue_growth": None,
        }
