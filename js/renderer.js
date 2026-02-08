/**
 * Folio — Financial Statement Renderer
 * Takes AnalysisJSON data and renders KPI cards, financial statements,
 * derived metrics, narrative, and source attribution into the DOM.
 */

// ============================================================
// XSS-safe text escaping
// ============================================================

const _escapeEl = document.createElement('div');

/**
 * Escape a string for safe insertion into HTML.
 * @param {string} str
 * @returns {string}
 */
function escapeHTML(str) {
  if (str == null) return '';
  _escapeEl.textContent = String(str);
  return _escapeEl.innerHTML;
}

// ============================================================
// Number Formatting Utilities
// ============================================================

/**
 * Format a raw monetary value.
 * Compact mode: $94.9B, $1.2M, $340K
 * Full mode:    $94,930M (millions with commas)
 * @param {number|null|undefined} value
 * @param {boolean} compact
 * @returns {string}
 */
export function formatCurrency(value, compact = false) {
  if (value == null || isNaN(value)) return '\u2014';

  const abs = Math.abs(value);
  const negative = value < 0;
  let formatted;

  if (compact) {
    if (abs >= 1e12) {
      formatted = '$' + (abs / 1e12).toFixed(1) + 'T';
    } else if (abs >= 1e9) {
      formatted = '$' + (abs / 1e9).toFixed(1) + 'B';
    } else if (abs >= 1e6) {
      formatted = '$' + (abs / 1e6).toFixed(1) + 'M';
    } else if (abs >= 1e3) {
      formatted = '$' + (abs / 1e3).toFixed(0) + 'K';
    } else {
      formatted = '$' + abs.toFixed(2);
    }
  } else {
    // Full mode: value in millions with commas
    const millions = abs / 1e6;
    if (millions >= 1) {
      formatted = Math.round(millions).toLocaleString('en-US');
    } else {
      formatted = abs.toLocaleString('en-US', { maximumFractionDigits: 0 });
    }
  }

  if (negative) {
    return compact ? '-' + formatted : '(' + formatted + ')';
  }
  return formatted;
}

/**
 * Format a decimal as a percentage string.
 * 0.463 -> "46.3%"
 * @param {number|null|undefined} value
 * @returns {string}
 */
export function formatPercent(value) {
  if (value == null || isNaN(value)) return '\u2014';
  return (value * 100).toFixed(1) + '%';
}

/**
 * Format a numeric ratio.
 * 1.872 -> "1.87x"
 * @param {number|null|undefined} value
 * @returns {string}
 */
export function formatRatio(value) {
  if (value == null || isNaN(value)) return '\u2014';
  return value.toFixed(2) + 'x';
}

/**
 * Format a plain number with commas.
 * 29160 -> "29,160"
 * @param {number|null|undefined} value
 * @param {number} decimals
 * @returns {string}
 */
function formatNumber(value, decimals = 2) {
  if (value == null || isNaN(value)) return '\u2014';
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}

/**
 * Return the trend arrow character.
 * @param {string} trend - "up", "down", or "stable"
 * @returns {string}
 */
function trendArrow(trend) {
  switch (trend) {
    case 'up': return '\u2191';
    case 'down': return '\u2193';
    case 'stable': return '\u2192';
    default: return '';
  }
}

/**
 * Return the Tailwind text-color class for a trend.
 * @param {string} trend
 * @returns {string}
 */
function trendColor(trend) {
  switch (trend) {
    case 'up': return 'text-emerald-600';
    case 'down': return 'text-red-600';
    case 'stable': return 'text-slate-400';
    default: return 'text-slate-400';
  }
}

/**
 * Return a Tailwind bg+text class pair for a trend badge.
 * @param {string} trend
 * @returns {{ bg: string, text: string }}
 */
function trendBadgeClasses(trend) {
  switch (trend) {
    case 'up': return { bg: 'bg-emerald-50', text: 'text-emerald-700' };
    case 'down': return { bg: 'bg-red-50', text: 'text-red-700' };
    case 'stable': return { bg: 'bg-slate-100', text: 'text-slate-600' };
    default: return { bg: 'bg-slate-100', text: 'text-slate-600' };
  }
}

/**
 * Detect if a metric value looks like a percentage (absolute value <= 2 and name
 * contains margin, return, yield, etc.) or a ratio (name contains ratio, turnover,
 * coverage, multiplier, etc.) and format accordingly.
 * @param {string} key - snake_case metric key
 * @param {number|null|undefined} value
 * @returns {string}
 */
function autoFormatMetric(key, value) {
  if (value == null || isNaN(value)) return '\u2014';

  const k = key.toLowerCase();
  const pctKeywords = ['margin', 'roe', 'roa', 'roic', 'yield', 'return', 'payout', 'sbc_pct', 'pct'];
  const ratioKeywords = ['ratio', 'turnover', 'coverage', 'multiplier', 'debt_to', 'net_debt', 'leverage'];
  const currencyKeywords = ['working_capital', 'net_debt', 'ebitda', 'fcf', 'revenue_per'];

  if (pctKeywords.some(w => k.includes(w))) {
    return formatPercent(value);
  }
  if (ratioKeywords.some(w => k.includes(w))) {
    return formatRatio(value);
  }
  if (currencyKeywords.some(w => k.includes(w)) && Math.abs(value) >= 1e6) {
    return formatCurrency(value, true);
  }
  return formatNumber(value);
}

/**
 * Convert a snake_case or camelCase key to a human-readable label.
 * "gross_margin" -> "Gross Margin"
 * @param {string} key
 * @returns {string}
 */
function humanizeKey(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/\bRoe\b/gi, 'ROE')
    .replace(/\bRoa\b/gi, 'ROA')
    .replace(/\bRoic\b/gi, 'ROIC')
    .replace(/\bFcf\b/gi, 'FCF')
    .replace(/\bSbc\b/gi, 'SBC')
    .replace(/\bEbitda\b/gi, 'EBITDA')
    .replace(/\bDso\b/gi, 'DSO')
    .replace(/\bDpo\b/gi, 'DPO')
    .replace(/\bPct\b/gi, '%')
    .replace(/\bO\/s\b/gi, 'O/S');
}

// ============================================================
// Concept classification for financial statements
// ============================================================

