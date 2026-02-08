# Folio: Technical Architecture

## System Overview

Folio is an equity research platform that combines SEC/EDGAR filings, user-uploaded documents, and Claude AI to produce structured investment analysis reports.

## Component Architecture

### Frontend (Static SPA)
- **Delivery:** Single `index.html` served statically (no build step)
- **Styling:** Tailwind CSS via CDN, Inter + JetBrains Mono fonts via Google Fonts
- **JavaScript:** Vanilla ES6+ modules loaded via `<script type="module">`
- **File Parsing:** Client-side using pdf.js (PDFs) and SheetJS (Excel/CSV)
- **State:** In-memory application state, persisted to localStorage for sessions
- **Rendering:** DOM manipulation, template literals for HTML generation

### Backend (FastAPI)
- **Framework:** FastAPI (Python 3.11+)
- **EDGAR Integration:** `edgartools` library for XBRL-structured SEC filings
- **AI Integration:** Anthropic Python SDK with streaming (SSE)
- **Validation:** Pydantic v2 models for all request/response schemas
- **CORS:** Enabled for `localhost` origins during development

### Data Pipeline

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  User Input  │────▶│  Data Layer   │────▶│  Analysis Layer  │
│              │     │              │     │                 │
│ • File Upload│     │ • PDF Parser │     │ • Prompt Engine │
│ • Ticker     │     │ • XLSX Parser│     │ • Claude API    │
│ • Parameters │     │ • EDGAR API  │     │ • JSON Validator│
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                                          ┌────────▼────────┐
                                          │  Render Layer    │
                                          │                 │
                                          │ • Statement Tbl │
                                          │ • KPI Cards     │
                                          │ • Metrics       │
                                          │ • Narrative     │
                                          │ • Source Attrib │
                                          └─────────────────┘
```

### EDGAR Integration

Uses `edgartools` Python library (MIT license) which wraps the SEC's CompanyFacts API:

- **CompanyFacts API:** Returns XBRL-structured financial data
- **Data available:** Balance sheets, income statements, cash flow statements
- **Lookup:** By CIK number or ticker symbol
- **Rate limiting:** Respects SEC's 10 requests/second limit
- **User-Agent:** Required by SEC — set to project identifier

Key `edgartools` usage:
```python
from edgar import Company

company = Company("AAPL")  # or by CIK
filings = company.get_filings(form="10-K")
facts = company.get_facts()
```

### Claude AI Integration

- **Model:** claude-sonnet-4-5-20250929 (default, configurable)
- **Streaming:** SSE via Anthropic SDK for progressive rendering
- **Prompts:** Structured system + user prompts with financial context
- **Output:** AnalysisJSON — validated structured output (see schema.md)
- **Token management:** Estimated costs displayed to user before analysis

### File Parsing Strategy

All parsing happens client-side to avoid sending raw files to the server:

| Format | Library | Extraction |
|--------|---------|-----------|
| PDF | pdf.js (Mozilla) | Text content, tables via heuristics |
| Excel/CSV | SheetJS | Cell data, sheet names, formulas |
| Plain text | Native | Direct text content |

Parsed data is sent as structured JSON to the backend for analysis.

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/edgar/company/{ticker}` | Company info + available filings |
| GET | `/api/edgar/financials/{ticker}` | Structured financial statements |
| POST | `/api/analysis/run` | Start Claude analysis (SSE stream) |
| GET | `/api/health` | Health check |

## Security Considerations

- No authentication (single-user local tool)
- API keys stored in environment variables (never in code)
- CORS restricted to localhost
- File parsing is client-side (no file uploads to server)
- Claude API key provided by user or from environment

## Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
# Just open index.html or use any static server
python -m http.server 3000
```
