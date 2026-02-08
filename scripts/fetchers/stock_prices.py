"""Stock Price Fetcher — Retrieves price history and returns from Yahoo Finance."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import yfinance as yf
import pandas as pd

from scripts.base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

# Cache TTL for market data (hours)
_CACHE_HOURS = 4


class StockPriceFetcher(BaseFetcher):
    """Fetches stock price data, returns, and benchmark comparisons via yfinance."""

    source_name: str = "yfinance"

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def fetch_stock_data(self, ticker: str) -> Dict[str, Any]:
        """Fetch comprehensive stock data for a ticker.

        Returns a dict matching the StockPerformance schema:
            current_price, price_history, returns_*, beta,
            high_52w, low_52w, avg_volume_30d
        """
        ticker = ticker.upper().strip()
        cache_key = self._cache_key("stock", ticker)
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for %s stock data", ticker)
            return cached

        logger.info("Fetching stock data for %s from yfinance", ticker)
        self.rate_limiter.wait()

        try:
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period="2y")
        except Exception as exc:
            logger.error("yfinance error fetching %s: %s", ticker, exc)
            return self._empty_result()

        if hist.empty:
            logger.warning("No price history returned for %s", ticker)
            return self._empty_result()

        info = self._safe_info(ticker_obj)

        result: Dict[str, Any] = {
            "current_price": self._current_price(hist, info),
            "price_history": self._weekly_price_history(hist),
            "returns_1m": self._calc_return(hist, days=21),
            "returns_3m": self._calc_return(hist, days=63),
            "returns_6m": self._calc_return(hist, days=126),
            "returns_1y": self._calc_return(hist, days=252),
            "returns_ytd": self._calc_return_ytd(hist),
            "beta": info.get("beta"),
            "high_52w": self._52w_high(hist, info),
            "low_52w": self._52w_low(hist, info),
            "avg_volume_30d": self._avg_volume_30d(hist),
        }

        self._set_cached(cache_key, result)
        return result

    def fetch_benchmark_returns(
        self, benchmark: str = "SPY"
    ) -> Dict[str, Optional[float]]:
        """Fetch return metrics for a benchmark ticker (default SPY).

        Returns a dict with returns_1m, returns_3m, returns_6m,
        returns_1y, and returns_ytd as decimal floats.
        """
        benchmark = benchmark.upper().strip()
        cache_key = self._cache_key("benchmark", benchmark)
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for %s benchmark data", benchmark)
            return cached

        logger.info("Fetching benchmark data for %s", benchmark)
        self.rate_limiter.wait()

        try:
            ticker_obj = yf.Ticker(benchmark)
            hist = ticker_obj.history(period="2y")
        except Exception as exc:
            logger.error("yfinance error fetching benchmark %s: %s", benchmark, exc)
            return self._empty_benchmark()

        if hist.empty:
            logger.warning("No price history returned for benchmark %s", benchmark)
            return self._empty_benchmark()

        result: Dict[str, Optional[float]] = {
            "ticker": benchmark,
            "returns_1m": self._calc_return(hist, days=21),
            "returns_3m": self._calc_return(hist, days=63),
            "returns_6m": self._calc_return(hist, days=126),
            "returns_1y": self._calc_return(hist, days=252),
            "returns_ytd": self._calc_return_ytd(hist),
        }

        self._set_cached(cache_key, result)
        return result

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _safe_info(ticker_obj: yf.Ticker) -> Dict[str, Any]:
        """Safely retrieve ticker.info, returning empty dict on failure."""
        try:
            return ticker_obj.info or {}
        except Exception:
            return {}

    @staticmethod
    def _current_price(
        hist: pd.DataFrame, info: Dict[str, Any]
    ) -> Optional[float]:
        """Best-effort current price: prefer info, fall back to last close."""
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is not None:
            return round(float(price), 2)
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
        return None

    @staticmethod
    def _weekly_price_history(hist: pd.DataFrame) -> List[Dict[str, Any]]:
        """Resample daily history to weekly (last close of each week).

        Returns a list of {date, close, volume} dicts sorted ascending.
        """
        if hist.empty:
            return []

        weekly = hist[["Close", "Volume"]].resample("W").agg(
            {"Close": "last", "Volume": "sum"}
        )
        weekly = weekly.dropna(subset=["Close"])

        records: List[Dict[str, Any]] = []
        for idx, row in weekly.iterrows():
            records.append(
                {
                    "date": idx.strftime("%Y-%m-%d"),
                    "close": round(float(row["Close"]), 2),
                    "volume": round(float(row["Volume"])),
                }
            )
        return records

    @staticmethod
    def _calc_return(
        hist: pd.DataFrame, days: int
    ) -> Optional[float]:
        """Calculate price return over the last N trading days.

        Returns a decimal float (e.g. 0.05 for 5%) or None.
        """
        if hist.empty or len(hist) < 2:
            return None

        end_price = float(hist["Close"].iloc[-1])
        offset = min(days, len(hist) - 1)
        start_price = float(hist["Close"].iloc[-1 - offset])

        if start_price == 0:
            return None

        return round((end_price - start_price) / start_price, 6)

    @staticmethod
    def _calc_return_ytd(hist: pd.DataFrame) -> Optional[float]:
        """Calculate year-to-date return from January 1 of the current year."""
        if hist.empty or len(hist) < 2:
            return None

        current_year = datetime.now().year
        ytd_data = hist.loc[hist.index >= f"{current_year}-01-01"]

        if ytd_data.empty:
            return None

        start_price = float(ytd_data["Close"].iloc[0])
        end_price = float(ytd_data["Close"].iloc[-1])

        if start_price == 0:
            return None

        return round((end_price - start_price) / start_price, 6)

    @staticmethod
    def _52w_high(
        hist: pd.DataFrame, info: Dict[str, Any]
    ) -> Optional[float]:
        """52-week high from info dict, falling back to computed from history."""
        val = info.get("fiftyTwoWeekHigh")
        if val is not None:
            return round(float(val), 2)
        if len(hist) >= 252:
            return round(float(hist["Close"].iloc[-252:].max()), 2)
        if not hist.empty:
            return round(float(hist["Close"].max()), 2)
        return None

    @staticmethod
    def _52w_low(
        hist: pd.DataFrame, info: Dict[str, Any]
    ) -> Optional[float]:
        """52-week low from info dict, falling back to computed from history."""
        val = info.get("fiftyTwoWeekLow")
        if val is not None:
            return round(float(val), 2)
        if len(hist) >= 252:
            return round(float(hist["Close"].iloc[-252:].min()), 2)
        if not hist.empty:
            return round(float(hist["Close"].min()), 2)
        return None

    @staticmethod
    def _avg_volume_30d(hist: pd.DataFrame) -> Optional[float]:
        """Average daily volume over the last 30 trading days."""
        if hist.empty:
            return None
        window = hist["Volume"].iloc[-30:]
        if window.empty:
            return None
        return round(float(window.mean()), 0)

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        """Return a valid but empty StockPerformance-shaped dict."""
        return {
            "current_price": None,
            "price_history": [],
            "returns_1m": None,
            "returns_3m": None,
            "returns_6m": None,
            "returns_1y": None,
            "returns_ytd": None,
            "beta": None,
            "high_52w": None,
            "low_52w": None,
            "avg_volume_30d": None,
        }

    @staticmethod
    def _empty_benchmark() -> Dict[str, Optional[float]]:
        """Return a valid but empty benchmark dict."""
        return {
            "ticker": None,
            "returns_1m": None,
            "returns_3m": None,
            "returns_6m": None,
            "returns_1y": None,
            "returns_ytd": None,
        }