const SUBTOTAL_CONCEPTS = new Set([
  'GrossProfit',
  'OperatingIncomeLoss',
  'OperatingExpenses',
  'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
  'IncomeFromContinuingOperations',
  'AssetsCurrent',
  'LiabilitiesCurrent',
  'TotalCurrentAssets',
  'TotalCurrentLiabilities',
  'CashFromOperations',
  'CashFromInvesting',
  'CashFromFinancing',
  'NetCashProvidedByOperatingActivities',
  'NetCashUsedInInvestingActivities',
  'NetCashUsedInFinancingActivities',
  'NetCashProvidedByUsedInInvestingActivities',
  'NetCashProvidedByUsedInFinancingActivities',
]);

const TOTAL_CONCEPTS = new Set([
  'NetIncomeLoss',
  'Assets',
  'Liabilities',
  'StockholdersEquity',
  'LiabilitiesAndStockholdersEquity',
  'TotalAssets',
  'TotalLiabilities',
  'TotalStockholdersEquity',
  'FreeCashFlow',
  'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect',
]);

const INDENT_CONCEPTS = new Set([
  'Products',
  'Services',
  'DepreciationAndAmortization',
  'DepreciationDepletionAndAmortization',
  'StockBasedCompensation',
  'ShareBasedCompensation',
  'ChangesInWorkingCapital',
  'IncreaseDecreaseInOperatingCapital',
  'DeferredIncomeTax',
  'AccountsReceivableChange',
  'InventoryChange',
  'AccountsPayableChange',
  'OtherNoncashIncomeExpense',
  'ResearchAndDevelopmentExpense',
  'SellingAndMarketingExpense',
  'GeneralAndAdministrativeExpense',
  'CostOfGoodsAndServicesSold',
  'PaymentsToAcquirePropertyPlantAndEquipment',
  'PaymentsToAcquireBusinessesNetOfCashAcquired',
  'PaymentsToAcquireInvestments',
  'ProceedsFromMaturitiesPrepaymentsAndCallsOfAvailableForSaleSecurities',
  'PaymentsForRepurchaseOfCommonStock',
  'ProceedsFromStockPlans',
  'PaymentsRelatedToTaxWithholdingForShareBasedCompensation',
]);

/**
 * Determine the CSS row class for a line item.
 * @param {object} item - { label, concept, values, ... }
 * @returns {string}
 */
function rowClass(item) {
  const concept = (item.concept || '').replace(/^us-gaap:/, '').replace(/^derived:/, '');
  // Margin/percent rows get special styling
  if (item.unit === 'percent') return 'margin-row';
  if (TOTAL_CONCEPTS.has(concept)) return 'total';
  if (SUBTOTAL_CONCEPTS.has(concept)) return 'subtotal';
  if (INDENT_CONCEPTS.has(concept)) return 'indent-1';
  // Detect indentation from label leading spaces
  if (item.label && /^\s{2,}/.test(item.label)) return 'indent-1';
  return '';
}

// ============================================================
// Sub-Renderers
// ============================================================

/**
 * Render the company header bar.
 * @param {object} company
 */
function renderCompanyHeader(company) {
  if (!company) return;

  const nameEl = document.getElementById('company-name');
  const tickerBadge = document.getElementById('company-ticker-badge');
  const metaEl = document.getElementById('company-meta');

  if (nameEl) nameEl.textContent = company.name || '';
  if (tickerBadge) tickerBadge.textContent = company.ticker || '';

  if (metaEl) {
    const parts = [];
    if (company.exchange) parts.push(escapeHTML(company.exchange));
    if (company.sector) parts.push(escapeHTML(company.sector));
    if (company.industry) parts.push(escapeHTML(company.industry));
    if (company.fiscal_year_end) parts.push('FY ends ' + escapeHTML(company.fiscal_year_end));
    metaEl.textContent = parts.join(' | ');
  }
}

/**
 * Render headline valuation metrics strip.
 * @param {Array} metrics - headline_metrics array from AnalysisJSON
 */
export function renderHeadlineMetrics(metrics) {
  if (!metrics || !Array.isArray(metrics)) return;

  const container = document.getElementById('headline-metrics');
  if (!container) return;

  container.innerHTML = '';
  for (const m of metrics) {
    const el = document.createElement('div');
    el.className = 'flex flex-col items-center px-4 py-2';
    el.innerHTML = `
      <span class="text-[10px] font-medium text-slate-400 uppercase tracking-wider">${escapeHTML(m.label)}</span>
      <span class="text-sm font-bold font-mono tabular-nums text-slate-900 mt-0.5">${escapeHTML(m.formatted)}</span>
    `;
    container.appendChild(el);
  }
}

/**
 * Render KPI cards into #kpi-grid.
 * @param {Array} kpis
 */
export function renderKPIs(kpis) {
  if (!kpis || !Array.isArray(kpis)) return;

  const container = document.getElementById('kpi-grid');
  if (!container) return;

  // Build cards inside the existing grid wrapper
  const gridDiv = container.querySelector('.grid') || container;

  gridDiv.innerHTML = '';

  for (const kpi of kpis) {
    const displayValue = kpi.formatted
      ? escapeHTML(kpi.formatted)
      : (kpi.value != null ? escapeHTML(formatCurrency(kpi.value, true)) : '\u2014');

    const changeDisplay = kpi.change_formatted
      ? escapeHTML(kpi.change_formatted)
      : (kpi.change != null ? escapeHTML(formatPercent(kpi.change)) : '');

    const trend = kpi.trend || 'stable';
    const badge = trendBadgeClasses(trend);
    const arrow = trendArrow(trend);
    const period = escapeHTML(kpi.period || '');

    const card = document.createElement('div');
    card.className = 'kpi-card bg-white rounded-lg border border-slate-200 shadow-sm p-4';
    card.innerHTML = `
      <div class="text-xs font-medium text-slate-500 uppercase tracking-wide">${escapeHTML(kpi.label)}</div>
      <div class="text-2xl font-bold text-slate-900 font-mono mt-1">${displayValue}</div>
      <div class="flex items-center gap-1 mt-2">
        ${changeDisplay ? `<span class="inline-flex items-center px-1.5 py-0.5 text-[11px] font-semibold ${badge.bg} ${badge.text} rounded-full">${arrow} ${changeDisplay}</span>` : ''}
        ${period ? `<span class="text-[10px] text-slate-400">${period}</span>` : ''}
      </div>
    `;

    gridDiv.appendChild(card);
  }
}

