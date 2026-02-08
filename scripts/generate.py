#!/usr/bin/env python3
"""
Master Generation Script — Generate AnalysisJSON files for covered companies.

Usage:
  python scripts/generate.py --ticker APPF --filing 10-K --year 2025
  python scripts/generate.py --all
  python scripts/generate.py --ticker RBLX --filing 10-K --year 2024

Output:
  data/companies/{TICKER}/{TICKER}-{FILING}-FY{YEAR}.json
  data/companies/{TICKER}/manifest.json (updated)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.config import COVERED_TICKERS, DATA_DIR

# Import all fetchers
from scripts.fetchers.edgar_financials import EdgarFinancialsFetcher
from scripts.fetchers.edgar_mda import EdgarMDAFetcher
from scripts.fetchers.edgar_management import EdgarManagementFetcher
from scripts.fetchers.stock_prices import StockPriceFetcher
from scripts.fetchers.fmp_fundamentals import FMPFetcher
from scripts.fetchers.finnhub_data import FinnhubFetcher
from scripts.fetchers.macro_data import MacroDataFetcher
from scripts.fetchers.public_comps import PublicCompsFetcher
from scripts.fetchers.damodaran_data import DamodaranFetcher
from scripts.fetchers.news_funding import NewsFundingFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("generate")


def _fmt_currency(value: Optional[float]) -> str:
    """Format a dollar value for headline display."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.2f}"


def _fmt_multiple(value: Optional[float], suffix: str = "x") -> str:
    """Format a valuation multiple."""
    if value is None:
        return "N/A"
    return f"{value:.1f}{suffix}"


def _fmt_pct(value: Optional[float]) -> str:
    """Format a percentage."""
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _safe_get(d: Dict[str, Any], *keys: str) -> Optional[float]:
    """Safely traverse nested dicts."""
    current: Any = d
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current is None:
        return None
    try:
        return float(current)
    except (TypeError, ValueError):
        return None


