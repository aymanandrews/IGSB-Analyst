/**
 * IGSB-Analyst — Main Application Controller
 * Entry point that initializes all modules.
 */

import { initUpload, uploadedDocuments, getParsedData } from './upload.js';
import { fetchCompanyInfo, fetchFinancials, getCompanyInfo, getFinancialStatements } from './edgar.js';
import { runAnalysis, cancelAnalysis, getCurrentAnalysis } from './analysis.js';
import { renderAnalysis } from './renderer.js';

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
  wireTickerSearch();
  wireAnalysisButton();
  wireExportButton();

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
 * Handle ticker search — fetches company data from EDGAR
 */
async function handleTickerSearch(ticker) {
  state.ticker = ticker;
  showToast(`Fetching EDGAR data for ${ticker}...`, 'info');

  try {
    const data = await fetchFinancials(ticker);
    state.edgarData = data;

    // Update company header if it exists
    const companyName = document.getElementById('company-name');
    const companyTicker = document.getElementById('company-ticker');
    if (companyName) companyName.textContent = data.company.name;
    if (companyTicker) companyTicker.textContent = data.company.ticker;

    showAnalysisContent();
    showToast(`Loaded financial data for ${data.company.name}`, 'success');
  } catch (err) {
    console.error('[IGSB-Analyst] EDGAR fetch failed:', err);
    showToast(`Failed to fetch data for ${ticker}: ${err.message}`, 'error');
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
 * Handle analysis run — sends data to Claude via backend
 */
async function handleRunAnalysis() {
  if (state.isAnalyzing) return;

  const parsedDocs = getParsedData();
  const hasData = parsedDocs.length > 0 || state.edgarData;

  if (!hasData) {
    showToast('Upload documents or search a ticker first', 'warning');
    return;
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
 * Wire up export button — will be fully implemented in PR #8
 */
function wireExportButton() {
  const btn = document.getElementById('export-btn');
  if (btn) {
    btn.addEventListener('click', () => {
      if (!state.analysisResult) {
        showToast('Run an analysis first before exporting', 'warning');
        return;
      }
      // TODO: PR #8 — call export.js
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
