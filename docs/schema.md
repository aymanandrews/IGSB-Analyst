# AnalysisJSON Schema Specification

## Overview

AnalysisJSON is the structured output format returned by Claude when analyzing financial data. It provides a consistent, validated schema for rendering financial analysis in the frontend.

## Top-Level Structure

```json
{
  "metadata": { ... },
  "company": { ... },
  "financial_statements": { ... },
  "derived_metrics": { ... },
  "kpis": [ ... ],
  "narrative": { ... },
  "sources": [ ... ],
  "data_quality": { ... }
}
```

## Schema Definitions

### metadata
```json
{
  "analysis_id": "uuid",
  "timestamp": "ISO 8601",
  "model": "claude-sonnet-4-5-20250929",
  "prompt_version": "1.0",
  "analysis_type": "full | quick | comparative"
}
```

### company
```json
{
  "name": "Apple Inc.",
  "ticker": "AAPL",
  "cik": "0000320193",
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "fiscal_year_end": "September"
}
```

### financial_statements

Contains three statement types, each with the same structure:

```json
{
  "income_statement": {
    "periods": ["2024-Q4", "2024-Q3", "2023-Q4"],
    "line_items": [
      {
        "label": "Revenue",
        "concept": "us-gaap:Revenues",
        "values": {
          "2024-Q4": 94930000000,
          "2024-Q3": 85777000000,
          "2023-Q4": 89498000000
        },
        "unit": "USD",
        "source": "10-K"
      }
    ]
  },
  "balance_sheet": { ... },
  "cash_flow_statement": { ... }
}
```

### derived_metrics

Calculated ratios and metrics:

```json
{
  "profitability": {
    "gross_margin": { "value": 0.463, "period": "2024-Q4", "trend": "up" },
    "operating_margin": { "value": 0.335, "period": "2024-Q4", "trend": "stable" },
    "net_margin": { "value": 0.267, "period": "2024-Q4", "trend": "up" },
    "roe": { "value": 1.609, "period": "2024-Q4", "trend": "up" }
  },
  "liquidity": {
    "current_ratio": { "value": 0.988, "period": "2024-Q4", "trend": "down" },
    "quick_ratio": { "value": 0.846, "period": "2024-Q4", "trend": "down" }
  },
  "leverage": {
    "debt_to_equity": { "value": 1.872, "period": "2024-Q4", "trend": "stable" },
    "interest_coverage": { "value": 29.16, "period": "2024-Q4", "trend": "up" }
  },
  "efficiency": {
    "asset_turnover": { "value": 1.29, "period": "2024-Q4", "trend": "stable" },
    "inventory_turnover": { "value": 33.37, "period": "2024-Q4", "trend": "up" }
  }
}
```

### kpis

Top-level key performance indicators for dashboard cards:

```json
[
  {
    "label": "Revenue",
    "value": 94930000000,
    "formatted": "$94.9B",
    "change": 0.061,
    "change_formatted": "+6.1%",
    "trend": "up",
    "period": "2024-Q4",
    "category": "growth"
  }
]
```

Trend values: `"up"` | `"down"` | `"stable"`
Categories: `"growth"` | `"profitability"` | `"liquidity"` | `"leverage"`

### narrative

AI-generated analysis text with section structure:

```json
{
  "summary": "One-paragraph executive summary...",
  "sections": [
    {
      "title": "Revenue Analysis",
      "content": "Detailed analysis paragraph...",
      "sentiment": "positive",
      "source_refs": [0, 1]
    }
  ],
  "risks": ["Risk factor 1", "Risk factor 2"],
  "outlook": "Forward-looking summary..."
}
```

Sentiment values: `"positive"` | `"negative"` | `"neutral"` | `"mixed"`

### sources

Attribution for all data used in the analysis:

```json
[
  {
    "id": 0,
    "type": "sec_filing",
    "label": "AAPL 10-K FY2024",
    "url": "https://www.sec.gov/...",
    "date": "2024-11-01",
    "reliability": "high"
  },
  {
    "id": 1,
    "type": "uploaded_document",
    "label": "Q4 Earnings Call Transcript.pdf",
    "filename": "earnings_call_q4.pdf",
    "date": null,
    "reliability": "medium"
  }
]
```

Source types: `"sec_filing"` | `"uploaded_document"` | `"analyst_input"` | `"computed"`
Reliability: `"high"` | `"medium"` | `"low"`

### data_quality

Assessment of the data completeness and confidence:

```json
{
  "overall_confidence": "high",
  "completeness": 0.92,
  "warnings": [
    "Cash flow statement Q3 2024 data estimated from quarterly report"
  ],
  "missing_data": [
    "Segment revenue breakdown not available for Q3 2023"
  ]
}
```

Confidence levels: `"high"` | `"medium"` | `"low"`

## Validation Rules

1. All monetary values in raw numbers (not formatted)
2. All percentages as decimals (0.463, not 46.3%)
3. All dates in ISO 8601 format
4. Period labels follow pattern: `YYYY-QN` or `YYYY-FY`
5. Source references (source_refs) are indices into the sources array
6. Every line_item must have at least one source
7. Trends computed from minimum 2 periods of data