/**
 * Render all three financial statement tables.
 * @param {object} statements - { income_statement, balance_sheet, cash_flow_statement }
 */
export function renderFinancialStatements(statements) {
  if (!statements) return;

  const mapping = [
    { key: 'income_statement', panelId: 'stmt-income' },
    { key: 'balance_sheet', panelId: 'stmt-balance' },
    { key: 'cash_flow_statement', panelId: 'stmt-cashflow' },
  ];

  for (const { key, panelId } of mapping) {
    const stmtData = statements[key];
    const panelEl = document.getElementById(panelId);
    if (!panelEl || !stmtData) continue;

    const periods = stmtData.periods || [];
    const lineItems = stmtData.line_items || [];
    const hasMultiplePeriods = periods.length >= 2;

    // Build table
    const table = document.createElement('table');
    table.className = 'stmt-table w-full text-sm';

    // -- thead --
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.className = 'border-b border-slate-200 bg-slate-50/50';

    // Line Item header
    const thLabel = document.createElement('th');
    thLabel.className = 'text-left py-2.5 px-4 text-xs font-semibold text-slate-600 w-[40%]';
    thLabel.textContent = 'Line Item';
    headerRow.appendChild(thLabel);

    // Period headers
    for (const period of periods) {
      const th = document.createElement('th');
      th.className = 'text-right py-2.5 px-4 text-xs font-semibold text-slate-600 font-mono';
      th.textContent = period;
      headerRow.appendChild(th);
    }

    // YoY Change header
    if (hasMultiplePeriods) {
      const thChange = document.createElement('th');
      thChange.className = 'text-right py-2.5 px-4 text-xs font-semibold text-slate-600 font-mono';
      thChange.textContent = 'Change %';
      headerRow.appendChild(thChange);
    }

    thead.appendChild(headerRow);
    table.appendChild(thead);

    // -- tbody --
    const tbody = document.createElement('tbody');
    tbody.className = 'divide-y divide-slate-100';

    for (const item of lineItems) {
      const tr = document.createElement('tr');
      const cls = rowClass(item);
      const hoverClass = cls === 'total' ? '' : ' hover:bg-slate-50/50';
      tr.className = (cls ? cls : '') + hoverClass;

      // Label cell
      const tdLabel = document.createElement('td');
      const isTotal = cls === 'total';
      const isSubtotal = cls === 'subtotal';
      const labelWeight = isTotal ? 'font-bold' : (isSubtotal ? 'font-semibold' : 'font-medium');
      const labelColor = (cls === 'indent-1') ? 'text-slate-700' : 'text-slate-900';
      tdLabel.className = `py-2 px-4 ${labelColor} ${labelWeight}`;
      tdLabel.textContent = (item.label || '').trim();
      tr.appendChild(tdLabel);

      // Value cells for each period
      const vals = item.values || {};
      const periodValues = periods.map(p => vals[p] != null ? vals[p] : null);
      const isPercent = item.unit === 'percent';
      const isShares = item.unit === 'shares';
      const isEPS = item.unit === 'USD/shares';

      for (let i = 0; i < periods.length; i++) {
        const td = document.createElement('td');
        const val = periodValues[i];
        const isMostRecent = i === 0;
        const baseColor = isMostRecent
          ? (cls === 'indent-1' ? 'text-slate-700' : 'text-slate-900')
          : (cls === 'indent-1' ? 'text-slate-500' : 'text-slate-600');
        const weight = isTotal ? 'font-bold' : (isSubtotal ? 'font-semibold' : '');

        if (val == null) {
          td.className = `py-2 px-4 font-mono tabular-nums text-slate-400 ${weight}`;
          td.textContent = '\u2014';
        } else if (isPercent) {
          const pctStr = (val * 100).toFixed(1) + '%';
          const color = val < 0 ? 'text-red-600' : baseColor;
          td.className = `py-2 px-4 font-mono tabular-nums text-right ${color} ${weight} italic text-xs`;
          td.textContent = pctStr;
        } else if (isShares) {
          const sharesStr = (val / 1e6).toFixed(1) + 'M';
          td.className = `py-2 px-4 font-mono tabular-nums ${baseColor} ${weight}`;
          td.textContent = sharesStr;
        } else if (isEPS) {
          const isNeg = val < 0;
          const color = isNeg ? 'text-red-600' : baseColor;
          const epsStr = isNeg ? '($' + Math.abs(val).toFixed(2) + ')' : '$' + val.toFixed(2);
          td.className = `py-2 px-4 font-mono tabular-nums ${color} ${weight}`;
          td.textContent = epsStr;
        } else {
          const isNeg = val < 0;
          const color = isNeg ? 'text-red-600' : baseColor;
          td.className = `py-2 px-4 font-mono tabular-nums ${color} ${weight}`;
          td.textContent = formatCurrency(val);
        }
        tr.appendChild(td);
      }

      // YoY Change cell
      if (hasMultiplePeriods) {
        const td = document.createElement('td');
        const current = periodValues[0];
        const prior = periodValues[1];
        const weight = isTotal ? 'font-bold' : (isSubtotal ? 'font-semibold' : '');

        if (isPercent && current != null && prior != null) {
          // For margin rows, show pp change
          const ppChange = (current - prior) * 100;
          const changeStr = (ppChange >= 0 ? '+' : '') + ppChange.toFixed(1) + 'pp';
          const changeColor = ppChange > 0.1 ? 'text-emerald-600' : (ppChange < -0.1 ? 'text-red-600' : 'text-slate-500');
          td.className = `py-2 px-4 font-mono tabular-nums ${changeColor} ${weight} text-xs`;
          td.textContent = changeStr;
        } else if (current != null && prior != null && prior !== 0) {
          const change = (current - prior) / Math.abs(prior);
          const changeStr = (change >= 0 ? '+' : '') + (change * 100).toFixed(1) + '%';
          const changeColor = change > 0.001 ? 'text-emerald-600' : (change < -0.001 ? 'text-red-600' : 'text-slate-500');
          td.className = `py-2 px-4 font-mono tabular-nums ${changeColor} ${weight}`;
          td.textContent = changeStr;
        } else {
          td.className = `py-2 px-4 font-mono tabular-nums text-slate-400 ${weight}`;
          td.textContent = '\u2014';
        }
        tr.appendChild(td);
      }

      tbody.appendChild(tr);
    }

    table.appendChild(tbody);

    // Replace panel contents
    panelEl.innerHTML = '';
    panelEl.appendChild(table);
  }
}

