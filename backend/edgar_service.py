"""EDGAR Service — Wrapper around edgartools for SEC filings data"""
from __future__ import annotations

import os
from typing import Any

from edgar import Company, set_identity


# SEC requires a User-Agent header
set_identity("IGSB-Analyst admin@example.com")


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


def get_company_facts(ticker: str) -> dict[str, Any]:
    """Fetch XBRL-structured company facts from EDGAR CompanyFacts API."""
    company = Company(ticker)
    facts = company.get_facts()

    # Extract key financial concepts
    financial_data = {
        "ticker": ticker.upper(),
        "concepts": {},
    }

    # Key US-GAAP concepts to extract
    key_concepts = [
        "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
        "CostOfRevenue", "CostOfGoodsAndServicesSold",
        "GrossProfit",
        "OperatingIncomeLoss", "OperatingExpenses",
        "NetIncomeLoss",
        "EarningsPerShareBasic", "EarningsPerShareDiluted",
        "Assets", "AssetsCurrent",
        "Liabilities", "LiabilitiesCurrent",
        "StockholdersEquity",
        "CashAndCashEquivalentsAtCarryingValue",
        "LongTermDebt", "LongTermDebtNoncurrent",
        "OperatingCashFlow", "NetCashProvidedByOperatingActivities",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "CommonStockSharesOutstanding",
    ]

    for concept_name in key_concepts:
        try:
            concept = facts.get("us-gaap", concept_name)
            if concept is not None:
                # Get the data as records
                df = concept.to_dataframe() if hasattr(concept, "to_dataframe") else None
                if df is not None and len(df) > 0:
                    # Get most recent entries
                    records = df.tail(12).to_dict("records")
                    financial_data["concepts"][concept_name] = {
                        "label": concept_name,
                        "unit": records[0].get("unit", "USD") if records else "USD",
                        "data": [
                            {
                                "period": str(r.get("end", r.get("period", ""))),
                                "value": r.get("val", r.get("value", None)),
                                "form": r.get("form", ""),
                                "filed": str(r.get("filed", "")),
                                "fiscal_year": r.get("fy", None),
                                "fiscal_period": r.get("fp", None),
                            }
                            for r in records
                        ],
                    }
        except Exception:
            continue

    return financial_data


def get_financial_statements(ticker: str) -> dict[str, Any]:
    """Build structured financial statements from EDGAR facts.

    Returns data shaped for the AnalysisJSON schema:
    income_statement, balance_sheet, cash_flow_statement
    """
    facts_data = get_company_facts(ticker)
    concepts = facts_data.get("concepts", {})

    def extract_latest(concept_name: str, n: int = 4) -> dict[str, float | None]:
        """Extract latest N period values for a concept."""
        concept = concepts.get(concept_name, {})
        data_points = concept.get("data", [])

        # Filter to annual (10-K) filings and deduplicate by period
        annual = [d for d in data_points if d.get("form") == "10-K"]
        seen = {}
        for d in annual:
            period = d.get("period", "")
            if period and period not in seen:
                seen[period] = d.get("value")

        # Sort by period descending, take latest N
        sorted_periods = sorted(seen.keys(), reverse=True)[:n]
        return {p: seen[p] for p in sorted_periods}

    # Build statement line items
    revenue_concepts = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"]
    revenue_data = {}
    for rc in revenue_concepts:
        revenue_data = extract_latest(rc)
        if revenue_data:
            break

    periods = sorted(revenue_data.keys(), reverse=True) if revenue_data else []

    income_statement = {
        "periods": periods,
        "line_items": [
            {"label": "Revenue", "concept": "us-gaap:Revenues", "values": revenue_data, "unit": "USD", "source": "10-K"},
            {"label": "Cost of Revenue", "concept": "us-gaap:CostOfRevenue", "values": extract_latest("CostOfRevenue"), "unit": "USD", "source": "10-K"},
            {"label": "Gross Profit", "concept": "us-gaap:GrossProfit", "values": extract_latest("GrossProfit"), "unit": "USD", "source": "10-K"},
            {"label": "Operating Expenses", "concept": "us-gaap:OperatingExpenses", "values": extract_latest("OperatingExpenses"), "unit": "USD", "source": "10-K"},
            {"label": "Operating Income", "concept": "us-gaap:OperatingIncomeLoss", "values": extract_latest("OperatingIncomeLoss"), "unit": "USD", "source": "10-K"},
            {"label": "Net Income", "concept": "us-gaap:NetIncomeLoss", "values": extract_latest("NetIncomeLoss"), "unit": "USD", "source": "10-K"},
            {"label": "EPS (Basic)", "concept": "us-gaap:EarningsPerShareBasic", "values": extract_latest("EarningsPerShareBasic"), "unit": "USD/shares", "source": "10-K"},
            {"label": "EPS (Diluted)", "concept": "us-gaap:EarningsPerShareDiluted", "values": extract_latest("EarningsPerShareDiluted"), "unit": "USD/shares", "source": "10-K"},
        ],
    }

    balance_sheet = {
        "periods": periods,
        "line_items": [
            {"label": "Total Assets", "concept": "us-gaap:Assets", "values": extract_latest("Assets"), "unit": "USD", "source": "10-K"},
            {"label": "Current Assets", "concept": "us-gaap:AssetsCurrent", "values": extract_latest("AssetsCurrent"), "unit": "USD", "source": "10-K"},
            {"label": "Cash & Equivalents", "concept": "us-gaap:CashAndCashEquivalentsAtCarryingValue", "values": extract_latest("CashAndCashEquivalentsAtCarryingValue"), "unit": "USD", "source": "10-K"},
            {"label": "Total Liabilities", "concept": "us-gaap:Liabilities", "values": extract_latest("Liabilities"), "unit": "USD", "source": "10-K"},
            {"label": "Current Liabilities", "concept": "us-gaap:LiabilitiesCurrent", "values": extract_latest("LiabilitiesCurrent"), "unit": "USD", "source": "10-K"},
            {"label": "Long-term Debt", "concept": "us-gaap:LongTermDebt", "values": extract_latest("LongTermDebt") or extract_latest("LongTermDebtNoncurrent"), "unit": "USD", "source": "10-K"},
            {"label": "Stockholders' Equity", "concept": "us-gaap:StockholdersEquity", "values": extract_latest("StockholdersEquity"), "unit": "USD", "source": "10-K"},
        ],
    }

    cash_flow = {
        "periods": periods,
        "line_items": [
            {"label": "Operating Cash Flow", "concept": "us-gaap:NetCashProvidedByOperatingActivities", "values": extract_latest("NetCashProvidedByOperatingActivities") or extract_latest("OperatingCashFlow"), "unit": "USD", "source": "10-K"},
            {"label": "Capital Expenditures", "concept": "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", "values": extract_latest("PaymentsToAcquirePropertyPlantAndEquipment"), "unit": "USD", "source": "10-K"},
        ],
    }

    return {
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cash_flow_statement": cash_flow,
    }
