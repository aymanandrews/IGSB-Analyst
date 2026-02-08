/**
 * Investment Group of Santa Barbara — Main Application Controller
 * Entry point that initializes all modules.
 */

import { initUpload, uploadedDocuments, getParsedData } from './upload.js';
import { fetchCompanyInfo, fetchFinancials, getCompanyInfo, getFinancialStatements } from './edgar.js';
import { runAnalysis, cancelAnalysis, getCurrentAnalysis } from './analysis.js';
import { renderAnalysis } from './renderer.js';
import { initExport, saveSession, restoreSession, exportJSON, exportPDF, exportCSV } from './export.js';

// App state
const state = {
  ticker: null,
  edgarData: null,
  analysisResult: null,
  isAnalyzing: false,
};

/**
 * Initialize the application
 */
function init() {
  initUpload();
  initExport();
  wireTickerSearch();
  wireAnalysisButton();
  wireExportButton();

  // Restore previous session if available
  const saved = restoreSession();
  if (saved && saved.analysisResult) {
    state.ticker = saved.ticker;
    state.edgarData = saved.edgarData;
    state.analysisResult = saved.analysisResult;
    renderAnalysis(saved.analysisResult);
    showAnalysisContent();

    // Restore ticker input
    const tickerInput = document.getElementById('ticker-input');
    if (tickerInput && saved.ticker) tickerInput.value = saved.ticker;
    const edgarTicker = document.getElementById('edgar-ticker');
    if (edgarTicker && saved.ticker) edgarTicker.value = saved.ticker;

    showToast('Previous session restored', 'info');
  }

  console.log('[IGSB-Analyst] Initialized');
}

/**
 * Wire up ticker search from header and EDGAR sidebar
 */
function wireTickerSearch() {
  const searchBtn = document.getElementById('ticker-search-btn');
  const tickerInput = document.getElementById('ticker-input');
  const edgarFetchBtn = document.getElementById('edgar-fetch-btn');

  if (searchBtn && tickerInput) {
    searchBtn.addEventListener('click', () => {
      const ticker = tickerInput.value.trim().toUpperCase();
      if (ticker) handleTickerSearch(ticker);
    });

    tickerInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const ticker = tickerInput.value.trim().toUpperCase();
        if (ticker) handleTickerSearch(ticker);
      }
    });
  }

  if (edgarFetchBtn) {
    edgarFetchBtn.addEventListener('click', () => {
      const ticker = document.getElementById('edgar-ticker')?.value.trim().toUpperCase();
      if (ticker) handleTickerSearch(ticker);
    });
  }
}

/**
 * Try loading a pre-generated analysis from data/companies/{TICKER}/ directory.
 * Reads the manifest to find the default filing, then loads that JSON.
 */
async function loadCachedAnalysis(ticker) {
  const t = ticker.toUpperCase();
  try {
    const manifestRes = await fetch(`data/companies/${t}/manifest.json`);
    if (!manifestRes.ok) return null;
    const manifest = await manifestRes.json();
    if (!manifest.default_filing) return null;
    const fileRes = await fetch(`data/companies/${t}/${manifest.default_filing}`);
    if (!fileRes.ok) return null;
    return await fileRes.json();
  } catch {
    return null;
  }
}

/**
 * Handle ticker search — fetches company data from EDGAR + loads cached analysis
 */
async function handleTickerSearch(ticker) {
  state.ticker = ticker;
  showToast(`Fetching data for ${ticker}...`, 'info');

  // Try EDGAR backend first
  try {
    const data = await fetchFinancials(ticker);
    state.edgarData = data;

    const companyName = document.getElementById('company-name');
    const companyTicker = document.getElementById('company-ticker');
    if (companyName) companyName.textContent = data.company.name;
    if (companyTicker) companyTicker.textContent = data.company.ticker;

    showAnalysisContent();
    showToast(`Loaded EDGAR data for ${data.company.name}`, 'success');
  } catch (err) {
    console.warn('[IGSB-Analyst] EDGAR fetch failed, trying cached data:', err.message);
  }

  // Try loading cached analysis
  const cached = await loadCachedAnalysis(ticker);
  if (cached) {
    state.analysisResult = cached;
    renderAnalysis(cached);
    saveSession(state);
    showAnalysisContent();
    showToast(`Loaded pre-generated analysis for ${ticker}`, 'success');
  }
}