/**
 * Render derived metrics into #metrics-panel.
 * @param {object} metrics - { profitability, liquidity, leverage, efficiency }
 */
export function renderDerivedMetrics(metrics) {
  if (!metrics) return;

  const panel = document.getElementById('metrics-panel');
  if (!panel) return;

  const categories = [
    { key: 'profitability', title: 'Profitability' },
    { key: 'liquidity', title: 'Liquidity' },
    { key: 'leverage', title: 'Leverage' },
    { key: 'efficiency', title: 'Efficiency' },
  ];

  // Build the container
  let html = `
    <div class="space-y-4">
      <h3 class="text-sm font-semibold text-slate-900 flex items-center gap-2">
        <svg class="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z"/>
        </svg>
        Derived Metrics &amp; Ratios
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
  `;

  for (const { key, title } of categories) {
    const categoryData = metrics[key];
    if (!categoryData) continue;

    html += `
      <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
        <div class="px-4 py-2.5 border-b border-slate-100">
          <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider">${escapeHTML(title)}</h4>
        </div>
        <div class="divide-y divide-slate-50">
    `;

    const entries = Object.entries(categoryData);
    for (const [metricKey, metricData] of entries) {
      const val = metricData != null && typeof metricData === 'object' ? metricData.value : metricData;
      const trend = metricData != null && typeof metricData === 'object' ? metricData.trend : null;

      const formattedValue = autoFormatMetric(metricKey, val);
      const label = humanizeKey(metricKey);

      const arrowSpan = trend
        ? `<span class="trend-${escapeHTML(trend)} text-xs ml-1">${trendArrow(trend)}</span>`
        : '';

      html += `
        <div class="flex items-center justify-between px-4 py-2.5">
          <span class="text-xs text-slate-600">${escapeHTML(label)}</span>
          <div class="flex items-center gap-1">
            <span class="text-xs font-semibold font-mono tabular-nums text-slate-900">${escapeHTML(formattedValue)}</span>
            ${arrowSpan}
          </div>
        </div>
      `;
    }

    html += `
        </div>
      </div>
    `;
  }

  html += `
      </div>
    </div>
  `;

  panel.innerHTML = html;
}

/**
 * Render the AI narrative panel (basic version — PR #7 extends).
 * @param {object} narrative - { summary, sections, risks, outlook }
 */
export function renderNarrative(narrative) {
  if (!narrative) return;

  const panel = document.getElementById('narrative-panel');
  if (!panel) return;

  const sentimentBadge = (sentiment) => {
    const classes = {
      positive: 'sentiment-positive',
      negative: 'sentiment-negative',
      neutral: 'sentiment-neutral',
      mixed: 'sentiment-mixed',
    };
    const labels = {
      positive: 'Positive',
      negative: 'Negative',
      neutral: 'Neutral',
      mixed: 'Mixed',
    };
    const cls = classes[sentiment] || classes.neutral;
    const lbl = labels[sentiment] || 'Neutral';
    return `<span class="inline-flex items-center px-2 py-0.5 text-[11px] font-semibold rounded-full ${cls}">${escapeHTML(lbl)}</span>`;
  };

  // Determine overall sentiment from sections
  const sectionSentiments = (narrative.sections || []).map(s => s.sentiment).filter(Boolean);
  const overallSentiment = sectionSentiments.length > 0 ? sectionSentiments[0] : 'neutral';

  let html = `
    <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
      <div class="flex items-center justify-between px-5 py-3 border-b border-slate-200">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"/>
          </svg>
          <h3 class="text-sm font-semibold text-slate-900">AI Analysis &amp; Narrative</h3>
        </div>
        <div class="flex items-center gap-2">
          ${sentimentBadge(overallSentiment)}
        </div>
      </div>
      <div class="p-5 space-y-4">
        <div class="prose prose-sm max-w-none">
  `;

  // Summary paragraph
  if (narrative.summary) {
    html += `
      <p class="text-sm text-slate-700 leading-relaxed">
        <strong>Executive Summary:</strong> ${escapeHTML(narrative.summary)}
      </p>
    `;
  }

  // Sections
  if (narrative.sections && Array.isArray(narrative.sections)) {
    for (const section of narrative.sections) {
      const badge = section.sentiment ? ' ' + sentimentBadge(section.sentiment) : '';
      html += `
        <div class="mt-3">
          <p class="text-sm text-slate-700 leading-relaxed">
            <strong>${escapeHTML(section.title || '')}${badge}:</strong>
            ${escapeHTML(section.content || '')}
          </p>
        </div>
      `;
    }
  }

  // Risks
  if (narrative.risks && Array.isArray(narrative.risks) && narrative.risks.length > 0) {
    html += `
      <div class="mt-4">
        <p class="text-sm font-semibold text-slate-700 mb-1">Key Risks:</p>
        <ul class="list-disc list-inside space-y-1">
    `;
    for (const risk of narrative.risks) {
      html += `<li class="text-sm text-slate-600 leading-relaxed">${escapeHTML(risk)}</li>`;
    }
    html += `
        </ul>
      </div>
    `;
  }

  // Outlook
  if (narrative.outlook) {
    html += `
      <p class="text-sm text-slate-600 leading-relaxed italic mt-3">
        <strong>Outlook:</strong> ${escapeHTML(narrative.outlook)}
      </p>
    `;
  }

  html += `
        </div>
      </div>
    </div>
  `;

  panel.innerHTML = html;
}

/**
 * Render source attributions and update footer.
 * @param {Array} sources
 */
