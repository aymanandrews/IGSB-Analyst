/**
 * Investment Group of Santa Barbara — EDGAR Data Fetching Module
 * Communicates with the FastAPI backend to fetch SEC/EDGAR data.
 */

const API_BASE = 'http://localhost:8000/api/edgar';

/** @type {object|null} */
let companyInfo = null;

/** @type {object|null} */
let financialStatements = null;

/** @type {Array} */
const edgarSources = [];

/**
 * Fetch company info from EDGAR via backend
 * @param {string} ticker
 * @returns {Promise<object>}
 */
export async function fetchCompanyInfo(ticker) {
  const res = await fetch(`${API_BASE}/company/${encodeURIComponent(ticker)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to fetch company: ${res.status}`);
  }
  companyInfo = await res.json();
  return companyInfo;
}

/**
 * Fetch structured financial statements from EDGAR via backend
 * @param {string} ticker
 * @returns {Promise<object>}
 */
export async function fetchFinancials(ticker) {
  const res = await fetch(`${API_BASE}/financials/${encodeURIComponent(ticker)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to fetch financials: ${res.status}`);
  }
  const data = await res.json();
  companyInfo = data.company;
  financialStatements = data.financial_statements;

  // Create source attribution
  edgarSources.length = 0;
  edgarSources.push({
    id: 0,
    type: 'sec_filing',
    label: `${ticker.toUpperCase()} 10-K (EDGAR)`,
    url: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${ticker}&type=10-K`,
    date: new Date().toISOString().split('T')[0],
    reliability: 'high',
  });

  updateSourceList();
  document.dispatchEvent(new CustomEvent('edgar-data-loaded', { detail: { companyInfo, financialStatements } }));

  return { company: companyInfo, financial_statements: financialStatements };
}

/**
 * Fetch filings list from EDGAR via backend
 * @param {string} ticker
 * @param {string} formType
 * @param {number} count
 * @returns {Promise<object>}
 */
export async function fetchFilings(ticker, formType = '10-K', count = 5) {
  const params = new URLSearchParams({ form_type: formType, count: String(count) });
  const res = await fetch(`${API_BASE}/filings/${encodeURIComponent(ticker)}?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to fetch filings: ${res.status}`);
  }
  return res.json();
}

/**
 * Update the sidebar source list with EDGAR sources
 */
function updateSourceList() {
  const sourceList = document.getElementById('source-list');
  if (!sourceList) return;

  // Remove existing EDGAR sources
  sourceList.querySelectorAll('[data-source-type="sec_filing"]').forEach(el => el.remove());

  // Remove empty state if present
  const emptyState = sourceList.querySelector('.text-slate-400');
  if (emptyState && edgarSources.length > 0) {
    emptyState.remove();
  }

  for (const source of edgarSources) {
    const el = document.createElement('div');
    el.setAttribute('data-source-type', 'sec_filing');
    el.className = 'flex items-center gap-2 text-xs py-1.5';
    el.innerHTML = `
      <span class="source-tag source-tag-sec">SEC</span>
      <span class="text-slate-700 truncate flex-1">${escapeHtml(source.label)}</span>
      <span class="text-emerald-600 text-xs font-medium">High</span>
    `;
    sourceList.prepend(el);
  }

  // Update footer source count
  const footerCount = document.getElementById('footer-source-count');
  if (footerCount) {
    const totalSources = sourceList.children.length;
    footerCount.textContent = `${totalSources} source${totalSources !== 1 ? 's' : ''} loaded`;
  }
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

export function getCompanyInfo() {
  return companyInfo;
}

export function getFinancialStatements() {
  return financialStatements;
}

export function getEdgarSources() {
  return [...edgarSources];
}
