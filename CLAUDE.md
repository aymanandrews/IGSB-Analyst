# Folio

## Project Overview
Equity research platform. Combines EDGAR/SEC filings data, uploaded documents (PDF/Excel/text), and Claude AI analysis to produce structured investment analysis reports with source attribution.

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

## Learnings & Build Notes

This project was built in a single Claude Code session across 8 PR-sized increments using parallel subagents for speed. Here's what we learned:

### What Worked Well
- **Parallel subagent strategy:** Launching 2-3 file-writing agents simultaneously per PR cut wall-clock time significantly. Each agent writes independent files, then a single integration pass fixes imports and cross-references.
- **PR-sized increments:** Each commit delivers a visible slice of functionality. This makes debugging easier — if something breaks, you know which slice caused it.
- **Static SPA + FastAPI:** No build step on the frontend means instant iteration. Tailwind CDN + vanilla JS eliminates toolchain complexity entirely.
- **Pre-generated analysis as fallback:** When API credits aren't available, cached AnalysisJSON files in `data/` let the full UI work without a live Claude API call. Claude Code itself can generate the analysis.
- **edgartools library:** Excellent for structured SEC data. The `EntityFacts` API gives you income statement, balance sheet, and cash flow as pandas DataFrames directly.

### Gotchas & Fixes
- **Python 3.9 vs 3.10+ type syntax:** Pydantic evaluates model field annotations at runtime, so `str | None` fails on Python 3.9 even with `from __future__ import annotations`. Fix: use `Optional[str]` from `typing` in all Pydantic models.
- **edgartools + hishel version conflict:** edgartools 4.6.x requires hishel >= 0.1.3, but hishel 1.1.x breaks with `module 'hishel' has no attribute 'FileStorage'`. Fix: pin `hishel>=0.1.3,<1.0`.
- **edgartools API evolution:** The `facts.get("us-gaap", concept_name)` pattern from older docs doesn't work in v4.6. Use `facts.income_statement()`, `facts.balance_sheet()`, `facts.cash_flow()` which return `FinancialStatement` objects with `.data` DataFrames.
- **Inline styles vs external CSS:** When subagents write HTML, they tend to inline `<style>` blocks. Always do an integration pass to replace with `<link rel="stylesheet">` pointing to the external CSS file.
- **CSS class name mismatch:** HTML agents may use `tab-active`/`tab-inactive` while CSS agents write `.tab-btn.active`. Check class names match across files.
- **Module script loading:** Use a single `<script type="module" src="js/app.js">` entry point that imports all other modules. Don't load modules as separate script tags.
- **CDN library loading patterns:** pdf.js loads as an ES module (`type="module"`), SheetJS loads as a global script (`window.XLSX`). They need different `<script>` tag patterns.

### Running Locally
```bash
# Backend (from backend/ directory)
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...  # optional, needed for live Claude analysis
cd backend && uvicorn main:app --reload --port 8000

# Frontend (from project root)
python -m http.server 3000

# Open http://localhost:3000, search "APPF" for AppFolio demo
```

### Cached Analysis (No API Key Needed)
Pre-generated analysis files live in `data/{TICKER}-analysis.json`. The app auto-loads these when you search a ticker. To generate more, you can use Claude Code to analyze EDGAR data and write the JSON manually — no API credits required.
