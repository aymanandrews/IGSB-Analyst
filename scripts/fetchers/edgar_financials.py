"""EDGAR Financials Fetcher — Extract financial statements from SEC EDGAR filings.

Uses the edgartools library to fetch structured financial data (XBRL CompanyFacts API)
and converts it to the AnalysisJSON line_items format.

Usage:
    fetcher = EdgarFinancialsFetcher()
    statements = fetcher.fetch_financials("APPF", filing_type="10-K")
    company_info = fetcher.fetch_company_info("APPF")
    filings = fetcher.fetch_filings_list("APPF", form_type="10-K", count=5)
"""
from __future__ import annotations

import logging
import math
from typing import Any, Optional

from edgar import Company, set_identity

from scripts.base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

# SEC requires a User-Agent header with contact info
set_identity("Folio/2.0 admin@example.com")

# Map internal statement keys to edgartools EntityFacts method names
_STATEMENT_MAP: dict[str, str] = {
    "income_statement": "income_statement",
    "balance_sheet": "balance_sheet",
    "cash_flow_statement": "cash_flow",
}


def _safe_val(v: Any) -> Optional[float]:
    """Convert a value to float, returning None for NaN/None/non-numeric."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


class EdgarFinancialsFetcher(BaseFetcher):
    """Fetcher for SEC EDGAR financial statements via edgartools."""

    source_name: str = "edgar"

    def fetch_company_info(self, ticker: str) -> dict[str, Any]:
        """Fetch basic company information from EDGAR.

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").

        Returns:
            Dict with company metadata: name, ticker, CIK, SIC, etc.
        """
        cache_key = self._cache_key("company_info", ticker.upper())
        cached = self._get_cached(cache_key, max_age_hours=168)  # 7 days
        if cached is not None:
            return cached

        self.rate_limiter.wait()
        company = Company(ticker)

        data: dict[str, Any] = {
            "name": company.name,
            "ticker": ticker.upper(),
            "cik": str(company.cik),
            "sic": getattr(company, "sic", None),
            "sic_description": getattr(company, "sic_description", None),
            "fiscal_year_end": getattr(company, "fiscal_year_end", None),
            "state": getattr(company, "state_of_incorporation", None),
        }

        self._set_cached(cache_key, data)
        return data

    def fetch_filings_list(
        self,
        ticker: str,
        form_type: str = "10-K",
        count: int = 5,
    ) -> list[dict[str, Any]]:
        """Fetch a list of recent SEC filings for a company.

        Args:
            ticker: Company stock ticker symbol.
            form_type: SEC form type to filter by (e.g. "10-K", "10-Q").
            count: Maximum number of filings to return.

        Returns:
            List of dicts with filing metadata (accession number, date, URL, etc.).
        """
        cache_key = self._cache_key("filings_list", ticker.upper(), form_type, str(count))
        cached = self._get_cached(cache_key, max_age_hours=24)
        if cached is not None:
            return cached  # type: ignore[return-value]

        self.rate_limiter.wait()
        company = Company(ticker)
        filings = company.get_filings(form=form_type).latest(count)

        results: list[dict[str, Any]] = []
        for filing in filings:
            results.append({
                "accession_number": filing.accession_no,
                "form": filing.form,
                "filed_date": str(filing.filing_date),
                "period": str(getattr(filing, "period_of_report", filing.filing_date)),
                "url": filing.filing_url if hasattr(filing, "filing_url") else None,
            })

        self._set_cached(cache_key, results)  # type: ignore[arg-type]
        return results

    def fetch_financials(
        self,
        ticker: str,
        filing_type: str = "10-K",
    ) -> dict[str, Any]:
        """Fetch full financial statements from EDGAR and convert to AnalysisJSON format.

        Uses edgartools EntityFacts API which provides income_statement(),
        balance_sheet(), and cash_flow() as structured DataFrames.

        Args:
            ticker: Company stock ticker symbol (e.g. "APPF").
            filing_type: SEC filing type used as the source label (default "10-K").

        Returns:
            Dict matching the FinancialStatements schema with keys:
            - income_statement: {periods: [...], line_items: [...]}
            - balance_sheet:    {periods: [...], line_items: [...]}
            - cash_flow_statement: {periods: [...], line_items: [...]}
        """
        cache_key = self._cache_key("financials", ticker.upper(), filing_type)
        cached = self._get_cached(cache_key, max_age_hours=24)
        if cached is not None:
            logger.info("Using cached financials for %s", ticker.upper())
            return cached

        self.rate_limiter.wait()
        company = Company(ticker)
        facts = company.get_facts()

        result: dict[str, Any] = {
            "income_statement": {"periods": [], "line_items": []},
            "balance_sheet": {"periods": [], "line_items": []},
            "cash_flow_statement": {"periods": [], "line_items": []},
        }

        for key, method_name in _STATEMENT_MAP.items():
            try:
                method = getattr(facts, method_name, None)
                if method is None:
                    logger.warning("EntityFacts has no method '%s' for %s", method_name, ticker)
                    continue

                stmt = method()
                if stmt is None or stmt.empty:
                    logger.warning("Empty %s for %s", key, ticker)
                    continue

                df = stmt.data
                periods = [str(c) for c in df.columns]
                line_items = self._dataframe_to_line_items(df, periods, filing_type)

                result[key] = {
                    "periods": periods,
                    "line_items": line_items,
                }
                logger.info(
                    "Extracted %s for %s: %d periods, %d line items",
                    key, ticker.upper(), len(periods), len(line_items),
                )

            except Exception:
                logger.exception("Failed to extract %s for %s", key, ticker.upper())
                continue

        self._set_cached(cache_key, result)
        return result

    @staticmethod
    def _dataframe_to_line_items(
        df: Any,
        periods: list[str],
        filing_type: str,
    ) -> list[dict[str, Any]]:
        """Convert a pandas DataFrame to AnalysisJSON line_items format.

        The DataFrame has row labels (index) as concept names and column headers
        as period labels (e.g. "FY2025", "FY2024").

        Args:
            df: pandas DataFrame with rows=labels, cols=periods.
            periods: List of period strings matching df columns.
            filing_type: SEC form type to tag as the data source.

        Returns:
            List of line_item dicts with label, concept, values, unit, source.
        """
        line_items: list[dict[str, Any]] = []
        for label in df.index:
            values: dict[str, Optional[float]] = {}
            for period in periods:
                if period in df.columns:
                    values[period] = _safe_val(df.loc[label, period])

            line_items.append({
                "label": str(label),
                "concept": "",
                "values": values,
                "unit": "USD",
                "source": filing_type,
            })
        return line_items
