/**
 * Folio — Analysis Orchestration Module
 * Sends data to Claude via backend, handles SSE streaming, validates response.
 */

const API_BASE = 'http://localhost:8000/api/analysis';

/** @type {object|null} */
let currentAnalysis = null;

/** @type {AbortController|null} */
let currentStream = null;

/**
 * Run analysis via backend SSE stream
 * @param {object} params
 * @param {object|null} params.companyInfo
 * @param {object|null} params.financialStatements
 * @param {Array} params.uploadedDocuments
 * @param {string|null} params.analystNotes
 * @param {string} params.model
 * @param {function} onDelta - called with each text chunk
 * @param {function} onComplete - called with final AnalysisJSON
 * @param {function} onError - called with error message
 * @returns {Promise<void>}
 */
export async function runAnalysis({ companyInfo, financialStatements, uploadedDocuments, analystNotes, model }, onDelta, onComplete, onError) {
  // Cancel any existing stream
  cancelAnalysis();

  currentStream = new AbortController();

  try {
    const res = await fetch(`${API_BASE}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_info: companyInfo || null,
        financial_statements: financialStatements || null,
        uploaded_documents: uploadedDocuments || [],
        analyst_notes: analystNotes || null,
        model: model || 'claude-sonnet-4-5-20250929',
      }),
      signal: currentStream.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Analysis request failed: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);

          if (event.event === 'delta' && event.text) {
            onDelta(event.text);
          } else if (event.event === 'complete' && event.result) {
            currentAnalysis = event.result;
            onComplete(event.result);
            document.dispatchEvent(new CustomEvent('analysis-complete', { detail: event.result }));
          } else if (event.event === 'error') {
            onError(event.message || 'Unknown analysis error');
          } else if (event.event === 'start') {
            console.log('[Analysis] Started:', event.analysis_id);
          }
        } catch (parseErr) {
          console.warn('[Analysis] Failed to parse SSE event:', parseErr);
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      console.log('[Analysis] Cancelled by user');
      return;
    }
    onError(err.message);
  } finally {
    currentStream = null;
  }
}

/**
 * Cancel an in-progress analysis
 */
export function cancelAnalysis() {
  if (currentStream) {
    currentStream.abort();
    currentStream = null;
  }
}

/**
 * Get the current analysis result
 * @returns {object|null}
 */
export function getCurrentAnalysis() {
  return currentAnalysis;
}

/**
 * Set analysis result (e.g., from localStorage restore)
 * @param {object} analysis
 */
export function setCurrentAnalysis(analysis) {
  currentAnalysis = analysis;
}

/**
 * Validate that an object conforms to basic AnalysisJSON structure
 * @param {object} obj
 * @returns {{ valid: boolean, errors: string[] }}
 */
export function validateAnalysisJSON(obj) {
  const errors = [];
  const requiredKeys = ['company', 'financial_statements', 'derived_metrics', 'kpis', 'narrative', 'sources', 'data_quality'];

  for (const key of requiredKeys) {
    if (!(key in obj)) {
      errors.push(`Missing required key: ${key}`);
    }
  }

  if (obj.kpis && !Array.isArray(obj.kpis)) {
    errors.push('kpis must be an array');
  }

  if (obj.sources && !Array.isArray(obj.sources)) {
    errors.push('sources must be an array');
  }

  if (obj.financial_statements) {
    const stmts = obj.financial_statements;
    for (const key of ['income_statement', 'balance_sheet', 'cash_flow_statement']) {
      if (stmts[key] && !Array.isArray(stmts[key].line_items)) {
        errors.push(`financial_statements.${key}.line_items must be an array`);
      }
    }
  }

  return { valid: errors.length === 0, errors };
}