def generate_analysis(ticker: str, filing_type: str, year: int) -> Dict[str, Any]:
    """Generate a full AnalysisJSON for a given ticker + filing.

    Orchestrates all data fetchers and assembles the final JSON.
    Each fetcher is called independently — failures in one don't block others.
    """
    logger.info("Generating %s FY%d analysis for %s...", filing_type, year, ticker)

    # Initialize fetchers
    edgar_fin = EdgarFinancialsFetcher()
    edgar_mda = EdgarMDAFetcher()
    edgar_mgmt = EdgarManagementFetcher()
    stock = StockPriceFetcher()
    fmp = FMPFetcher()
    finnhub = FinnhubFetcher()
    macro = MacroDataFetcher()
    comps = PublicCompsFetcher()
    damodaran = DamodaranFetcher()
    news_funding = NewsFundingFetcher()

    # ---- Fetch data from each source (isolated error handling) ----

    # 1. Company info + financial statements from EDGAR
    company_info: Dict[str, Any] = {}
    try:
        company_info = edgar_fin.fetch_company_info(ticker)
        logger.info("Fetched company info for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch company info for %s", ticker)

    financial_statements: Dict[str, Any] = {
        "income_statement": {"periods": [], "line_items": []},
        "balance_sheet": {"periods": [], "line_items": []},
        "cash_flow_statement": {"periods": [], "line_items": []},
    }
    try:
        financial_statements = edgar_fin.fetch_financials(ticker, filing_type)
        logger.info("Fetched financial statements for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch financials for %s", ticker)

    # 2. MD&A analysis
    mda_analysis: Optional[Dict[str, Any]] = None
    try:
        mda_result = edgar_mda.fetch_mda(ticker, filing_type)
        if mda_result and mda_result.get("sections"):
            mda_analysis = mda_result
            logger.info("Fetched MD&A for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch MD&A for %s", ticker)

    # 3. Management team + insider transactions
    management_team: Optional[Dict[str, Any]] = None
    try:
        mgmt_result = edgar_mgmt.fetch_management(ticker)
        if mgmt_result and (mgmt_result.get("executives") or mgmt_result.get("insider_transactions")):
            management_team = mgmt_result
            logger.info("Fetched management team for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch management for %s", ticker)

    # 4. Stock price history
    stock_performance: Optional[Dict[str, Any]] = None
    try:
        stock_result = stock.fetch_stock_data(ticker)
        if stock_result and stock_result.get("current_price"):
            stock_performance = stock_result
            logger.info("Fetched stock data for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch stock data for %s", ticker)

    # 5. FMP fundamentals (profile, metrics, ratios)
    fmp_profile: Dict[str, Any] = {}
    fmp_metrics: List[Dict[str, Any]] = []
    fmp_ratios: List[Dict[str, Any]] = []
    try:
        fmp_profile = fmp.fetch_profile(ticker)
        fmp_metrics = fmp.fetch_key_metrics(ticker, period="annual", limit=5)
        fmp_ratios = fmp.fetch_ratios(ticker, period="annual", limit=5)
        logger.info("Fetched FMP data for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch FMP data for %s", ticker)

    # 6. Finnhub data (peers, news, recommendations)
    finnhub_data: Dict[str, Any] = {}
    try:
        finnhub_data = finnhub.fetch_all(ticker)
        logger.info("Fetched Finnhub data for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch Finnhub data for %s", ticker)

    # 7. Macro data
    macro_data: Dict[str, Any] = {}
    try:
        macro_data = macro.fetch_macro_snapshot()
        logger.info("Fetched macro data")
    except Exception:
        logger.exception("Failed to fetch macro data")

    # 8. Public comps
    public_comps: Optional[Dict[str, Any]] = None
    try:
        comps_result = comps.fetch_comps(ticker)
        if comps_result and comps_result.get("comps"):
            public_comps = comps_result
            logger.info("Fetched public comps for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch public comps for %s", ticker)

    # 9. Damodaran industry data
    damodaran_data: Dict[str, Any] = {}
    try:
        damodaran_data = damodaran.fetch_for_ticker(ticker)
        logger.info("Fetched Damodaran data for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch Damodaran data for %s", ticker)

    # 10. News and competitor funding
    news_result: Dict[str, Any] = {}
    try:
        news_result = news_funding.fetch_all(ticker)
        logger.info("Fetched news/funding for %s", ticker)
    except Exception:
        logger.exception("Failed to fetch news/funding for %s", ticker)

    # ---- Assemble AnalysisJSON ----

    # Merge company info from EDGAR + FMP
    stock_price = _safe_get(stock_performance or {}, "current_price")
    market_cap = _safe_get(fmp_profile, "mktCap")
    ev = _safe_get(fmp_metrics[0] if fmp_metrics else {}, "enterpriseValueTTM")
    shares_out = _safe_get(fmp_profile, "sharesOutstanding")

    company = {
        "name": company_info.get("name") or fmp_profile.get("companyName", ticker),
        "ticker": ticker.upper(),
        "cik": company_info.get("cik"),
        "sector": fmp_profile.get("sector") or company_info.get("sic_description"),
        "industry": fmp_profile.get("industry"),
        "fiscal_year_end": company_info.get("fiscal_year_end"),
        "exchange": fmp_profile.get("exchangeShortName"),
        "market_cap": market_cap,
        "enterprise_value": ev,
        "stock_price": stock_price,
        "shares_outstanding": shares_out,
    }

    # Build headline metrics strip
    latest_metrics = fmp_metrics[0] if fmp_metrics else {}
    latest_ratios = fmp_ratios[0] if fmp_ratios else {}
    pe_ratio = _safe_get(latest_metrics, "peRatioTTM") or _safe_get(fmp_profile, "peRatio")
    ev_revenue = _safe_get(latest_metrics, "enterpriseValueOverRevenueTTM")
    ev_ebitda = _safe_get(latest_metrics, "enterpriseValueOverEBITDATTM")

    headline_metrics = [
        {"label": "Stock Price", "value": stock_price, "formatted": f"${stock_price:,.2f}" if stock_price else "N/A"},
        {"label": "Market Cap", "value": market_cap, "formatted": _fmt_currency(market_cap)},
        {"label": "EV", "value": ev, "formatted": _fmt_currency(ev)},
        {"label": "P/E", "value": pe_ratio, "formatted": _fmt_multiple(pe_ratio)},
        {"label": "EV/Revenue", "value": ev_revenue, "formatted": _fmt_multiple(ev_revenue)},
        {"label": "EV/EBITDA", "value": ev_ebitda, "formatted": _fmt_multiple(ev_ebitda)},
    ]

    # Build KPIs from FMP metrics + ratios
    kpis = _build_kpis(latest_metrics, latest_ratios, fmp_profile, stock_performance)

    # Build derived metrics
    derived_metrics = _build_derived_metrics(fmp_metrics, fmp_ratios)

    # Build narrative summary
    narrative = _build_narrative(ticker, company, fmp_profile, mda_analysis)

    # Build sources list
    sources = _build_sources(ticker, filing_type, year)

    # Data quality assessment
    sections_populated = sum(1 for x in [
        financial_statements.get("income_statement", {}).get("line_items"),
        mda_analysis,
        management_team,
        stock_performance,
        public_comps,
    ] if x)
    completeness = sections_populated / 5.0

    data_quality = {
        "overall_confidence": "high" if completeness > 0.7 else "medium" if completeness > 0.3 else "low",
        "completeness": round(completeness, 2),
        "warnings": [],
        "missing_data": [],
    }
    if not financial_statements.get("income_statement", {}).get("line_items"):
        data_quality["missing_data"].append("financial_statements")
    if not mda_analysis:
        data_quality["missing_data"].append("mda_analysis")
    if not stock_performance:
        data_quality["missing_data"].append("stock_performance")
    if not fmp_profile:
        data_quality["warnings"].append("FMP profile unavailable — market data may be incomplete")

    # Build competitors section from Finnhub peers + curated data
    competitors = _build_competitors(finnhub_data)

    # Build investment frameworks from Damodaran + FMP data
    investment_frameworks = _build_frameworks(latest_metrics, latest_ratios, damodaran_data)

    # Build funding tracker
    funding_tracker = None
    funding_rounds = news_result.get("funding_rounds", [])
    if funding_rounds:
        funding_tracker = {"rounds": funding_rounds}

    # Build IR materials stub
    ir_materials = {
        "documents": [],
        "ir_website": fmp_profile.get("website"),
        "next_earnings_date": None,
        "dividend_info": None,
    }

    # ---- Assemble final JSON ----
    analysis: Dict[str, Any] = {
        "metadata": {
            "analysis_id": f"{ticker}-{filing_type}-FY{year}",
            "timestamp": date.today().isoformat(),
            "model": "pipeline-v2",
            "prompt_version": "2.0",
            "schema_version": "2.0.0",
            "analysis_type": "full",
            "filing_type": filing_type,
            "period": f"FY{year}",
        },
        "company": company,
        "financial_statements": financial_statements,
        "derived_metrics": derived_metrics,
        "kpis": kpis,
        "headline_metrics": headline_metrics,
        "narrative": narrative,
        "sources": sources,
        "data_quality": data_quality,
        "mda_analysis": mda_analysis,
        "management_team": management_team,
        "business_model": None,  # Populated by Claude analysis in future
        "product_developments": None,
        "competitors": competitors,
        "public_comps": public_comps,
        "stock_performance": stock_performance,
        "funding_tracker": funding_tracker,
        "investment_frameworks": investment_frameworks,
        "ir_materials": ir_materials,
    }

    return analysis


