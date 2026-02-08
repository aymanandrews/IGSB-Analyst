# Folio: Pull Request Roadmap

## Overview

The project is built incrementally across 8 PRs, each delivering a working slice of functionality.

## PR Sequence

### PR #1: Project Plan + CLAUDE.md
**Branch:** `pr-1-project-plan`
**Files:**
- `CLAUDE.md` — project context, conventions, design system
- `docs/architecture.md` — technical architecture
- `docs/schema.md` — AnalysisJSON specification
- `docs/pull-requests.md` — this file
- `.gitignore`

**Outcome:** Repository initialized with full project documentation.

---

### PR #2: Static Shell + Design System
**Branch:** `pr-2-static-shell`
**Files:**
- `index.html` — full SPA layout (header, sidebar, main panels, footer)
- `css/styles.css` — custom styles beyond Tailwind utilities

**Outcome:** Pixel-complete empty shell of the application. All panels visible with placeholder content. Responsive layout. Design system fully applied.

---

### PR #3: File Parsing + Upload UI
**Branch:** `pr-3-file-parsing`
**Files:**
- `js/upload.js` — file upload handler, PDF/Excel/text parsing
- Upload UI components in `index.html`
- Source attribution display

**Outcome:** Users can drag-and-drop or select files. PDFs parsed via pdf.js, Excel via SheetJS. Parsed content displayed with source labels.

---

### PR #4: Backend + EDGAR Integration
**Branch:** `pr-4-backend-edgar`
**Files:**
- `backend/main.py` — FastAPI app with CORS
- `backend/edgar_service.py` — edgartools wrapper
- `backend/routers/edgar.py` — EDGAR API routes
- `backend/schemas/edgar.py` — Pydantic response models
- `requirements.txt`
- `js/edgar.js` — frontend EDGAR data fetching

**Outcome:** Enter a ticker, fetch real SEC financial data via EDGAR. Data displayed in raw/debug format.

---

### PR #5: Claude API + Prompt Engine + AnalysisJSON
**Branch:** `pr-5-claude-analysis`
**Files:**
- `backend/analysis_service.py` — Claude API integration + prompt engine
- `backend/routers/analysis.py` — analysis API routes (SSE streaming)
- `backend/schemas/analysis.py` — AnalysisJSON Pydantic models
- `js/analysis.js` — frontend analysis orchestration

**Outcome:** Financial data + uploaded docs sent to Claude. Structured AnalysisJSON returned and validated. SSE streaming shows progressive output.

---

### PR #6: Financial Renderer + Metrics + KPIs
**Branch:** `pr-6-financial-renderer`
**Files:**
- `js/renderer.js` — financial statement table renderer
- KPI card components
- Derived metrics display

**Outcome:** AnalysisJSON rendered into formatted financial statement tables, KPI dashboard cards, and derived metrics panels. Numbers formatted with proper accounting conventions.

---

### PR #7: Analyst Input + Qualitative + Source Manifest
**Branch:** `pr-7-analyst-qualitative`
**Files:**
- Analyst input UI (notes, overrides, custom context)
- Narrative/qualitative section rendering
- Source manifest / attribution panel
- Data quality indicators

**Outcome:** Analysts can add custom context. AI-generated narrative sections rendered with sentiment indicators. Full source attribution visible for every data point.

---

### PR #8: Session Management + Export + Polish
**Branch:** `pr-8-session-export`
**Files:**
- `js/export.js` — PDF + JSON export
- localStorage session persistence
- Error handling + loading states
- Final UI polish

**Outcome:** Complete working application. Sessions persist across reloads. Analysis exportable as PDF report or raw JSON. Proper loading spinners and error toasts throughout.

## Definition of Done (per PR)

- [ ] All files from the PR spec are created/modified
- [ ] Code follows conventions from CLAUDE.md
- [ ] No hardcoded API keys or secrets
- [ ] HTML is semantic and accessible
- [ ] Works in Chrome/Firefox latest
