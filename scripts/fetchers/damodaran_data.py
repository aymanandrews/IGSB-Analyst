"""Damodaran Data Fetcher — Industry-level valuation metrics from Aswath Damodaran's datasets.

Downloads and parses the publicly available Excel files hosted at NYU Stern.
Provides industry betas, cost of capital, multiples, ERP, and ROIC data
for benchmarking individual companies against their sector.

Requires: pandas, xlrd (for reading .xls format files)

Usage:
    fetcher = DamodaranFetcher()
    betas = fetcher.fetch_industry_betas("Software (System & Application)")
    wacc = fetcher.fetch_cost_of_capital("Software (System & Application)")
    multiples = fetcher.fetch_industry_multiples("Software (System & Application)")
    erp = fetcher.fetch_erp()
    everything = fetcher.fetch_all_for_industry("Software (System & Application)")
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from scripts.base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

# Cache TTL — Damodaran updates datasets roughly quarterly
_CACHE_HOURS = 168  # 7 days

# Damodaran dataset URLs (NYU Stern, .xls format — requires xlrd engine)
DATASETS: Dict[str, str] = {
    "betas": "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls",
    "wacc": "https://pages.stern.nyu.edu/~adamodar/pc/datasets/wacc.xls",
    "psdata": "https://pages.stern.nyu.edu/~adamodar/pc/datasets/psdata.xls",
    "pedata": "https://pages.stern.nyu.edu/~adamodar/pc/datasets/pedata.xls",
    "eva": "https://pages.stern.nyu.edu/~adamodar/pc/datasets/EVA.xls",
    "erp": "https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xls",
}

# Maps covered tickers to their Damodaran industry classification
TICKER_INDUSTRY_MAP: Dict[str, str] = {
    "APPF": "Software (System & Application)",
    "RBLX": "Entertainment",
    "WDAY": "Software (System & Application)",
    "PCOR": "Software (System & Application)",
    "TTAN": "Software (System & Application)",
    "VEEV": "Software (System & Application)",
}


class DamodaranFetcher(BaseFetcher):
    """Fetches industry-level valuation benchmarks from Damodaran's NYU datasets."""

    source_name: str = "damodaran"

    def __init__(self) -> None:
        super().__init__()
        self._excel_cache_dir = self.cache_dir / "excel"
        self._excel_cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def fetch_industry_betas(self, industry: Optional[str] = None) -> List[Dict[str, Any]]:
        """Download betas.xls and parse industry beta data.

        Args:
            industry: If specified, filter results to matching industry row(s).
                Uses fuzzy matching (case-insensitive substring).

        Returns:
            List of dicts with keys: industry, num_firms, avg_unlevered_beta,
            avg_levered_beta. Returns empty list on failure.
        """
        cache_key = self._cache_key("industry_betas", str(industry))
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for industry betas (industry=%s)", industry)
            return cached  # type: ignore[return-value]

        df = self._download_and_parse("betas")
        if df is None:
            return []

        industry_col = self._find_industry_column(df)
        if industry_col is None:
            logger.error("Cannot find industry column in betas dataset")
            return []

        results: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            industry_name = _clean_str(row.get(industry_col))
            if not industry_name or industry_name.lower() in ("industry name", "total market"):
                continue

            entry = {
                "industry": industry_name,
                "num_firms": _safe_int(row, "Number of firms"),
                "avg_unlevered_beta": _safe_float(row, "Unlevered beta"),
                "avg_levered_beta": _safe_float(row, "Levered Beta"),
            }
            results.append(entry)

        if industry is not None:
            results = self._filter_by_industry(results, industry)

        self._set_cached(cache_key, results)  # type: ignore[arg-type]
        return results

    def fetch_cost_of_capital(self, industry: Optional[str] = None) -> List[Dict[str, Any]]:
        """Download wacc.xls and parse cost of capital data.

        Args:
            industry: If specified, filter results to matching industry row(s).

        Returns:
            List of dicts with keys: industry, wacc, cost_of_equity,
            cost_of_debt, debt_ratio. Returns empty list on failure.
        """
        cache_key = self._cache_key("cost_of_capital", str(industry))
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for cost of capital (industry=%s)", industry)
            return cached  # type: ignore[return-value]

        df = self._download_and_parse("wacc")
        if df is None:
            return []

        industry_col = self._find_industry_column(df)
        if industry_col is None:
            logger.error("Cannot find industry column in wacc dataset")
            return []

        results: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            industry_name = _clean_str(row.get(industry_col))
            if not industry_name or industry_name.lower() in ("industry name", "total market"):
                continue

            entry = {
                "industry": industry_name,
                "wacc": _safe_float(row, "Cost of Capital"),
                "cost_of_equity": _safe_float(row, "Cost of Equity"),
                "cost_of_debt": _safe_float(row, "Pre-tax Cost of Debt"),
                "debt_ratio": _safe_float(row, "Debt/Capital"),
            }
            results.append(entry)

        if industry is not None:
            results = self._filter_by_industry(results, industry)

        self._set_cached(cache_key, results)  # type: ignore[arg-type]
        return results

    def fetch_industry_multiples(self, industry: Optional[str] = None) -> List[Dict[str, Any]]:
        """Download psdata.xls and pedata.xls, then merge revenue and PE multiples.

        Args:
            industry: If specified, filter results to matching industry row(s).

        Returns:
            List of dicts with keys: industry, ev_sales, pe_ratio, peg_ratio.
            Returns empty list on failure.
        """
        cache_key = self._cache_key("industry_multiples", str(industry))
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for industry multiples (industry=%s)", industry)
            return cached  # type: ignore[return-value]

        # Parse revenue multiples (psdata.xls)
        ps_df = self._download_and_parse("psdata")
        ps_lookup: Dict[str, Dict[str, Optional[float]]] = {}
        if ps_df is not None:
            ps_industry_col = self._find_industry_column(ps_df)
            if ps_industry_col is not None:
                for _, row in ps_df.iterrows():
                    name = _clean_str(row.get(ps_industry_col))
                    if not name or name.lower() in ("industry name", "total market"):
                        continue
                    ps_lookup[name.lower()] = {
                        "ev_sales": _safe_float(row, "EV/Sales"),
                        "industry_name_raw": name,
                    }

        # Parse PE data (pedata.xls)
        pe_df = self._download_and_parse("pedata")
        pe_lookup: Dict[str, Dict[str, Optional[float]]] = {}
        if pe_df is not None:
            pe_industry_col = self._find_industry_column(pe_df)
            if pe_industry_col is not None:
                for _, row in pe_df.iterrows():
                    name = _clean_str(row.get(pe_industry_col))
                    if not name or name.lower() in ("industry name", "total market"):
                        continue
                    pe_lookup[name.lower()] = {
                        "pe_ratio": _safe_float(row, "Current PE"),
                        "peg_ratio": _safe_float(row, "PEG Ratio"),
                        "industry_name_raw": name,
                    }

        # Merge on industry name (case-insensitive)
        all_industries = set(ps_lookup.keys()) | set(pe_lookup.keys())
        results: List[Dict[str, Any]] = []

        for ind_lower in sorted(all_industries):
            ps_data = ps_lookup.get(ind_lower, {})
            pe_data = pe_lookup.get(ind_lower, {})

            # Use whichever source has the raw name
            raw_name = ps_data.get("industry_name_raw") or pe_data.get("industry_name_raw") or ind_lower

            entry = {
                "industry": raw_name,
                "ev_sales": ps_data.get("ev_sales"),
                "pe_ratio": pe_data.get("pe_ratio"),
                "peg_ratio": pe_data.get("peg_ratio"),
            }
            results.append(entry)

        if industry is not None:
            results = self._filter_by_industry(results, industry)

        self._set_cached(cache_key, results)  # type: ignore[arg-type]
        return results

    def fetch_erp(self) -> Dict[str, Any]:
        """Fetch the US equity risk premium from ctryprem.xls.

        Returns:
            Dict with keys: implied_erp, date, treasury_rate.
            Returns empty dict on failure.
        """
        cache_key = self._cache_key("erp_us")
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for US equity risk premium")
            return cached

        df = self._download_and_parse("erp")
        if df is None:
            return {}

        # The ERP dataset uses country rows; find the US row
        us_row = self._find_country_row(df, "United States")
        if us_row is None:
            logger.warning("Could not find United States row in ERP dataset")
            return {}

        result: Dict[str, Any] = {
            "implied_erp": _safe_float(us_row, "Equity Risk Premium"),
            "date": _safe_str(us_row, "Date"),
            "treasury_rate": _safe_float(us_row, "Risk Free Rate"),
        }

        # If date column not found, try to infer from the file modification time
        if result["date"] is None:
            erp_path = self._excel_cache_dir / "ctryprem.xls"
            if erp_path.exists():
                mtime = erp_path.stat().st_mtime
                result["date"] = time.strftime("%Y-%m-%d", time.localtime(mtime))

        self._set_cached(cache_key, result)
        return result

    def fetch_all_for_industry(self, industry: str) -> Dict[str, Any]:
        """Convenience method: fetch betas, WACC, multiples, and ERP for one industry.

        Args:
            industry: Damodaran industry classification string,
                e.g. "Software (System & Application)".

        Returns:
            Combined dict with keys: industry, betas, cost_of_capital,
            multiples, erp. Sub-keys match the individual fetch method outputs.
        """
        cache_key = self._cache_key("all_for_industry", industry)
        cached = self._get_cached(cache_key, max_age_hours=_CACHE_HOURS)
        if cached is not None:
            logger.info("Cache hit for all Damodaran data (industry=%s)", industry)
            return cached

        result: Dict[str, Any] = {"industry": industry}

        # Betas
        betas = self.fetch_industry_betas(industry)
        result["betas"] = betas[0] if betas else {}

        # Cost of capital
        wacc = self.fetch_cost_of_capital(industry)
        result["cost_of_capital"] = wacc[0] if wacc else {}

        # Multiples
        multiples = self.fetch_industry_multiples(industry)
        result["multiples"] = multiples[0] if multiples else {}

        # ERP (not industry-specific, but useful context)
        result["erp"] = self.fetch_erp()

        self._set_cached(cache_key, result)
        return result

    def fetch_for_ticker(self, ticker: str) -> Dict[str, Any]:
        """Fetch all Damodaran data for a covered ticker via TICKER_INDUSTRY_MAP.

        Args:
            ticker: Stock ticker symbol (e.g. "APPF").

        Returns:
            Combined industry data dict, or empty dict if ticker is not mapped.
        """
        ticker = ticker.upper().strip()
        industry = TICKER_INDUSTRY_MAP.get(ticker)
        if industry is None:
            logger.warning(
                "Ticker %s not in TICKER_INDUSTRY_MAP — cannot determine Damodaran industry",
                ticker,
            )
            return {}
        return self.fetch_all_for_industry(industry)

    # ------------------------------------------------------------------ #
    #  Internal — Excel download, parsing, and matching                   #
    # ------------------------------------------------------------------ #

    def _download_and_parse(self, dataset_key: str) -> Optional[pd.DataFrame]:
        """Download a Damodaran .xls file by dataset key, cache locally, and parse.

        Cached files are reused if they are less than 7 days old. Downloads
        use the BaseFetcher session with retry logic.

        Args:
            dataset_key: Key into the DATASETS dict (e.g. "betas", "wacc").

        Returns:
            DataFrame with the first sheet's data, or None on failure.
        """
        url = DATASETS.get(dataset_key)
        if url is None:
            logger.error("Unknown dataset key: %s", dataset_key)
            return None

        filename = url.rsplit("/", 1)[-1]
        local_path = self._excel_cache_dir / filename

        # Check if cached file is still fresh
        if local_path.exists():
            age_hours = (time.time() - local_path.stat().st_mtime) / 3600
            if age_hours < _CACHE_HOURS:
                logger.debug("Using cached Excel file: %s (%.1fh old)", filename, age_hours)
                return self._read_excel(local_path)

        # Download the file
        logger.info("Downloading Damodaran dataset: %s", filename)
        try:
            resp = self.fetch_with_retry(url)
            local_path.write_bytes(resp.content)
            logger.info("Saved %s (%d bytes)", filename, len(resp.content))
        except Exception:
            logger.exception("Failed to download %s", url)
            # Fall back to stale cache if available
            if local_path.exists():
                logger.warning("Using stale cached file: %s", filename)
                return self._read_excel(local_path)
            return None

        return self._read_excel(local_path)

    @staticmethod
    def _read_excel(path: Path) -> Optional[pd.DataFrame]:
        """Read a .xls file into a DataFrame using xlrd engine.

        Damodaran's files are in the old Excel 97-2003 format (.xls),
        which requires the xlrd library. Attempts xlrd first, then falls
        back to openpyxl for .xlsx files.

        Args:
            path: Local path to the downloaded Excel file.

        Returns:
            DataFrame, or None if parsing fails.
        """
        try:
            df = pd.read_excel(path, engine="xlrd")
            return df
        except Exception as e:
            logger.debug("xlrd failed for %s: %s — trying openpyxl", path.name, e)
            try:
                df = pd.read_excel(path, engine="openpyxl")
                return df
            except Exception:
                logger.exception("Failed to parse Excel file: %s", path)
                return None

    @staticmethod
    def _find_industry_column(df: pd.DataFrame) -> Optional[str]:
        """Locate the column containing industry names.

        Damodaran's spreadsheets use varying column headers like
        "Industry Name", "Industry name", or just "Industry".

        Args:
            df: DataFrame from a Damodaran Excel file.

        Returns:
            Column name string, or None if not found.
        """
        for col in df.columns:
            col_lower = str(col).strip().lower()
            if col_lower in ("industry name", "industry"):
                return str(col)

        # Fallback: first column is often the industry name
        if len(df.columns) > 0:
            first_col = str(df.columns[0]).strip().lower()
            if "industr" in first_col or "name" in first_col:
                return str(df.columns[0])

        return None

    @staticmethod
    def _filter_by_industry(
        rows: List[Dict[str, Any]], industry: str
    ) -> List[Dict[str, Any]]:
        """Filter a list of industry dicts by fuzzy industry name matching.

        Matching strategy (in order):
            1. Exact match on the "industry" key
            2. Case-insensitive exact match
            3. Case-insensitive substring containment

        Args:
            rows: List of dicts each containing an "industry" key.
            industry: Target industry name.

        Returns:
            Filtered list (may be empty if no match found).
        """
        industry_stripped = industry.strip()
        industry_lower = industry_stripped.lower()

        # 1. Exact match
        exact = [r for r in rows if r.get("industry", "").strip() == industry_stripped]
        if exact:
            return exact

        # 2. Case-insensitive exact match
        ci_exact = [r for r in rows if r.get("industry", "").strip().lower() == industry_lower]
        if ci_exact:
            return ci_exact

        # 3. Case-insensitive substring match
        ci_contains = [
            r for r in rows
            if industry_lower in r.get("industry", "").strip().lower()
        ]
        if ci_contains:
            return ci_contains

        logger.warning("Industry '%s' not found in results", industry)
        return []

    @staticmethod
    def _find_country_row(
        df: pd.DataFrame, country: str
    ) -> Optional[pd.Series]:
        """Find a row matching a country name in the ERP dataset.

        The ERP dataset uses "Country" as its key column rather than
        "Industry Name".

        Args:
            df: DataFrame from the ERP (country risk premium) Excel file.
            country: Target country name (e.g. "United States").

        Returns:
            The matching row as a pd.Series, or None if not found.
        """
        # Try common column names for country
        country_col = None
        for col in df.columns:
            col_lower = str(col).strip().lower()
            if col_lower in ("country", "country name"):
                country_col = str(col)
                break

        if country_col is None:
            # Fallback to first column
            if len(df.columns) > 0:
                country_col = str(df.columns[0])
            else:
                return None

        col_vals = df[country_col].astype(str).str.strip()
        country_lower = country.lower()

        # Exact match
        exact = df[col_vals == country]
        if len(exact) > 0:
            return exact.iloc[0]

        # Case-insensitive
        ci_exact = df[col_vals.str.lower() == country_lower]
        if len(ci_exact) > 0:
            return ci_exact.iloc[0]

        # Substring
        ci_contains = df[col_vals.str.lower().str.contains(country_lower, na=False)]
        if len(ci_contains) > 0:
            return ci_contains.iloc[0]

        return None