def _build_kpis(
    metrics: Dict[str, Any],
    ratios: Dict[str, Any],
    profile: Dict[str, Any],
    stock_data: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build KPI cards from FMP metrics and ratios."""
    kpis: List[Dict[str, Any]] = []

    # Revenue
    revenue = _safe_get(metrics, "revenuePerShareTTM")
    shares = _safe_get(profile, "sharesOutstanding")
    total_revenue = None
    if revenue and shares:
        total_revenue = revenue * shares
    kpis.append({
        "label": "Revenue (TTM)",
        "value": total_revenue,
        "formatted": _fmt_currency(total_revenue),
        "change": _safe_get(metrics, "revenueGrowth"),
        "change_formatted": _fmt_pct(_safe_get(metrics, "revenueGrowth")),
        "trend": "up" if (_safe_get(metrics, "revenueGrowth") or 0) > 0 else "down",
        "period": "TTM",
        "category": "growth",
    })

    # Gross Margin
    gm = _safe_get(ratios, "grossProfitMarginTTM") or _safe_get(profile, "grossMargin")
    kpis.append({
        "label": "Gross Margin",
        "value": gm,
        "formatted": _fmt_pct(gm),
        "change": None, "change_formatted": "", "trend": "stable",
        "period": "TTM", "category": "profitability",
    })

    # Operating Margin
    om = _safe_get(ratios, "operatingProfitMarginTTM") or _safe_get(profile, "operatingMargin")
    kpis.append({
        "label": "Operating Margin",
        "value": om,
        "formatted": _fmt_pct(om),
        "change": None, "change_formatted": "", "trend": "stable",
        "period": "TTM", "category": "profitability",
    })

    # Net Margin
    nm = _safe_get(ratios, "netProfitMarginTTM")
    kpis.append({
        "label": "Net Margin",
        "value": nm,
        "formatted": _fmt_pct(nm),
        "change": None, "change_formatted": "", "trend": "stable",
        "period": "TTM", "category": "profitability",
    })

    # FCF Margin
    fcf_margin = _safe_get(metrics, "freeCashFlowMarginTTM")
    kpis.append({
        "label": "FCF Margin",
        "value": fcf_margin,
        "formatted": _fmt_pct(fcf_margin),
        "change": None, "change_formatted": "", "trend": "stable",
        "period": "TTM", "category": "profitability",
    })

    # ROIC
    roic = _safe_get(ratios, "returnOnCapitalEmployedTTM")
    kpis.append({
        "label": "ROIC",
        "value": roic,
        "formatted": _fmt_pct(roic),
        "change": None, "change_formatted": "", "trend": "stable",
        "period": "TTM", "category": "profitability",
    })

    # Rule of 40
    rev_growth = _safe_get(metrics, "revenueGrowth")
    if rev_growth is not None and fcf_margin is not None:
        rule40 = (rev_growth * 100) + (fcf_margin * 100)
        kpis.append({
            "label": "Rule of 40",
            "value": round(rule40, 1),
            "formatted": f"{rule40:.0f}",
            "change": None, "change_formatted": "",
            "trend": "up" if rule40 >= 40 else "down",
            "period": "TTM", "category": "saas",
        })

    # Debt/Equity
    de = _safe_get(ratios, "debtEquityRatioTTM")
    kpis.append({
        "label": "Debt/Equity",
        "value": de,
        "formatted": _fmt_multiple(de, "x") if de is not None else "N/A",
        "change": None, "change_formatted": "", "trend": "stable",
        "period": "TTM", "category": "leverage",
    })

    # Current Ratio
    cr = _safe_get(ratios, "currentRatioTTM")
    kpis.append({
        "label": "Current Ratio",
        "value": cr,
        "formatted": _fmt_multiple(cr, "x") if cr is not None else "N/A",
        "change": None, "change_formatted": "", "trend": "stable",
        "period": "TTM", "category": "liquidity",
    })

    return kpis


def _build_derived_metrics(
    metrics_list: List[Dict[str, Any]],
    ratios_list: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build derived metrics categories from FMP data."""
    latest_m = metrics_list[0] if metrics_list else {}
    latest_r = ratios_list[0] if ratios_list else {}

    def _metric_val(value: Optional[float], period: str = "TTM") -> Dict[str, Any]:
        return {"value": value, "period": period, "trend": "stable"}

    return {
        "profitability": {
            "gross_margin": _metric_val(_safe_get(latest_r, "grossProfitMarginTTM")),
            "operating_margin": _metric_val(_safe_get(latest_r, "operatingProfitMarginTTM")),
            "net_margin": _metric_val(_safe_get(latest_r, "netProfitMarginTTM")),
            "roe": _metric_val(_safe_get(latest_r, "returnOnEquityTTM")),
            "roa": _metric_val(_safe_get(latest_r, "returnOnAssetsTTM")),
            "roic": _metric_val(_safe_get(latest_r, "returnOnCapitalEmployedTTM")),
        },
        "liquidity": {
            "current_ratio": _metric_val(_safe_get(latest_r, "currentRatioTTM")),
            "quick_ratio": _metric_val(_safe_get(latest_r, "quickRatioTTM")),
            "cash_ratio": _metric_val(_safe_get(latest_r, "cashRatioTTM")),
        },
        "leverage": {
            "debt_equity": _metric_val(_safe_get(latest_r, "debtEquityRatioTTM")),
            "debt_assets": _metric_val(_safe_get(latest_r, "debtRatioTTM")),
            "interest_coverage": _metric_val(_safe_get(latest_r, "interestCoverageTTM")),
        },
        "efficiency": {
            "asset_turnover": _metric_val(_safe_get(latest_r, "assetTurnoverTTM")),
            "inventory_turnover": _metric_val(_safe_get(latest_r, "inventoryTurnoverTTM")),
            "receivables_turnover": _metric_val(_safe_get(latest_r, "receivablesTurnoverTTM")),
        },
        "saas": {
            "revenue_per_share": _metric_val(_safe_get(latest_m, "revenuePerShareTTM")),
            "fcf_per_share": _metric_val(_safe_get(latest_m, "freeCashFlowPerShareTTM")),
            "fcf_margin": _metric_val(_safe_get(latest_m, "freeCashFlowMarginTTM")),
        },
    }


def _build_narrative(
    ticker: str,
    company: Dict[str, Any],
    profile: Dict[str, Any],
    mda: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build narrative section from available data."""
    name = company.get("name", ticker)
    sector = company.get("sector", "")
    industry = company.get("industry", "")
    description = profile.get("description", "")

    summary = f"{name} operates in the {industry or sector or 'technology'} sector."
    if description:
        # Use first 2 sentences of FMP description
        sentences = description.split(". ")[:2]
        summary = ". ".join(sentences) + "."

    sections = []
    if description:
        sections.append({
            "title": "Company Overview",
            "content": description[:2000],
            "sentiment": "neutral",
            "source_refs": [0],
        })

    if mda and mda.get("sections"):
        for s in mda["sections"][:5]:
            sections.append({
                "title": s.get("topic", "MD&A"),
                "content": s.get("content", "")[:2000],
                "sentiment": s.get("sentiment", "neutral"),
                "source_refs": [1],
            })

    risks = []
    if mda and mda.get("key_themes"):
        risks = [f"Key theme: {t}" for t in mda["key_themes"]]

    outlook = ""
    if mda and mda.get("management_tone"):
        outlook = f"Management tone: {mda['management_tone']}"

    return {
        "summary": summary,
        "sections": sections,
        "risks": risks,
        "outlook": outlook,
    }


def _build_sources(ticker: str, filing_type: str, year: int) -> List[Dict[str, Any]]:
    """Build the sources attribution list."""
    return [
        {
            "id": 0,
            "type": "sec_filing",
            "label": f"{ticker} {filing_type} FY{year}",
            "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type={filing_type}",
            "date": f"{year}-12-31",
            "reliability": "high",
        },
        {
            "id": 1,
            "type": "sec_filing",
            "label": f"{ticker} MD&A Analysis",
            "url": None,
            "date": f"{year}-12-31",
            "reliability": "high",
        },
        {
            "id": 2,
            "type": "computed",
            "label": "Financial Modeling Prep API",
            "url": "https://financialmodelingprep.com",
            "date": date.today().isoformat(),
            "reliability": "medium",
        },
        {
            "id": 3,
            "type": "computed",
            "label": "Yahoo Finance (via yfinance)",
            "url": None,
            "date": date.today().isoformat(),
            "reliability": "medium",
        },
        {
            "id": 4,
            "type": "computed",
            "label": "Finnhub Financial Data",
            "url": "https://finnhub.io",
            "date": date.today().isoformat(),
            "reliability": "medium",
        },
    ]


def _build_competitors(finnhub_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build competitors section from Finnhub peer data."""
    peers = finnhub_data.get("peers", [])
    if not peers:
        return None

    direct = []
    for peer in peers[:8]:
        direct.append({
            "name": peer,
            "ticker": peer,
            "is_public": True,
            "description": "",
            "threat_level": "medium",
        })

    return {
        "direct": direct,
        "indirect": [],
        "competitive_advantages": [],
        "competitive_risks": [],
    }


def _build_frameworks(
    metrics: Dict[str, Any],
    ratios: Dict[str, Any],
    damodaran: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build investment frameworks from available data."""
    frameworks = []

    # Peter Lynch PEG ratio
    pe = _safe_get(metrics, "peRatioTTM")
    growth = _safe_get(metrics, "revenueGrowth")
    if pe and growth and growth > 0:
        peg = pe / (growth * 100)
        classification = "fast_grower" if growth > 0.20 else "stalwart" if growth > 0.05 else "slow_grower"
        frameworks.append({
            "name": "peter_lynch_peg",
            "label": "Peter Lynch PEG Ratio",
            "result": {"peg_ratio": round(peg, 2), "classification": classification},
            "fair_value": None,
            "upside_pct": None,
            "notes": f"PEG of {peg:.2f} {'suggests undervalued' if peg < 1 else 'suggests fairly valued' if peg < 2 else 'suggests overvalued'} for growth rate",
        })

    # Greenblatt Magic Formula (simplified)
    roic = _safe_get(ratios, "returnOnCapitalEmployedTTM")
    earnings_yield = _safe_get(metrics, "earningsYieldTTM")
    if roic and earnings_yield:
        frameworks.append({
            "name": "magic_formula",
            "label": "Greenblatt Magic Formula",
            "result": {"roic": round(roic, 4), "earnings_yield": round(earnings_yield, 4)},
            "fair_value": None,
            "upside_pct": None,
            "notes": f"ROIC: {roic*100:.1f}%, Earnings Yield: {earnings_yield*100:.1f}%",
        })

    # Damodaran WACC comparison
    wacc_data = damodaran.get("cost_of_capital", {})
    if wacc_data and wacc_data.get("wacc"):
        wacc = wacc_data["wacc"]
        frameworks.append({
            "name": "wacc_analysis",
            "label": "Damodaran WACC Analysis",
            "result": {
                "wacc": wacc,
                "cost_of_equity": wacc_data.get("cost_of_equity"),
                "cost_of_debt": wacc_data.get("cost_of_debt"),
            },
            "fair_value": None,
            "upside_pct": None,
            "notes": f"Industry WACC: {wacc*100:.1f}%" if isinstance(wacc, float) else f"Industry WACC: {wacc}",
        })

    if not frameworks:
        return None

    return {"frameworks": frameworks}


def update_manifest(ticker: str, filing_type: str, year: int, filename: str) -> None:
    """Update the company's manifest.json with the new filing."""
    manifest_path = DATA_DIR / ticker.upper() / "manifest.json"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {
            "ticker": ticker.upper(),
            "name": "",
            "sector": "",
            "industry": "",
            "filings": [],
            "default_filing": None,
        }

    period = f"FY{year}"
    filing_entry = {
        "type": filing_type,
        "period": period,
        "file": filename,
        "generated": date.today().isoformat(),
    }

    # Replace existing entry for same type+period or append
    existing_idx = next(
        (i for i, f in enumerate(manifest["filings"])
         if f["type"] == filing_type and f["period"] == period),
        None,
    )
    if existing_idx is not None:
        manifest["filings"][existing_idx] = filing_entry
    else:
        manifest["filings"].append(filing_entry)

    # Set as default if no default yet or if this is the latest
    if not manifest["default_filing"]:
        manifest["default_filing"] = filename
    else:
        # Update default to the latest filing
        manifest["default_filing"] = filename

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info("Updated manifest: %s", manifest_path)


def run(ticker: str, filing_type: str, year: int) -> None:
    """Generate analysis and write to disk."""
    t = ticker.upper()
    out_dir = DATA_DIR / t
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{t}-{filing_type.replace('-', '')}-FY{year}.json"
    out_path = out_dir / filename

    analysis = generate_analysis(t, filing_type, year)

    out_path.write_text(json.dumps(analysis, indent=2, default=str) + "\n")
    logger.info("Wrote %s", out_path)

    update_manifest(t, filing_type, year, filename)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AnalysisJSON files")
    parser.add_argument("--ticker", type=str, help="Company ticker (e.g. APPF)")
    parser.add_argument("--filing", type=str, default="10-K", help="Filing type (10-K or 10-Q)")
    parser.add_argument("--year", type=int, default=2025, help="Fiscal year")
    parser.add_argument("--all", action="store_true", help="Generate for all covered tickers")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.all:
        for t in COVERED_TICKERS:
            try:
                run(t, args.filing, args.year)
            except Exception:
                logger.exception("Failed to generate for %s", t)
    elif args.ticker:
        run(args.ticker, args.filing, args.year)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