/**
 * Wire up the Run Analysis button
 */
function wireAnalysisButton() {
  const btn = document.getElementById('run-analysis-btn');
  if (btn) {
    btn.addEventListener('click', handleRunAnalysis);
  }
}

/**
 * Handle analysis run — tries cached analysis first, then Claude API
 */
async function handleRunAnalysis() {
  if (state.isAnalyzing) return;

  const parsedDocs = getParsedData();
  const hasData = parsedDocs.length > 0 || state.edgarData;

  if (!hasData) {
    showToast('Upload documents or search a ticker first', 'warning');
    return;
  }

  // If we already have a cached result loaded, just re-render it
  if (state.analysisResult && !parsedDocs.length) {
    renderAnalysis(state.analysisResult);
    showAnalysisContent();
    showToast('Analysis already loaded', 'info');
    return;
  }

  // Try cached analysis file first
  if (state.ticker) {
    const cached = await loadCachedAnalysis(state.ticker);
    if (cached) {
      state.analysisResult = cached;
      renderAnalysis(cached);
      saveSession(state);
      showAnalysisContent();
      showToast('Loaded pre-generated analysis', 'success');
      return;
    }
  }

  state.isAnalyzing = true;
  const btn = document.getElementById('run-analysis-btn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Analyzing...';
  }

  showToast('Starting Claude analysis...', 'info');
  showAnalysisContent();

  const analystNotes = document.getElementById('analyst-notes')?.value || null;

  await runAnalysis(
    {
      companyInfo: state.edgarData?.company || null,
      financialStatements: state.edgarData?.financial_statements || null,
      uploadedDocuments: parsedDocs,
      analystNotes,
    },
    // onDelta — streaming text chunk
    (text) => {
      const streamEl = document.getElementById('analysis-stream');
      if (streamEl) {
        streamEl.textContent += text;
        streamEl.classList.remove('hidden');
      }
    },
    // onComplete — full AnalysisJSON received
    (result) => {
      state.analysisResult = result;
      state.isAnalyzing = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Run Analysis';
      }
      const streamEl = document.getElementById('analysis-stream');
      if (streamEl) streamEl.classList.add('hidden');
      renderAnalysis(result);
      saveSession(state);
      showToast('Analysis complete', 'success');
    },
    // onError
    (errMsg) => {
      state.isAnalyzing = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Run Analysis';
      }
      showToast(`Analysis failed: ${errMsg}`, 'error');
    }
  );
}

/**
 * Wire up export buttons
 */
function wireExportButton() {
  // Header export button — defaults to JSON
  const btn = document.getElementById('header-export-btn');
  if (btn) {
    btn.addEventListener('click', () => {
      if (!state.analysisResult) {
        showToast('Run an analysis first before exporting', 'warning');
        return;
      }
      exportJSON(state.analysisResult, state.ticker || 'analysis');
      showToast('JSON report downloaded', 'success');
    });
  }

  // Sidebar export button — show dropdown or default to JSON
  const sidebarBtn = document.getElementById('export-report-btn');
  if (sidebarBtn) {
    sidebarBtn.addEventListener('click', () => {
      if (!state.analysisResult) {
        showToast('Run an analysis first before exporting', 'warning');
        return;
      }
      exportJSON(state.analysisResult, state.ticker || 'analysis');
      showToast('JSON report downloaded', 'success');
    });
  }
}

/**
 * Show/hide the empty state vs analysis content
 */
export function showAnalysisContent() {
  document.getElementById('empty-state')?.classList.add('hidden');
  document.getElementById('analysis-content')?.classList.remove('hidden');
}

export function showEmptyState() {
  document.getElementById('empty-state')?.classList.remove('hidden');
  document.getElementById('analysis-content')?.classList.add('hidden');
}

/**
 * Toast helper (delegates to upload.js toast or creates simple one)
 */
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const colors = {
    success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    error: 'bg-red-50 border-red-200 text-red-800',
    warning: 'bg-amber-50 border-amber-200 text-amber-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
  };

  const toast = document.createElement('div');
  toast.className = `toast ${colors[type] || colors.info} border rounded-lg px-4 py-3 shadow-md text-sm font-medium`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-exit');
    toast.addEventListener('animationend', () => toast.remove());
  }, 4000);
}

// Export state for other modules
export { state };

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