# ------------------------------------------------------------------ #
#  Module-level helpers                                               #
# ------------------------------------------------------------------ #

def _clean_str(val: Any) -> Optional[str]:
    """Clean a value into a stripped string, or None if empty/NaN."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s else None


def _safe_float(
    row: pd.Series,
    column_name: str,
) -> Optional[float]:
    """Safely extract a float value from a DataFrame row by column name.

    Handles missing columns, NaN values, percentage strings, and
    non-numeric entries gracefully.

    Args:
        row: A pandas Series representing a single row.
        column_name: The target column name (checked case-insensitively).

    Returns:
        A rounded float, or None if the value cannot be extracted.
    """
    # Find the column case-insensitively
    target = column_name.lower()
    matched_col = None
    for col in row.index:
        if str(col).strip().lower() == target:
            matched_col = col
            break

    # Try partial match if exact fails
    if matched_col is None:
        for col in row.index:
            if target in str(col).strip().lower():
                matched_col = col
                break

    if matched_col is None:
        return None

    val = row[matched_col]

    if pd.isna(val):
        return None

    # Handle string values (e.g. "12.5%" or "N/A")
    if isinstance(val, str):
        val = val.strip().rstrip("%")
        if not val or val.upper() in ("N/A", "NA", "-", "NM", "#DIV/0!", "#N/A"):
            return None
        try:
            return round(float(val), 6)
        except ValueError:
            return None

    try:
        return round(float(val), 6)
    except (TypeError, ValueError):
        return None


def _safe_int(
    row: pd.Series,
    column_name: str,
) -> Optional[int]:
    """Safely extract an integer value from a DataFrame row by column name.

    Args:
        row: A pandas Series representing a single row.
        column_name: The target column name (checked case-insensitively).

    Returns:
        An integer, or None if the value cannot be extracted.
    """
    val = _safe_float(row, column_name)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_str(
    row: pd.Series,
    column_name: str,
) -> Optional[str]:
    """Safely extract a string value from a DataFrame row by column name.

    Args:
        row: A pandas Series representing a single row.
        column_name: The target column name (checked case-insensitively).

    Returns:
        A stripped string, or None if the value cannot be extracted.
    """
    target = column_name.lower()
    matched_col = None
    for col in row.index:
        if str(col).strip().lower() == target:
            matched_col = col
            break

    if matched_col is None:
        for col in row.index:
            if target in str(col).strip().lower():
                matched_col = col
                break

    if matched_col is None:
        return None

    val = row[matched_col]
    if pd.isna(val):
        return None

    s = str(val).strip()
    return s if s else None
