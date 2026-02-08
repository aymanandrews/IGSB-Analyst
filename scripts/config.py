"""Pipeline Configuration — API keys, rate limits, paths."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---- Paths ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "companies"
CACHE_DIR = PROJECT_ROOT / ".cache"

# ---- API Keys (loaded from .env) ----
FMP_API_KEY = os.getenv("FMP_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ---- SEC EDGAR ----
EDGAR_USER_AGENT = "IGSB-Analyst/2.0 admin@example.com"

# ---- Rate Limits (requests per second) ----
RATE_LIMITS = {
    "edgar": 10,       # SEC allows 10 req/s
    "fmp": 5,          # FMP free tier
    "finnhub": 30,     # Finnhub free tier
    "fred": 10,        # FRED
    "yfinance": 2,     # yfinance (unofficial, be conservative)
}

# ---- Companies covered ----
COVERED_TICKERS = ["APPF", "RBLX", "WDAY", "PCOR", "TTAN", "VEEV"]

# ---- Filing Types ----
FILING_TYPES = ["10-K", "10-Q"]