function renderSources(sources) {
  if (!sources || !Array.isArray(sources)) return;

  // Update footer source count
  const footerCount = document.getElementById('footer-source-count');
  if (footerCount) {
    footerCount.innerHTML = `
      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375"/>
      </svg>
      ${sources.length} source${sources.length !== 1 ? 's' : ''} loaded
    `;
  }

  // Update sidebar source list
  const sourceList = document.getElementById('source-list');
  if (sourceList) {
    if (sources.length === 0) {
      sourceList.innerHTML = '<p class="text-xs text-slate-400 italic py-2 text-center">No data sources loaded</p>';
      return;
    }

    sourceList.innerHTML = '';
    for (const src of sources) {
      const typeColors = {
        sec_filing: 'bg-blue-500',
        uploaded_document: 'bg-emerald-500',
        analyst_input: 'bg-amber-500',
        computed: 'bg-slate-400',
      };
      const reliabilityColors = {
        high: 'bg-emerald-50 text-emerald-600',
        medium: 'bg-amber-50 text-amber-600',
        low: 'bg-red-50 text-red-600',
      };

      const dotColor = typeColors[src.type] || 'bg-slate-400';
      const reliabilityCls = reliabilityColors[src.reliability] || reliabilityColors.medium;
      const reliabilityLabel = src.reliability
        ? src.reliability.charAt(0).toUpperCase() + src.reliability.slice(1)
        : '';

      const item = document.createElement('div');
      item.className = 'flex items-center gap-2 p-2 bg-slate-50 rounded-md text-xs';
      item.innerHTML = `
        <span class="w-1.5 h-1.5 rounded-full ${dotColor} flex-shrink-0"></span>
        <span class="flex-1 truncate text-slate-700">${escapeHTML(src.label || src.filename || 'Unknown')}</span>
        ${reliabilityLabel ? `<span class="px-1.5 py-0.5 text-[10px] font-medium ${reliabilityCls} rounded">${escapeHTML(reliabilityLabel)}</span>` : ''}
      `;
      sourceList.appendChild(item);
    }
  }

  // Populate the source manifest panel (main content area)
  const manifestList = document.getElementById('source-manifest-list');
  if (manifestList) {
    manifestList.innerHTML = '';
    for (const src of sources) {
      const typeLabels = { sec_filing: 'SEC Filing', uploaded_document: 'Upload', analyst_input: 'Analyst', computed: 'Computed' };
      const typeTagClass = { sec_filing: 'source-tag-sec', uploaded_document: 'source-tag-upload', analyst_input: 'source-tag-analyst', computed: 'source-tag-computed' };
      const reliabilityDots = { high: 'bg-emerald-500', medium: 'bg-amber-500', low: 'bg-red-500' };

      const el = document.createElement('div');
      el.className = 'flex items-center gap-3 p-3 bg-slate-50 rounded-lg text-sm';
      el.innerHTML = `
        <span class="source-tag ${typeTagClass[src.type] || 'source-tag-computed'}">${escapeHTML(typeLabels[src.type] || src.type)}</span>
        <div class="flex-1 min-w-0">
          <div class="font-medium text-slate-800 truncate">${escapeHTML(src.label || src.filename || 'Unknown')}</div>
          ${src.date ? `<div class="text-xs text-slate-400 mt-0.5">${escapeHTML(src.date)}</div>` : ''}
        </div>
        <div class="flex items-center gap-1.5">
          <span class="w-1.5 h-1.5 rounded-full ${reliabilityDots[src.reliability] || 'bg-slate-300'}"></span>
          <span class="text-xs text-slate-500">${escapeHTML((src.reliability || 'medium').charAt(0).toUpperCase() + (src.reliability || 'medium').slice(1))}</span>
        </div>
      `;
      manifestList.appendChild(el);
    }
  }
}

/**
 * Update footer data quality indicator.
 * @param {object} dataQuality - { overall_confidence, completeness, warnings, missing_data }
 */
