"""EDGAR Service — Wrapper around edgartools for SEC filings data"""
from __future__ import annotations

import math
from typing import Any

from edgar import Company, set_identity


# SEC requires a User-Agent header
set_identity("IGSB-Analyst/2.0 admin@example.com")


def get_company_info(ticker: str) -> dict[str, Any]:
    """Fetch basic company information from EDGAR."""
    company = Company(ticker)
    return {
        "name": company.name,
        "ticker": ticker.upper(),
        "cik": str(company.cik),
        "sic": getattr(company, "sic", None),
        "sic_description": getattr(company, "sic_description", None),
        "fiscal_year_end": getattr(company, "fiscal_year_end", None),
        "state": getattr(company, "state_of_incorporation", None),
    }


def get_filings_list(ticker: str, form_type: str = "10-K", count: int = 5) -> list[dict[str, Any]]:
    """Get recent filings of a specific type."""
    company = Company(ticker)
    filings = company.get_filings(form=form_type).latest(count)
    results = []
    for filing in filings:
        results.append({
            "accession_number": filing.accession_no,
            "form": filing.form,
            "filed_date": str(filing.filing_date),
            "period": str(getattr(filing, "period_of_report", filing.filing_date)),
            "url": filing.filing_url if hasattr(filing, "filing_url") else None,
        })
    return results


def _safe_val(v: Any) -> float | None:
    """Convert a value to float, returning None for NaN/None."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _statement_to_line_items(df: Any, periods: list[str]) -> list[dict[str, Any]]:
    """Convert a pandas DataFrame (rows=labels, cols=periods) to line items."""
    line_items = []
    for label in df.index:
        values = {}
        for period in periods:
            if period in df.columns:
                values[period] = _safe_val(df.loc[label, period])
        line_items.append({
            "label": str(label),
            "concept": "",
            "values": values,
            "unit": "USD",
            "source": "10-K",
        })
    return line_items


def get_financial_statements(ticker: str) -> dict[str, Any]:
    """Build structured financial statements from EDGAR facts.

    Uses edgartools EntityFacts API which provides income_statement(),
    balance_sheet(), and cash_flow() as structured DataFrames.
    """
    company = Company(ticker)
    facts = company.get_facts()

    result = {
        "income_statement": {"periods": [], "line_items": []},
        "balance_sheet": {"periods": [], "line_items": []},
        "cash_flow_statement": {"periods": [], "line_items": []},
    }

    # Map of statement key -> facts method name
    statement_map = {
        "income_statement": "income_statement",
        "balance_sheet": "balance_sheet",
        "cash_flow_statement": "cash_flow",
    }

    for key, method_name in statement_map.items():
        try:
            method = getattr(facts, method_name, None)
            if method is None:
                continue
            stmt = method()
            if stmt is None or stmt.empty:
                continue

            df = stmt.data
            periods = [str(c) for c in df.columns]
            line_items = _statement_to_line_items(df, periods)

            result[key] = {
                "periods": periods,
                "line_items": line_items,
            }
        except Exception as e:
            print(f"Warning: Failed to extract {key}: {e}")
            continue

    return result
