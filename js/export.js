/**
 * IGSB-Analyst — Export & Session Management Module
 * Handles JSON/PDF export and localStorage persistence.
 */

const STORAGE_KEY = 'igsb-analyst-session';

/**
 * Save current session state to localStorage
 * @param {object} state - { ticker, edgarData, analysisResult }
 */
export function saveSession(state) {
  try {
    const session = {
      ticker: state.ticker,
      edgarData: state.edgarData,
      analysisResult: state.analysisResult,
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    console.log('[Export] Session saved');
  } catch (err) {
    console.warn('[Export] Failed to save session:', err.message);
  }
}

/**
 * Restore session from localStorage
 * @returns {object|null} Saved state or null
 */
export function restoreSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw);
    console.log('[Export] Session restored from', session.savedAt);
    return session;
  } catch (err) {
    console.warn('[Export] Failed to restore session:', err.message);
    return null;
  }
}

/**
 * Clear saved session
 */
export function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
  console.log('[Export] Session cleared');
}

/**
 * Export analysis result as a JSON file download
 * @param {object} analysisResult - The AnalysisJSON object
 * @param {string} ticker - Company ticker for filename
 */
export function exportJSON(analysisResult, ticker = 'analysis') {
  if (!analysisResult) {
    console.warn('[Export] No analysis result to export');
    return;
  }

  const json = JSON.stringify(analysisResult, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const filename = `${ticker.toLowerCase()}-analysis-${formatDate()}.json`;
  downloadFile(url, filename);

  URL.revokeObjectURL(url);
}

/**
 * Export as PDF using browser print functionality
 * The css/styles.css already has @media print rules that hide
 * the header, footer, sidebar, and non-essential elements.
 */
export function exportPDF() {
  window.print();
}

/**
 * Export analysis as a CSV file (financial statements only)
 * @param {object} analysisResult - The AnalysisJSON object
 * @param {string} ticker - Company ticker for filename
 */
export function exportCSV(analysisResult, ticker = 'analysis') {
  if (!analysisResult?.financial_statements) {
    console.warn('[Export] No financial data to export');
    return;
  }

  const statements = analysisResult.financial_statements;
  const lines = [];

  for (const [stmtKey, stmtName] of [
    ['income_statement', 'Income Statement'],
    ['balance_sheet', 'Balance Sheet'],
    ['cash_flow_statement', 'Cash Flow Statement'],
  ]) {
    const stmt = statements[stmtKey];
    if (!stmt) continue;

    lines.push(stmtName);
    const periods = stmt.periods || [];
    lines.push(['Line Item', ...periods].join(','));

    for (const item of stmt.line_items || []) {
      const values = periods.map(p => item.values?.[p] ?? '');
      lines.push([`"${item.label}"`, ...values].join(','));
    }
    lines.push(''); // blank line between statements
  }

  const csv = lines.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const filename = `${ticker.toLowerCase()}-financials-${formatDate()}.csv`;
  downloadFile(url, filename);

  URL.revokeObjectURL(url);
}

/**
 * Initialize export module — wire up auto-save on analysis complete
 */
export function initExport() {
  // Auto-save when analysis completes
  document.addEventListener('analysis-complete', (e) => {
    // We need access to app state — import will be done in app.js
    // This just logs; actual save is called from app.js
    console.log('[Export] Analysis complete event received');
  });

  // Warn before leaving with unsaved analysis
  window.addEventListener('beforeunload', (e) => {
    const hasSession = localStorage.getItem(STORAGE_KEY);
    if (hasSession) {
      // Session is already saved, no need to warn
      return;
    }
  });
}

// ---- Helpers ----

function downloadFile(url, filename) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function formatDate() {
  const now = new Date();
  return now.toISOString().split('T')[0];
}
