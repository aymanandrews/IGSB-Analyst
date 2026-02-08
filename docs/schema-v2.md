# AnalysisJSON v2 Schema Specification

## Overview

AnalysisJSON v2 extends the original schema with sections for comprehensive equity research: MD&A analysis, management profiles, business model breakdown, competitor intelligence, public comps, stock performance, funding tracker, investment frameworks, and IR materials.

All v1 fields are preserved and backward-compatible. New v2 sections are optional (`null` when not populated).

## Top-Level Structure

```json
{
  "metadata": { ... },
  "company": { ... },
  "financial_statements": { ... },
  "derived_metrics": { ... },
  "kpis": [ ... ],
  "headline_metrics": [ ... ],
  "narrative": { ... },
  "sources": [ ... ],
  "data_quality": { ... },
  "mda_analysis": { ... },
  "management_team": { ... },
  "business_model": { ... },
  "product_developments": { ... },
  "competitors": { ... },
  "public_comps": { ... },
  "stock_performance": { ... },
  "funding_tracker": { ... },
  "investment_frameworks": { ... },
  "ir_materials": { ... }
}
```

## New in v2

### headline_metrics

Top-line metrics rendered as a horizontal strip above KPI cards:

```json
[
  { "label": "Stock Price", "value": 245.80, "formatted": "$245.80" },
  { "label": "Market Cap", "value": 14200000000, "formatted": "$14.2B" },
  { "label": "EV/Revenue", "value": 22.5, "formatted": "22.5x" }
]
```

### company (extended)

Added fields: `exchange`, `market_cap`, `enterprise_value`, `stock_price`, `shares_outstanding`.

### mda_analysis

Extracted from SEC filing Item 7 (10-K) or Item 2 (10-Q):

```json
{
  "filing_period": "FY2025",
  "sections": [
    {
      "topic": "Revenue Drivers",
      "content": "Management highlighted...",
      "sentiment": "positive",
      "key_figures": ["Revenue grew 28% YoY"]
    }
  ],
  "key_themes": ["AI adoption", "market expansion"],
  "management_tone": "optimistic"
}
```

### management_team

```json
{
  "executives": [
    {
      "name": "Jason Randall",
      "title": "President & CEO",
      "since": "2017",
      "compensation": 5200000,
      "bio": "Former COO..."
    }
  ],
  "insider_transactions": [
    {
      "name": "Jason Randall",
      "title": "CEO",
      "date": "2024-11-15",
      "type": "sell",
      "shares": 5000,
      "price": 245.50,
      "value": 1227500
    }
  ],
  "board_size": 9,
  "insider_ownership_pct": 0.032
}
```

### business_model

```json
{
  "description": "Cloud-based property management platform...",
  "revenue_model": "subscription",
  "segments": [
    { "name": "Core Solutions", "revenue": 520000000, "pct_of_total": 0.72, "growth_rate": 0.25 },
    { "name": "Value+ Services", "revenue": 200000000, "pct_of_total": 0.28, "growth_rate": 0.35 }
  ],
  "key_customers": ["Property managers", "HOA management"],
  "geographic_mix": { "US": 0.95, "International": 0.05 },
  "moat_sources": ["switching_costs", "network_effects"]
}
```

### product_developments

```json
{
  "recent_launches": [
    { "title": "AI Leasing Assistant", "date": "2024-Q3", "description": "...", "impact": "positive" }
  ],
  "roadmap_items": [],
  "key_partnerships": ["Google Cloud", "Plaid"]
}
```

### competitors

```json
{
  "direct": [
    { "name": "RealPage", "ticker": null, "is_public": false, "description": "...", "threat_level": "high" }
  ],
  "indirect": [
    { "name": "Yardi Systems", "ticker": null, "is_public": false, "description": "...", "threat_level": "medium" }
  ],
  "competitive_advantages": ["Ease of use", "AI features"],
  "competitive_risks": ["Enterprise incumbents", "Price competition"]
}
```

### public_comps

Comparable public companies with key metrics:

```json
{
  "comps": [
    {
      "ticker": "PCOR",
      "name": "Procore Technologies",
      "market_cap": 12000000000,
      "ev": 11500000000,
      "revenue": 950000000,
      "revenue_growth": 0.22,
      "gross_margin": 0.78,
      "operating_margin": -0.05,
      "ev_revenue": 12.1,
      "ev_ebitda": null,
      "pe_ratio": null,
      "fcf_margin": 0.08,
      "rule_of_40": 30
    }
  ],
  "median_ev_revenue": 10.5,
  "median_ev_ebitda": 45.0,
  "median_revenue_growth": 0.20
}
```

### stock_performance

```json
{
  "current_price": 245.80,
  "price_history": [
    { "date": "2025-02-07", "close": 245.80, "volume": 523000 }
  ],
  "returns_1m": 0.05,
  "returns_3m": 0.12,
  "returns_1y": 0.45,
  "returns_ytd": 0.08,
  "beta": 1.15,
  "high_52w": 280.50,
  "low_52w": 160.25,
  "avg_volume_30d": 450000
}
```

### funding_tracker

Private competitor funding rounds:

```json
{
  "rounds": [
    {
      "company": "Buildium",
      "stage": "late",
      "date": "2024-06-15",
      "amount": 50000000,
      "lead_investor": "Insight Partners",
      "valuation": 500000000,
      "key_news": "Expanding into commercial real estate",
      "threat_level": "medium"
    }
  ]
}
```

### investment_frameworks

Results from applying investor frameworks:

```json
{
  "frameworks": [
    {
      "name": "peter_lynch_peg",
      "label": "Peter Lynch PEG Ratio",
      "result": { "peg_ratio": 1.8, "classification": "fast_grower" },
      "fair_value": null,
      "upside_pct": null,
      "notes": "PEG of 1.8 suggests fairly valued for growth rate"
    },
    {
      "name": "dcf",
      "label": "Discounted Cash Flow",
      "result": { "wacc": 0.10, "terminal_growth": 0.03, "ev": 15000000000 },
      "fair_value": 275.00,
      "upside_pct": 0.12,
      "notes": "Base case with 10% WACC and 3% terminal growth"
    }
  ]
}
```

### ir_materials

```json
{
  "documents": [
    {
      "title": "Q4 2024 Earnings Presentation",
      "type": "presentation",
      "date": "2025-02-03",
      "url": "https://investors.appfolio.com/...",
      "summary": "Record revenue, AI product expansion"
    }
  ],
  "ir_website": "https://investors.appfolio.com",
  "next_earnings_date": "2025-05-05",
  "dividend_info": "No dividend — reinvesting in growth"
}
```

## Validation Rules (v2 additions)

1. All v1 validation rules still apply
2. New sections are Optional — `null` when data not yet populated
3. `headline_metrics` values should match corresponding `company` or `kpis` fields
4. `public_comps.comps` should include 5-10 comparable companies
5. `investment_frameworks.frameworks[].name` should be unique within the array
6. `funding_tracker.rounds` ordered by date descending (most recent first)
7. `stock_performance.price_history` ordered by date ascending
8. Unit field in line items expanded: `"USD"` | `"percent"` | `"shares"` | `"USD/shares"` | `"ratio"`