function renderDataQuality(dataQuality) {
  if (!dataQuality) return;

  const footerQuality = document.getElementById('footer-quality');
  if (!footerQuality) return;

  const confidenceColors = {
    high: 'bg-emerald-500',
    medium: 'bg-amber-500',
    low: 'bg-red-500',
  };

  const confidence = dataQuality.overall_confidence || 'medium';
  const dotColor = confidenceColors[confidence] || 'bg-slate-300';
  const label = confidence.charAt(0).toUpperCase() + confidence.slice(1);

  footerQuality.innerHTML = `
    <span class="w-1.5 h-1.5 rounded-full ${dotColor}"></span>
    Data quality: ${escapeHTML(label)}
  `;

  // Populate the data quality detail panel
  const detailPanel = document.getElementById('data-quality-detail');
  if (detailPanel) {
    const completeness = dataQuality.completeness != null ? Math.round(dataQuality.completeness * 100) : null;
    const warnings = dataQuality.warnings || [];
    const missing = dataQuality.missing_data || [];

    detailPanel.innerHTML = `
      <div class="flex items-center gap-3 p-3 rounded-lg ${confidence === 'high' ? 'bg-emerald-50' : confidence === 'low' ? 'bg-red-50' : 'bg-amber-50'}">
        <span class="w-2.5 h-2.5 rounded-full ${dotColor}"></span>
        <div>
          <div class="text-sm font-semibold ${confidence === 'high' ? 'text-emerald-800' : confidence === 'low' ? 'text-red-800' : 'text-amber-800'}">${escapeHTML(label)} Confidence</div>
          ${completeness != null ? `<div class="text-xs text-slate-500 mt-0.5">${completeness}% data completeness</div>` : ''}
        </div>
      </div>
      ${warnings.length > 0 ? `
        <div>
          <div class="text-xs font-semibold text-amber-700 mb-1.5">Warnings</div>
          <ul class="space-y-1">
            ${warnings.map(w => `<li class="text-xs text-slate-600 flex gap-2"><span class="text-amber-500 mt-0.5">&#9888;</span>${escapeHTML(w)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
      ${missing.length > 0 ? `
        <div>
          <div class="text-xs font-semibold text-slate-500 mb-1.5">Missing Data</div>
          <ul class="space-y-1">
            ${missing.map(m => `<li class="text-xs text-slate-500 flex gap-2"><span class="text-slate-400">&#8212;</span>${escapeHTML(m)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    `;
  }
}

// ============================================================
// Tab Renderers — Valuation, Competitors, Management, IR
// ============================================================

/**
 * Render the Valuation tab — multiples, profitability metrics, and narrative.
 */
function renderValuationTab(data) {
  const headlines = data.headline_metrics || [];
  const dm = data.derived_metrics || {};
  const narrative = data.narrative || {};
  const company = data.company || {};

  // Valuation multiples table
  const multiplesEl = document.getElementById('valuation-multiples');
  if (multiplesEl) {
    const valuationMetrics = headlines.filter(m =>
      ['P/E Ratio', 'EV / Revenue', 'EV / EBITDA', 'Market Cap', 'Enterprise Value', 'Stock Price'].includes(m.label)
    );

    let html = `
      <div class="px-5 py-3 border-b border-slate-200">
        <h3 class="text-sm font-semibold text-slate-900">Valuation Summary</h3>
      </div>
      <div class="p-5">
        <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
    `;
    for (const m of valuationMetrics) {
      html += `
        <div class="text-center p-3 bg-slate-50 rounded-lg">
          <div class="text-[10px] font-medium text-slate-400 uppercase tracking-wider">${escapeHTML(m.label)}</div>
          <div class="text-lg font-bold font-mono tabular-nums text-slate-900 mt-1">${escapeHTML(m.formatted)}</div>
        </div>
      `;
    }
    html += '</div></div>';
    multiplesEl.innerHTML = html;
  }

  // Profitability + efficiency metrics
  const metricsEl = document.getElementById('valuation-metrics');
  if (metricsEl) {
    metricsEl.innerHTML = '';
    const cats = [
      { key: 'profitability', title: 'Profitability Metrics' },
      { key: 'efficiency', title: 'Efficiency & Returns' },
    ];
    for (const { key, title } of cats) {
      const catData = dm[key];
      if (!catData) continue;
      let html = `
        <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div class="px-5 py-3 border-b border-slate-100">
            <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider">${escapeHTML(title)}</h4>
          </div>
          <div class="divide-y divide-slate-50">
      `;
      for (const [mk, mv] of Object.entries(catData)) {
        if (!mv) continue;
        const val = typeof mv === 'object' ? mv.value : mv;
        const trend = typeof mv === 'object' ? mv.trend : null;
        html += `
          <div class="flex items-center justify-between px-5 py-3">
            <span class="text-sm text-slate-600">${escapeHTML(humanizeKey(mk))}</span>
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold font-mono tabular-nums text-slate-900">${escapeHTML(autoFormatMetric(mk, val))}</span>
              ${trend ? `<span class="trend-${escapeHTML(trend)} text-xs">${trendArrow(trend)}</span>` : ''}
            </div>
          </div>
        `;
      }
      html += '</div></div>';
      metricsEl.innerHTML += html;
    }
  }

  // Narrative sections about profitability / cash flow
  const narEl = document.getElementById('valuation-narrative');
  if (narEl && narrative.sections) {
    const relevant = narrative.sections.filter(s =>
      /profit|cash|capital|balance|valuation|margin/i.test(s.title)
    );
    if (relevant.length) {
      let html = '';
      for (const section of relevant) {
        const sentCls = section.sentiment === 'positive' ? 'sentiment-positive'
          : section.sentiment === 'negative' ? 'sentiment-negative'
          : section.sentiment === 'mixed' ? 'sentiment-mixed' : 'sentiment-neutral';
        html += `
          <div class="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-semibold text-slate-900">${escapeHTML(section.title)}</h4>
              <span class="inline-flex items-center px-2 py-0.5 text-[11px] font-semibold rounded-full ${sentCls}">
                ${escapeHTML((section.sentiment || 'neutral').charAt(0).toUpperCase() + (section.sentiment || 'neutral').slice(1))}
              </span>
            </div>
            <p class="text-sm text-slate-600 leading-relaxed">${escapeHTML(section.content)}</p>
          </div>
        `;
      }
      narEl.innerHTML = html;
    }
  }
}

/**
 * Render the Competitors tab — comps placeholder + competitive narrative.
 */
function renderCompetitorsTab(data) {
  const narrative = data.narrative || {};
  const company = data.company || {};

  // Public comps table placeholder
  const compsEl = document.getElementById('comps-table');
  if (compsEl) {
    compsEl.innerHTML = `
      <div class="px-5 py-3 border-b border-slate-200">
        <h3 class="text-sm font-semibold text-slate-900">Public Comparable Companies</h3>
      </div>
      <div class="p-8 text-center">
        <svg class="w-10 h-10 text-slate-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605"/>
        </svg>
        <p class="text-sm text-slate-500 font-medium">Comparable companies analysis</p>
        <p class="text-xs text-slate-400 mt-1">Sortable comps table with valuation multiples coming in Phase 5</p>
        <p class="text-xs text-slate-400 mt-0.5">Industry: ${escapeHTML(company.industry || 'N/A')}</p>
      </div>
    `;
  }

  // Competitive narrative sections
  const narEl = document.getElementById('competitors-narrative');
  if (narEl && narrative.sections) {
    const relevant = narrative.sections.filter(s =>
      /compet|market|position|risk|growth|revenue/i.test(s.title)
    );
    if (relevant.length) {
      let html = '';
      for (const section of relevant) {
        const sentCls = section.sentiment === 'positive' ? 'sentiment-positive'
          : section.sentiment === 'negative' ? 'sentiment-negative'
          : section.sentiment === 'mixed' ? 'sentiment-mixed' : 'sentiment-neutral';
        html += `
          <div class="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-semibold text-slate-900">${escapeHTML(section.title)}</h4>
              <span class="inline-flex items-center px-2 py-0.5 text-[11px] font-semibold rounded-full ${sentCls}">
                ${escapeHTML((section.sentiment || 'neutral').charAt(0).toUpperCase() + (section.sentiment || 'neutral').slice(1))}
              </span>
            </div>
            <p class="text-sm text-slate-600 leading-relaxed">${escapeHTML(section.content)}</p>
          </div>
        `;
      }
      narEl.innerHTML = html;
    } else {
      narEl.innerHTML = `
        <div class="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
          <p class="text-sm text-slate-400 italic text-center">No competitive analysis narrative available for this company</p>
        </div>
      `;
    }
  }

  // Risks as competitive threats
  if (narrative.risks?.length) {
    const narEl2 = document.getElementById('competitors-narrative');
    if (narEl2) {
      narEl2.innerHTML += `
        <div class="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
          <h4 class="text-sm font-semibold text-slate-900 mb-3">Competitive Risk Factors</h4>
          <ul class="space-y-2">
            ${narrative.risks.map(r => `
              <li class="flex gap-2 text-sm text-slate-600">
                <span class="text-red-400 mt-0.5 flex-shrink-0">&#9679;</span>
                ${escapeHTML(r)}
              </li>
            `).join('')}
          </ul>
        </div>
      `;
    }
  }
}

/**
 * Render the Management tab — company overview, risks, outlook.
 */
function renderManagementTab(data) {
  const company = data.company || {};
  const narrative = data.narrative || {};
  const dm = data.derived_metrics || {};

  // Company overview card
  const overviewEl = document.getElementById('management-overview');
  if (overviewEl) {
    const liquidity = dm.liquidity || {};
    const leverage = dm.leverage || {};

    let metricsHtml = '';
    const keyMetrics = [
      ['Market Cap', company.market_cap ? formatCurrency(company.market_cap, true) : 'N/A'],
      ['Shares Outstanding', company.shares_outstanding ? formatNumber(company.shares_outstanding / 1e6, 1) + 'M' : 'N/A'],
      ['Current Ratio', liquidity.current_ratio ? formatRatio(liquidity.current_ratio.value) : 'N/A'],
      ['Debt to Equity', leverage.debt_to_equity ? formatRatio(leverage.debt_to_equity.value) : 'N/A'],
    ];
    for (const [label, val] of keyMetrics) {
      metricsHtml += `
        <div class="flex items-center justify-between py-2.5 border-b border-slate-50 last:border-0">
          <span class="text-sm text-slate-500">${escapeHTML(label)}</span>
          <span class="text-sm font-semibold font-mono tabular-nums text-slate-900">${escapeHTML(val)}</span>
        </div>
      `;
    }

    overviewEl.innerHTML = `
      <div class="px-5 py-3 border-b border-slate-200">
        <h3 class="text-sm font-semibold text-slate-900">Company Overview</h3>
      </div>
      <div class="p-5">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Company Details</h4>
            <div class="space-y-2">
              <div class="flex justify-between text-sm"><span class="text-slate-500">Name</span><span class="font-medium text-slate-900">${escapeHTML(company.name || 'N/A')}</span></div>
              <div class="flex justify-between text-sm"><span class="text-slate-500">Ticker</span><span class="font-medium text-slate-900">${escapeHTML(company.ticker || 'N/A')}</span></div>
              <div class="flex justify-between text-sm"><span class="text-slate-500">Exchange</span><span class="font-medium text-slate-900">${escapeHTML(company.exchange || 'N/A')}</span></div>
              <div class="flex justify-between text-sm"><span class="text-slate-500">Sector</span><span class="font-medium text-slate-900">${escapeHTML(company.sector || 'N/A')}</span></div>
              <div class="flex justify-between text-sm"><span class="text-slate-500">Industry</span><span class="font-medium text-slate-900">${escapeHTML(company.industry || 'N/A')}</span></div>
              <div class="flex justify-between text-sm"><span class="text-slate-500">Fiscal Year End</span><span class="font-medium text-slate-900">${escapeHTML(company.fiscal_year_end || 'N/A')}</span></div>
              <div class="flex justify-between text-sm"><span class="text-slate-500">CIK</span><span class="font-medium font-mono text-slate-900">${escapeHTML(company.cik || 'N/A')}</span></div>
            </div>
          </div>
          <div>
            <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Key Financial Metrics</h4>
            ${metricsHtml}
          </div>
        </div>
      </div>
    `;
  }

  // Risk factors
  const risksEl = document.getElementById('management-risks');
  if (risksEl && narrative.risks?.length) {
    risksEl.innerHTML = `
      <div class="px-5 py-3 border-b border-slate-200">
        <h3 class="text-sm font-semibold text-slate-900">Key Risk Factors</h3>
      </div>
      <div class="p-5">
        <ul class="space-y-3">
          ${narrative.risks.map((r, i) => `
            <li class="flex gap-3">
              <span class="flex-shrink-0 w-6 h-6 rounded-full bg-red-50 text-red-600 text-xs font-bold flex items-center justify-center">${i + 1}</span>
              <p class="text-sm text-slate-600 leading-relaxed">${escapeHTML(r)}</p>
            </li>
          `).join('')}
        </ul>
      </div>
    `;
  } else if (risksEl) {
    risksEl.innerHTML = '';
  }

  // Forward outlook
  const outlookEl = document.getElementById('management-outlook');
  if (outlookEl && narrative.outlook) {
    outlookEl.innerHTML = `
      <div class="px-5 py-3 border-b border-slate-200">
        <h3 class="text-sm font-semibold text-slate-900">Forward Outlook</h3>
      </div>
      <div class="p-5">
        <p class="text-sm text-slate-600 leading-relaxed">${escapeHTML(narrative.outlook)}</p>
      </div>
    `;
  } else if (outlookEl) {
    outlookEl.innerHTML = '';
  }
}

/**
 * Render the IR tab — SEC filing links, sources, metadata.
 */
function renderIRTab(data) {
  const sources = data.sources || [];
  const dq = data.data_quality || {};
  const meta = data.metadata || {};
  const company = data.company || {};

  // SEC filing links
  const filingsEl = document.getElementById('ir-filings');
  if (filingsEl) {
    const secSources = sources.filter(s => s.type === 'sec_filing');
    const cik = company.cik || '';
    const edgarUrl = cik ? `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${cik}&type=10-K` : '';

    filingsEl.innerHTML = `
      <div class="px-5 py-3 border-b border-slate-200">
        <h3 class="text-sm font-semibold text-slate-900">SEC Filings</h3>
      </div>
      <div class="p-5">
        ${secSources.length ? secSources.map(s => `
          <div class="flex items-center gap-3 p-3 bg-slate-50 rounded-lg mb-2">
            <span class="source-tag source-tag-sec">SEC Filing</span>
            <div class="flex-1">
              <div class="text-sm font-medium text-slate-800">${escapeHTML(s.label)}</div>
              ${s.date ? `<div class="text-xs text-slate-400 mt-0.5">${escapeHTML(s.date)}</div>` : ''}
            </div>
            ${s.url ? `<a href="${escapeHTML(s.url)}" target="_blank" rel="noopener" class="text-xs text-blue-600 hover:text-blue-800 font-medium">View on EDGAR</a>` : ''}
          </div>
        `).join('') : '<p class="text-sm text-slate-400 italic">No SEC filing sources</p>'}
        ${edgarUrl ? `
          <div class="mt-4 pt-4 border-t border-slate-100">
            <a href="${escapeHTML(edgarUrl)}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 font-medium">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/>
              </svg>
              Browse all ${escapeHTML(company.ticker || '')} filings on SEC EDGAR
            </a>
          </div>
        ` : ''}
      </div>
    `;
  }

  // All sources
  const sourcesEl = document.getElementById('ir-sources');
  if (sourcesEl) {
    const confidenceColors = { high: 'bg-emerald-500', medium: 'bg-amber-500', low: 'bg-red-500' };
    const confidence = dq.overall_confidence || 'medium';
    const completeness = dq.completeness != null ? Math.round(dq.completeness * 100) : null;

    let qualityHtml = `
      <div class="flex items-center gap-3 p-4 rounded-lg ${confidence === 'high' ? 'bg-emerald-50' : confidence === 'low' ? 'bg-red-50' : 'bg-amber-50'}">
        <span class="w-3 h-3 rounded-full ${confidenceColors[confidence] || 'bg-slate-300'}"></span>
        <div>
          <div class="text-sm font-semibold ${confidence === 'high' ? 'text-emerald-800' : confidence === 'low' ? 'text-red-800' : 'text-amber-800'}">
            ${escapeHTML(confidence.charAt(0).toUpperCase() + confidence.slice(1))} Confidence
          </div>
          ${completeness != null ? `<div class="text-xs text-slate-500 mt-0.5">${completeness}% data completeness</div>` : ''}
        </div>
      </div>
    `;

    if (dq.warnings?.length) {
      qualityHtml += `
        <div class="mt-4">
          <h5 class="text-xs font-semibold text-amber-700 mb-2">Warnings</h5>
          <ul class="space-y-1.5">
            ${dq.warnings.map(w => `<li class="text-xs text-slate-600 flex gap-2"><span class="text-amber-500">&#9888;</span>${escapeHTML(w)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    if (dq.missing_data?.length) {
      qualityHtml += `
        <div class="mt-4">
          <h5 class="text-xs font-semibold text-slate-500 mb-2">Missing Data</h5>
          <ul class="space-y-1.5">
            ${dq.missing_data.map(m => `<li class="text-xs text-slate-500 flex gap-2"><span class="text-slate-400">&#8212;</span>${escapeHTML(m)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    sourcesEl.innerHTML = `
      <div class="px-5 py-3 border-b border-slate-200">
        <h3 class="text-sm font-semibold text-slate-900">Data Sources & Quality</h3>
      </div>
      <div class="p-5">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Sources</h4>
            <div class="space-y-2">
              ${sources.map(s => {
                const typeLabels = { sec_filing: 'SEC Filing', uploaded_document: 'Upload', analyst_input: 'Analyst', computed: 'Computed' };
                const typeTagClass = { sec_filing: 'source-tag-sec', uploaded_document: 'source-tag-upload', analyst_input: 'source-tag-analyst', computed: 'source-tag-computed' };
                return `
                  <div class="flex items-center gap-3 p-3 bg-slate-50 rounded-lg text-sm">
                    <span class="source-tag ${typeTagClass[s.type] || 'source-tag-computed'}">${escapeHTML(typeLabels[s.type] || s.type)}</span>
                    <span class="flex-1 text-slate-700 truncate">${escapeHTML(s.label || 'Unknown')}</span>
                    <span class="text-xs text-slate-400">${escapeHTML(s.reliability || '')}</span>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
          <div>
            <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Quality Assessment</h4>
            ${qualityHtml}
          </div>
        </div>
      </div>
    `;
  }

  // Analysis metadata
  const metaEl = document.getElementById('ir-metadata');
  if (metaEl) {
    metaEl.innerHTML = `
      <div class="px-5 py-3 border-b border-slate-200">
        <h3 class="text-sm font-semibold text-slate-900">Analysis Metadata</h3>
      </div>
      <div class="p-5">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div class="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Analysis ID</div>
            <div class="text-sm font-mono text-slate-900 mt-1">${escapeHTML(meta.analysis_id || 'N/A')}</div>
          </div>
          <div>
            <div class="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Timestamp</div>
            <div class="text-sm font-mono text-slate-900 mt-1">${escapeHTML(meta.timestamp ? new Date(meta.timestamp).toLocaleDateString() : 'N/A')}</div>
          </div>
          <div>
            <div class="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Model</div>
            <div class="text-sm font-mono text-slate-900 mt-1">${escapeHTML(meta.model || 'N/A')}</div>
          </div>
          <div>
            <div class="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Schema Version</div>
            <div class="text-sm font-mono text-slate-900 mt-1">${escapeHTML(meta.prompt_version || 'N/A')}</div>
          </div>
        </div>
      </div>
    `;
  }
}

// ============================================================
// Main Entry Point
// ============================================================

/**
 * Render a complete AnalysisJSON result into the DOM.
 * @param {object} analysisJSON - Full AnalysisJSON object
 */
export function renderAnalysis(analysisJSON) {
  if (!analysisJSON) return;

  // Show analysis content, hide empty state
  const emptyState = document.getElementById('empty-state');
  const analysisContent = document.getElementById('analysis-content');
  if (emptyState) emptyState.classList.add('hidden');
  if (analysisContent) analysisContent.classList.remove('hidden');

  // Render each section
  renderCompanyHeader(analysisJSON.company);
  renderHeadlineMetrics(analysisJSON.headline_metrics);
  renderKPIs(analysisJSON.kpis);
  renderFinancialStatements(analysisJSON.financial_statements);
  renderDerivedMetrics(analysisJSON.derived_metrics);
  renderNarrative(analysisJSON.narrative);
  renderSources(analysisJSON.sources);
  renderDataQuality(analysisJSON.data_quality);

  // Render tab-specific content
  renderValuationTab(analysisJSON);
  renderCompetitorsTab(analysisJSON);
  renderManagementTab(analysisJSON);
  renderIRTab(analysisJSON);

  // Update analysis status badge
  const statusEl = document.getElementById('analysis-status');
  if (statusEl) {
    statusEl.innerHTML = `
      <span class="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>
      Analysis Complete
    `;
    statusEl.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-emerald-50 text-emerald-700 rounded-full';
  }

  // Update footer timestamp
  const footerTs = document.getElementById('footer-timestamp');
  if (footerTs) {
    const now = new Date();
    footerTs.textContent = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      + ' ' + now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  }

  // Dispatch event for other modules
  document.dispatchEvent(new CustomEvent('analysis-rendered', { detail: analysisJSON }));
}
