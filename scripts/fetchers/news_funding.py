"""News & Funding Fetcher — Company news from Finnhub + curated competitor funding data.

Fetches recent company news articles from the Finnhub /company-news endpoint and
combines them with a curated dataset of private competitor funding rounds for the
six tickers tracked by IGSB-Analyst.

Usage:
    fetcher = NewsFundingFetcher()
    news = fetcher.fetch_company_news("APPF", days=30)
    funding = fetcher.fetch_competitor_funding("APPF")
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
_CACHE_HOURS_NEWS = 4       # news is time-sensitive
_CACHE_HOURS_FUNDING = 168  # curated data, refreshed weekly at most


# ------------------------------------------------------------------ #
#  Curated private-competitor funding data                            #
# ------------------------------------------------------------------ #
#  Private company funding rounds are not freely available via APIs.  #
#  This curated dataset covers 2-4 key private competitors for each  #
#  ticker tracked by IGSB-Analyst.                                    #
# ------------------------------------------------------------------ #

COMPETITOR_FUNDING: Dict[str, List[Dict[str, Any]]] = {
    "APPF": [
        {
            "company": "Entrata",
            "stage": "Late Stage",
            "date": "2021-10-15",
            "amount": 507_000_000,
            "lead_investor": "Silver Lake",
            "valuation": 4_000_000_000,
            "key_news": "Major multifamily property management platform; direct competitor to AppFolio in rental management SaaS",
            "threat_level": "high",
        },
        {
            "company": "RealPage",
            "stage": "Take-Private",
            "date": "2021-04-22",
            "amount": 10_200_000_000,
            "lead_investor": "Thoma Bravo",
            "valuation": 10_200_000_000,
            "key_news": "Taken private by Thoma Bravo; largest PropTech competitor with full-stack property management suite",
            "threat_level": "high",
        },
        {
            "company": "Buildium",
            "stage": "Acquired",
            "date": "2019-12-01",
            "amount": 580_000_000,
            "lead_investor": "RealPage (acquirer)",
            "valuation": 580_000_000,
            "key_news": "Acquired by RealPage; strong in small/mid property management segment that overlaps with AppFolio's core",
            "threat_level": "medium",
        },
        {
            "company": "Yardi Systems",
            "stage": "Private (bootstrapped)",
            "date": "2024-01-15",
            "amount": 0,
            "lead_investor": "N/A (founder-owned)",
            "valuation": 8_000_000_000,
            "key_news": "Privately held since 1984; dominant in enterprise property management; expanding into mid-market where AppFolio operates",
            "threat_level": "high",
        },
    ],
    "RBLX": [
        {
            "company": "Epic Games",
            "stage": "Late Stage",
            "date": "2022-04-11",
            "amount": 2_000_000_000,
            "lead_investor": "Sony Group",
            "valuation": 31_500_000_000,
            "key_news": "Fortnite Creative and Unreal Engine pose direct UGC platform threat; expanding metaverse ambitions",
            "threat_level": "high",
        },
        {
            "company": "Rec Room",
            "stage": "Series D",
            "date": "2022-03-22",
            "amount": 145_000_000,
            "lead_investor": "Coatue Management",
            "valuation": 3_500_000_000,
            "key_news": "Cross-platform social gaming with user-created rooms; targets similar young demographic",
            "threat_level": "medium",
        },
        {
            "company": "Manticore Games",
            "stage": "Series B",
            "date": "2021-03-01",
            "amount": 100_000_000,
            "lead_investor": "SoftBank Vision Fund",
            "valuation": 1_300_000_000,
            "key_news": "Core platform enables user-generated multiplayer games; direct UGC gaming competitor",
            "threat_level": "medium",
        },
    ],
    "WDAY": [
        {
            "company": "Rippling",
            "stage": "Series E",
            "date": "2024-03-11",
            "amount": 200_000_000,
            "lead_investor": "Coatue Management",
            "valuation": 13_500_000_000,
            "key_news": "Unified HR/IT/Finance platform growing rapidly in mid-market; aggressive sales motion targeting Workday's installed base",
            "threat_level": "high",
        },
        {
            "company": "Deel",
            "stage": "Series D",
            "date": "2022-05-18",
            "amount": 50_000_000,
            "lead_investor": "Coatue Management",
            "valuation": 12_000_000_000,
            "key_news": "Global payroll and HR compliance platform; attacking Workday's international payroll weakness",
            "threat_level": "high",
        },
        {
            "company": "Lattice",
            "stage": "Series F",
            "date": "2022-01-25",
            "amount": 175_000_000,
            "lead_investor": "Tiger Global",
            "valuation": 3_000_000_000,
            "key_news": "Performance management and engagement platform competing with Workday's HCM talent modules",
            "threat_level": "medium",
        },
    ],
    "PCOR": [
        {
            "company": "PlanGrid",
            "stage": "Acquired",
            "date": "2018-12-20",
            "amount": 875_000_000,
            "lead_investor": "Autodesk (acquirer)",
            "valuation": 875_000_000,
            "key_news": "Now part of Autodesk Construction Cloud; competes head-to-head with Procore in field collaboration",
            "threat_level": "high",
        },
        {
            "company": "Fieldwire",
            "stage": "Acquired",
            "date": "2022-01-10",
            "amount": 300_000_000,
            "lead_investor": "Hilti Group (acquirer)",
            "valuation": 300_000_000,
            "key_news": "Field management software for construction; acquired by Hilti to bolster digital construction tools",
            "threat_level": "medium",
        },
        {
            "company": "Buildertrend",
            "stage": "Growth Equity",
            "date": "2021-07-15",
            "amount": 150_000_000,
            "lead_investor": "Bain Capital Tech Opportunities",
            "valuation": 1_500_000_000,
            "key_news": "Residential construction project management; expanding into commercial segment that overlaps with Procore",
            "threat_level": "medium",
        },
    ],
    "TTAN": [
        {
            "company": "Jobber",
            "stage": "Series D",
            "date": "2022-01-19",
            "amount": 100_000_000,
            "lead_investor": "Summit Partners",
            "valuation": 900_000_000,
            "key_news": "Field service management for home service SMBs; strong overlap with Titan Machinery's service operations software",
            "threat_level": "medium",
        },
        {
            "company": "ServiceTitan",
            "stage": "Series H",
            "date": "2022-11-01",
            "amount": 365_000_000,
            "lead_investor": "Tiger Global",
            "valuation": 9_500_000_000,
            "key_news": "Leading field service management platform; dominates HVAC/plumbing/electrical verticals adjacent to TTAN's markets",
            "threat_level": "high",
        },
        {
            "company": "Housecall Pro",
            "stage": "Series D",
            "date": "2022-07-20",
            "amount": 125_000_000,
            "lead_investor": "Permira",
            "valuation": 1_200_000_000,
            "key_news": "Home services management platform for SMBs; competes for same contractor/technician workflow segment",
            "threat_level": "medium",
        },
    ],
    "VEEV": [
        {
            "company": "Medidata Solutions",
            "stage": "Acquired",
            "date": "2019-10-29",
            "amount": 5_800_000_000,
            "lead_investor": "Dassault Systemes (acquirer)",
            "valuation": 5_800_000_000,
            "key_news": "Clinical trial data platform acquired by Dassault; competes with Veeva Vault CDMS in clinical data management",
            "threat_level": "high",
        },
        {
            "company": "Benchling",
            "stage": "Series F",
            "date": "2021-12-14",
            "amount": 200_000_000,
            "lead_investor": "Sequoia Capital",
            "valuation": 6_100_000_000,
            "key_news": "R&D cloud for biotech/pharma; threatens Veeva's life sciences data management with modern UX and open architecture",
            "threat_level": "high",
        },
        {
            "company": "Vault Biologics (Dotmatics)",
            "stage": "Growth Equity",
            "date": "2022-02-01",
            "amount": 370_000_000,
            "lead_investor": "Insight Partners",
            "valuation": 4_200_000_000,
            "key_news": "Scientific data platform merging multiple acquisitions; competes with Veeva in preclinical and regulatory data workflows",
            "threat_level": "medium",
        },
    ],
}


# ------------------------------------------------------------------ #
#  Fetcher class                                                      #
# ------------------------------------------------------------------ #


class NewsFundingFetcher(BaseFetcher):
    """Aggregates company news (via Finnhub) and curated private-competitor funding data."""

    source_name: str = "news_funding"

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _check_api_key(self) -> bool:
        """Return True if the Finnhub API key is configured, False otherwise."""
        if not FINNHUB_API_KEY:
            logger.warning(
                "FINNHUB_API_KEY is not set — skipping news fetch. "
                "Set it in your .env file to enable Finnhub news data."
            )
            return False
        return True

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def fetch_company_news(
        self, ticker: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Fetch recent company news articles from Finnhub /company-news endpoint.

        Each article is returned with headline, summary, url, date, source,
        and a keyword-based sentiment label (positive / negative / neutral).

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").
            days: Number of days of news history to fetch (default 30).

        Returns:
            List of up to 50 news items sorted newest-first. Empty list if
            the Finnhub API key is not configured or the request fails.
        """
        ticker = ticker.upper().strip()

        # Check cache first
        cache_key = self._cache_key("company_news", ticker, str(days))
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS_NEWS)
        if cached is not None:
            logger.info("Cache hit for %s company news", ticker)
            return cached.get("articles", [])

        if not self._check_api_key():
            return []

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            url = f"{_BASE_URL}/company-news"
            params: Dict[str, str] = {
                "symbol": ticker,
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d"),
                "token": FINNHUB_API_KEY,
            }

            resp = self.fetch_with_retry(url, params=params)
            data = resp.json()

            if not isinstance(data, list):
                logger.warning("Unexpected response type for %s news: %s", ticker, type(data))
                return []

            # Normalize and enrich with sentiment — Finnhub returns newest first
            articles: List[Dict[str, Any]] = []
            for item in data[:50]:
                raw_dt = item.get("datetime")
                if isinstance(raw_dt, (int, float)) and raw_dt > 0:
                    date_str = datetime.utcfromtimestamp(raw_dt).strftime("%Y-%m-%d")
                elif isinstance(raw_dt, str):
                    date_str = raw_dt
                else:
                    date_str = ""

                headline = item.get("headline", "")
                articles.append({
                    "headline": headline,
                    "summary": item.get("summary", ""),
                    "url": item.get("url", ""),
                    "date": date_str,
                    "source": item.get("source", ""),
                    "sentiment": _classify_sentiment(headline),
                })

            # Cache the enriched result
            self._set_cached(cache_key, {"articles": articles})
            logger.info("Fetched %d news articles for %s", len(articles), ticker)
            return articles

        except Exception:
            logger.exception("Failed to fetch company news for %s", ticker)
            return []

    def fetch_competitor_funding(self, ticker: str) -> List[Dict[str, Any]]:
        """Return curated private competitor funding rounds for the given ticker.

        Since private-company funding data is not freely available via public
        APIs, this method draws from the hardcoded ``COMPETITOR_FUNDING`` dict
        which covers 2-4 key private competitors for each of the six covered
        tickers (APPF, RBLX, WDAY, PCOR, TTAN, VEEV).

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").

        Returns:
            List of funding round dicts, each with fields: company, stage,
            date, amount, lead_investor, valuation, key_news, threat_level.
            Empty list for uncovered tickers.
        """
        ticker = ticker.upper().strip()

        # Funding data is curated/static, but we still cache to follow the
        # BaseFetcher pattern and allow override via cache file edits.
        cache_key = self._cache_key("competitor_funding", ticker)
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS_FUNDING)
        if cached is not None:
            logger.info("Cache hit for %s competitor funding", ticker)
            return cached.get("rounds", [])

        rounds = COMPETITOR_FUNDING.get(ticker, [])

        if not rounds:
            logger.info("No curated competitor funding data for %s", ticker)
        else:
            logger.info(
                "Loaded %d competitor funding rounds for %s", len(rounds), ticker
            )

        # Cache the curated data
        self._set_cached(cache_key, {"rounds": rounds})
        return rounds

    def fetch_all(self, ticker: str) -> Dict[str, Any]:
        """Fetch all news and funding data for a ticker.

        Combines company news (via Finnhub) and curated private-competitor
        funding rounds into a single response dict.  Individual failures are
        isolated — a failed news fetch returns an empty list without blocking
        the funding lookup.

        Args:
            ticker: Company stock ticker symbol.

        Returns:
            Dict with keys: ``news`` (list of articles) and
            ``funding_rounds`` (list of funding round dicts).
        """
        ticker = ticker.upper().strip()

        return {
            "news": self.fetch_company_news(ticker),
            "funding_rounds": self.fetch_competitor_funding(ticker),
        }


