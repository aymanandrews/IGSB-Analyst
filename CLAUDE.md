# IGSB-Analyst

## Project Overview
Financial analysis platform for IGSB (Investment Grade Short-term Bond). Combines EDGAR/SEC filings data, uploaded documents (PDF/Excel/text), and Claude AI analysis to produce structured financial reports with source attribution.

## Architecture
- **Frontend:** Static HTML + Tailwind CSS (CDN) + vanilla JavaScript
- **Backend:** Python FastAPI server
- **EDGAR Data:** `edgartools` library (XBRL-structured CompanyFacts API)
- **AI Analysis:** Anthropic Python SDK with SSE streaming
- **File Parsing:** Client-side (pdf.js for PDFs, SheetJS for Excel)
- **No database** — localStorage for session persistence, JSON for data exchange

## Directory Structure
```
project-alpha/
├── CLAUDE.md
├── index.html              # Main SPA entry point
├── css/
│   └── styles.css          # Custom styles (Tailwind via CDN)
├── js/
│   ├── app.js              # Main application controller
│   ├── upload.js           # File upload + parsing
│   ├── edgar.js            # EDGAR data fetching (via backend proxy)
│   ├── analysis.js         # Claude analysis orchestration
│   ├── renderer.js         # Financial statement rendering
│   └── export.js           # PDF/JSON export
├── backend/
│   ├── main.py             # FastAPI app entry point
│   ├── edgar_service.py    # edgartools wrapper
│   ├── analysis_service.py # Claude API + prompt engine
│   ├── routers/
│   │   ├── edgar.py        # /api/edgar/* routes
│   │   └── analysis.py     # /api/analysis/* routes
│   └── schemas/
│       ├── analysis.py     # AnalysisJSON Pydantic models
│       └── edgar.py        # EDGAR response models
├── docs/
│   ├── architecture.md
│   ├── schema.md           # AnalysisJSON specification
│   └── pull-requests.md    # PR roadmap
└── requirements.txt
```

## Conventions

### Code Style
- **Python:** PEP 8, type hints on all function signatures, f-strings preferred
- **JavaScript:** No framework, vanilla ES6+, `const`/`let` only, no `var`
- **HTML:** Semantic elements, Tailwind utility classes, minimal custom CSS
- **Naming:** snake_case (Python), camelCase (JS), kebab-case (CSS classes)

### Design System
- **Primary font:** Inter (Google Fonts CDN)
- **Mono font:** JetBrains Mono (Google Fonts CDN)
- **Color palette:** Tailwind defaults with these semantic tokens:
  - `bg-slate-50` — page background
  - `bg-white` — card/panel background
  - `border-slate-200` — borders
  - `text-slate-900` — primary text
  - `text-slate-500` — secondary text
  - `bg-blue-600` / `text-blue-600` — primary actions/links
  - `bg-emerald-50` / `text-emerald-700` — positive metrics
  - `bg-red-50` / `text-red-700` — negative metrics/alerts
  - `bg-amber-50` / `text-amber-700` — warnings/caution
- **Spacing:** Tailwind scale (4px base: p-2=8px, p-4=16px, p-6=24px)
- **Border radius:** `rounded-lg` for cards, `rounded-md` for inputs/buttons
- **Shadows:** `shadow-sm` for cards, `shadow-md` for modals/dropdowns

### Data Flow
1. User uploads documents OR enters company ticker
2. Frontend parses files client-side (pdf.js / SheetJS)
3. Backend fetches EDGAR data via edgartools
4. All data sources sent to Claude API with structured prompts
5. Claude returns AnalysisJSON (validated by Pydantic)
6. Frontend renders financial statements, metrics, KPIs, and narrative

### API Patterns
- All backend routes under `/api/`
- JSON request/response bodies
- Pydantic models for validation
- SSE streaming for Claude analysis responses
- CORS enabled for local development

### Error Handling
- Backend: FastAPI exception handlers, structured error JSON
- Frontend: Toast notifications for user errors, console for dev errors
- Never expose raw stack traces to the user

### Git
- Branch naming: `pr-N-short-description` (e.g., `pr-1-project-plan`)
- Commit messages: conventional commits style
- One PR per feature slice
