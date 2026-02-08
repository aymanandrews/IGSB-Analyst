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
import sys
from datetime import date
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.config import COVERED_TICKERS, DATA_DIR


def generate_analysis(ticker: str, filing_type: str, year: int) -> dict:
    """
    Generate a full AnalysisJSON for a given ticker + filing.

    This is the orchestrator that calls individual fetchers and assembles
    the final JSON. Currently a stub — individual fetchers (PRs #16-#25)
    will be wired in as they are built.
    """
    print(f"[generate] Generating {filing_type} FY{year} analysis for {ticker}...")

    # TODO: Wire fetchers as they are built (PRs #16-#25)
    # from scripts.fetchers.edgar_financials import EdgarFinancialsFetcher
    # from scripts.fetchers.stock_prices import StockPriceFetcher
    # from scripts.fetchers.fmp_fundamentals import FMPFetcher
    # etc.

    analysis = {
        "meta": {
            "schema_version": "2.0.0",
            "generated_at": date.today().isoformat(),
            "filing_type": filing_type,
            "period": f"FY{year}",
            "ticker": ticker.upper(),
        },
        "company": {
            "name": f"{ticker.upper()} (pending data pipeline)",
            "ticker": ticker.upper(),
        },
        "financial_statements": {
            "income_statement": {"periods": [], "line_items": []},
            "balance_sheet": {"periods": [], "line_items": []},
            "cash_flow_statement": {"periods": [], "line_items": []},
        },
        "kpis": [],
        "headline_metrics": [],
        "derived_metrics": {},
        "narrative": {"summary": "Analysis pending — data pipeline not yet connected."},
        "sources": [],
        "data_quality": {"overall_score": 0, "completeness": 0},
    }

    return analysis


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

    # Set as default if no default yet
    if not manifest["default_filing"]:
        manifest["default_filing"] = filename

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[generate] Updated manifest: {manifest_path}")


def run(ticker: str, filing_type: str, year: int) -> None:
    """Generate analysis and write to disk."""
    t = ticker.upper()
    out_dir = DATA_DIR / t
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{t}-{filing_type.replace('-', '')}-FY{year}.json"
    out_path = out_dir / filename

    analysis = generate_analysis(t, filing_type, year)

    out_path.write_text(json.dumps(analysis, indent=2) + "\n")
    print(f"[generate] Wrote {out_path}")

    update_manifest(t, filing_type, year, filename)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AnalysisJSON files")
    parser.add_argument("--ticker", type=str, help="Company ticker (e.g. APPF)")
    parser.add_argument("--filing", type=str, default="10-K", help="Filing type (10-K or 10-Q)")
    parser.add_argument("--year", type=int, default=2025, help="Fiscal year")
    parser.add_argument("--all", action="store_true", help="Generate for all covered tickers")

    args = parser.parse_args()

    if args.all:
        for t in COVERED_TICKERS:
            run(t, args.filing, args.year)
    elif args.ticker:
        run(args.ticker, args.filing, args.year)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