# ------------------------------------------------------------------ #
#  Sentiment helper (module-level for reuse)                          #
# ------------------------------------------------------------------ #

_POSITIVE_KEYWORDS = frozenset({
    "surge", "surges", "surging",
    "beat", "beats", "beating",
    "record",
    "growth", "growing",
    "upgrade", "upgrades", "upgraded",
    "raise", "raises", "raised",
    "gain", "gains",
    "profit", "profitable",
    "outperform", "outperforms",
    "rally", "rallies",
    "strong", "strength",
    "accelerate", "accelerates",
    "expand", "expands", "expansion",
    "exceed", "exceeds", "exceeded",
    "soar", "soars",
    "boost", "boosts",
    "win", "wins",
    "positive",
    "uptick",
    "bullish",
})

_NEGATIVE_KEYWORDS = frozenset({
    "miss", "misses", "missed",
    "decline", "declines", "declining",
    "downgrade", "downgrades", "downgraded",
    "layoff", "layoffs",
    "cut", "cuts",
    "loss", "losses",
    "drop", "drops", "dropping",
    "fall", "falls", "falling",
    "weak", "weakness",
    "slow", "slows", "slowdown",
    "concern", "concerns",
    "warning", "warns",
    "risk", "risks",
    "plunge", "plunges",
    "tumble", "tumbles",
    "underperform", "underperforms",
    "bearish",
    "shortfall",
    "disappoint", "disappoints", "disappointing",
})


def _classify_sentiment(headline: str) -> str:
    """Return 'positive', 'negative', or 'neutral' based on headline keywords.

    Uses a simple bag-of-words heuristic: count matches against positive and
    negative keyword sets and compare.  Ties resolve to 'neutral'.
    """
    words = set(headline.lower().split())
    pos_count = len(words & _POSITIVE_KEYWORDS)
    neg_count = len(words & _NEGATIVE_KEYWORDS)

    if pos_count > neg_count:
        return "positive"
    if neg_count > pos_count:
        return "negative"
    return "neutral"
