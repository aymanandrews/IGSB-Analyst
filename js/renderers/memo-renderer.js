/**
 * Folio — Investment Memo Renderer
 * Renders a professional investment memo formatted as a long-only hedge fund
 * analyst or PM would present to an investment committee.
 *
 * Sections:
 *  1. Header bar (rating, price target, conviction)
 *  2. Executive snapshot (thesis bullets + metrics grid)
 *  3. Thesis pillars with supporting metrics
 *  4. Financial summary (compact 5-year table)
 *  5. Valuation comps + scenario analysis
 *  6. Catalysts timeline
 *  7. Risk-mitigant pairs
 *  8. Final recommendation
 */

// Note: This module uses its own formatting helpers (pctStr, numStr, fmtCell)
// to keep it self-contained. For shared formatters, see ../renderer.js.

// ============================================================
// XSS-safe text escaping
// ============================================================
const _esc = document.createElement('div');
function esc(str) {
  if (str == null) return '';
  _esc.textContent = String(str);
  return _esc.innerHTML;
}

// ============================================================
// Color / style helpers
// ============================================================

const RATING_COLORS = {
  'Strong Buy': { bg: 'bg-emerald-600', text: 'text-white', border: 'border-emerald-600' },
  'Buy':        { bg: 'bg-emerald-500', text: 'text-white', border: 'border-emerald-500' },
  'Hold':       { bg: 'bg-amber-500',   text: 'text-white', border: 'border-amber-500' },
  'Sell':       { bg: 'bg-red-500',      text: 'text-white', border: 'border-red-500' },
  'Strong Sell':{ bg: 'bg-red-700',      text: 'text-white', border: 'border-red-700' },
};

const CONVICTION_COLORS = {
  'High':   'text-emerald-700 bg-emerald-50 border-emerald-200',
  'Medium': 'text-amber-700 bg-amber-50 border-amber-200',
  'Low':    'text-slate-600 bg-slate-50 border-slate-200',
};

const SEVERITY_COLORS = {
  'High':   'bg-red-100 text-red-700',
  'Medium': 'bg-amber-100 text-amber-700',
  'Low':    'bg-slate-100 text-slate-600',
};

function trendArrow(trend) {
  if (trend === 'up') return '<span class="text-emerald-600">&#9650;</span>';
  if (trend === 'down') return '<span class="text-red-600">&#9660;</span>';
  return '<span class="text-slate-400">&#9644;</span>';
}

function changeColor(val) {
  if (val == null) return 'text-slate-500';
  return val >= 0 ? 'text-emerald-700' : 'text-red-700';
}

function pctStr(val, decimals = 1) {
  if (val == null || isNaN(val)) return '\u2014';
  return (val * 100).toFixed(decimals) + '%';
}

function numStr(val, decimals = 1) {
  if (val == null || isNaN(val)) return '\u2014';
  return val.toFixed(decimals);
}

// ============================================================
// Main Entry Point
// ============================================================

/**
 * Render the full investment memo tab.
 * @param {object} data — Full AnalysisJSON object
 */
export function renderMemoTab(data) {
  const memo = data.investment_memo || {};
  const company = data.company || {};
  const kpis = data.kpis || [];
  const metrics = data.derived_metrics || {};
  const narrative = data.narrative || {};
  const headline = data.headline_metrics || [];
  const stmts = data.financial_statements || {};

  renderMemoHeader(memo, company, headline);
  renderExecutiveSnapshot(memo, company, kpis, metrics, narrative);
  renderThesisPillars(memo, narrative);
  renderFinancialSummary(stmts, company);
  renderValuationScenario(memo, headline, data);
  renderCatalysts(memo);
  renderRiskMitigants(memo, narrative);
  renderRecommendation(memo, company, headline);
}


// ============================================================
// 1. Header Bar — Rating, Price, Target, Upside, Conviction
// ============================================================

function renderMemoHeader(memo, company, headline) {
  const el = document.getElementById('memo-header');
  if (!el) return;

  const rec = memo.recommendation || {};
  const rating = rec.rating || 'Hold';
  const rc = RATING_COLORS[rating] || RATING_COLORS['Hold'];
  const price = company.stock_price;
  const target = rec.price_target;
  const upside = (price && target) ? ((target - price) / price) : null;
  const conviction = rec.conviction || 'Medium';
  const cc = CONVICTION_COLORS[conviction] || CONVICTION_COLORS['Medium'];
  const timeHorizon = rec.time_horizon || '12 months';

  el.innerHTML = `
    <div class="flex flex-wrap items-center gap-4 md:gap-6 px-6 py-4 bg-white border-b border-slate-200">
      <!-- Rating badge -->
      <div class="flex items-center gap-3">
        <span class="px-3 py-1.5 text-sm font-bold rounded-md ${rc.bg} ${rc.text}">${esc(rating)}</span>
        <div class="flex items-center gap-1 px-2 py-1 text-xs font-medium border rounded ${cc}">${esc(conviction)} Conviction</div>
      </div>

      <!-- Price / Target / Upside -->
      <div class="flex items-center gap-6 text-sm">
        <div>
          <div class="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Current</div>
          <div class="text-lg font-bold text-slate-900 tabular-nums">${price != null ? '$' + numStr(price, 2) : '\u2014'}</div>
        </div>
        <div>
          <div class="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Target</div>
          <div class="text-lg font-bold text-blue-700 tabular-nums">${target != null ? '$' + numStr(target, 2) : '\u2014'}</div>
        </div>
        <div>
          <div class="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Upside</div>
          <div class="text-lg font-bold tabular-nums ${upside != null && upside >= 0 ? 'text-emerald-700' : 'text-red-700'}">
            ${upside != null ? (upside >= 0 ? '+' : '') + (upside * 100).toFixed(1) + '%' : '\u2014'}
          </div>
        </div>
      </div>

      <!-- Time horizon -->
      <div class="ml-auto text-xs text-slate-500">
        <span class="font-medium">Horizon:</span> ${esc(timeHorizon)}
      </div>
    </div>
  `;
}


// ============================================================
// 2. Executive Snapshot — Thesis Bullets + Metrics Grid
// ============================================================

function renderExecutiveSnapshot(memo, company, kpis, metrics, narrative) {
  const el = document.getElementById('memo-executive');
  if (!el) return;

  const summary = memo.executive_summary || narrative.summary || '';
  const thesisBullets = memo.thesis_bullets || [];
  const oneLiner = memo.company_description || `${company.name || ''} — ${company.industry || ''}`;

  // Build metrics grid from KPIs
  const metricItems = [];
  const revKpi = kpis.find(k => k.label === 'Revenue');
  if (revKpi) metricItems.push({ label: 'Revenue', value: revKpi.formatted, change: revKpi.change_formatted, trend: revKpi.trend });

  const gmKpi = kpis.find(k => k.label === 'Gross Margin');
  if (gmKpi) metricItems.push({ label: 'Gross Margin', value: gmKpi.formatted, change: gmKpi.change_formatted, trend: gmKpi.trend });

  const fcfKpi = kpis.find(k => k.label === 'FCF Margin');
  if (fcfKpi) metricItems.push({ label: 'FCF Margin', value: fcfKpi.formatted, change: fcfKpi.change_formatted, trend: fcfKpi.trend });

  const r40Kpi = kpis.find(k => k.label === 'Rule of 40');
  if (r40Kpi) metricItems.push({ label: 'Rule of 40', value: r40Kpi.formatted, change: r40Kpi.change_formatted, trend: r40Kpi.trend });

  const effMetrics = metrics.efficiency || {};
  if (effMetrics.fcf_yield?.value != null) metricItems.push({ label: 'FCF Yield', value: pctStr(effMetrics.fcf_yield.value), trend: effMetrics.fcf_yield.trend });

  const profMetrics = metrics.profitability || {};
  if (profMetrics.roic?.value != null) metricItems.push({ label: 'ROIC', value: pctStr(profMetrics.roic.value), trend: profMetrics.roic.trend });

  el.innerHTML = `
    <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
      <div class="px-6 py-4 border-b border-slate-100">
        <div class="text-xs text-slate-500 mb-1">${esc(oneLiner)}</div>
        <h3 class="text-base font-bold text-slate-900">Executive Summary</h3>
      </div>
      <div class="p-6">
        <!-- Summary -->
        <p class="text-sm text-slate-700 leading-relaxed mb-5">${esc(summary)}</p>

        ${thesisBullets.length ? `
          <!-- Thesis Bullets -->
          <div class="mb-5">
            <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Investment Thesis</h4>
            <div class="space-y-2">
              ${thesisBullets.map((b, i) => `
                <div class="flex gap-3 items-start">
                  <span class="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">${i + 1}</span>
                  <p class="text-sm text-slate-700">${esc(b)}</p>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Metrics Grid -->
        ${metricItems.length ? `
          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            ${metricItems.map(m => `
              <div class="bg-slate-50 rounded-lg p-3 text-center">
                <div class="text-[10px] uppercase tracking-wider text-slate-400 font-medium mb-1">${esc(m.label)}</div>
                <div class="text-base font-bold text-slate-900 tabular-nums">${esc(m.value)}</div>
                ${m.change ? `<div class="text-xs ${changeColor(parseFloat(m.change))} tabular-nums mt-0.5">${esc(m.change)}</div>` :
                  m.trend ? `<div class="text-xs mt-0.5">${trendArrow(m.trend)}</div>` : ''}
              </div>
            `).join('')}
          </div>
        ` : ''}
      </div>
    </div>
  `;
}


// ============================================================
// 3. Thesis Pillars
// ============================================================

function renderThesisPillars(memo, narrative) {
  const el = document.getElementById('memo-thesis');
  if (!el) return;

  const pillars = memo.thesis_pillars || [];

  // If no explicit pillars, derive from narrative sections
  const items = pillars.length ? pillars : (narrative.sections || []).slice(0, 5).map(s => ({
    title: s.title,
    description: s.content,
    sentiment: s.sentiment,
    metric: null,
    metric_label: null,
  }));

  if (!items.length) {
    el.innerHTML = '';
    return;
  }

  el.innerHTML = `
    <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
      <div class="px-6 py-4 border-b border-slate-100">
        <h3 class="text-base font-bold text-slate-900">Thesis Pillars</h3>
      </div>
      <div class="p-6 space-y-4">
        ${items.map((p, i) => {
          const sentColor = p.sentiment === 'positive' ? 'border-l-emerald-500' :
                            p.sentiment === 'negative' ? 'border-l-red-500' :
                            p.sentiment === 'mixed' ? 'border-l-amber-500' : 'border-l-blue-500';
          return `
            <div class="border-l-4 ${sentColor} pl-4 py-2">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-bold text-slate-400">#${i + 1}</span>
                <h4 class="text-sm font-semibold text-slate-900">${esc(p.title)}</h4>
                ${p.metric != null ? `<span class="ml-auto text-sm font-bold tabular-nums text-blue-700">${esc(p.metric_label || '')}: ${esc(String(p.metric))}</span>` : ''}
              </div>
              <p class="text-sm text-slate-600 leading-relaxed">${esc(p.description)}</p>
            </div>
          `;
        }).join('')}
      </div>
    </div>
  `;
}


// ============================================================
// 4. Financial Summary — Compact 5-Year Table
// ============================================================

function renderFinancialSummary(stmts, company) {
  const el = document.getElementById('memo-financials');
  if (!el) return;

  const income = stmts.income_statement || {};
  const cashflow = stmts.cash_flow_statement || {};

  // Gather years from revenue line items
  const revLine = income.Revenue || income.revenue || income['Total Revenue'] || {};
  const years = Object.keys(revLine).filter(k => /^FY|^20/.test(k)).sort();

  if (!years.length) {
    el.innerHTML = '<div class="bg-white rounded-lg border border-slate-200 shadow-sm p-6"><p class="text-sm text-slate-400 italic">Financial data not available for summary table.</p></div>';
    return;
  }

  // Helper to get a value from a statement
  function getVal(statement, ...keys) {
    for (const k of keys) {
      if (statement[k]) return statement[k];
    }
    return {};
  }

  const rows = [
    { label: 'Revenue', data: getVal(income, 'Revenue', 'revenue', 'Total Revenue'), format: 'currency' },
    { label: 'Revenue Growth', compute: true, format: 'pct' },
    { label: 'Gross Profit', data: getVal(income, 'Gross Profit', 'gross_profit'), format: 'currency' },
    { label: 'Gross Margin', compute: true, format: 'pct' },
    { label: 'Operating Income', data: getVal(income, 'Operating Income', 'operating_income'), format: 'currency' },
    { label: 'Op Margin', compute: true, format: 'pct' },
    { label: 'EBITDA', data: getVal(income, 'EBITDA', 'ebitda'), format: 'currency' },
    { label: 'Net Income', data: getVal(income, 'Net Income', 'net_income'), format: 'currency' },
    { label: 'Free Cash Flow', data: getVal(cashflow, 'Free Cash Flow', 'free_cash_flow', 'FCF'), format: 'currency' },
    { label: 'FCF Margin', compute: true, format: 'pct' },
  ];

  // Precompute revenue array for derived rows
  const revData = rows[0].data;

  function cellVal(row, year, yearIdx) {
    if (row.label === 'Revenue Growth') {
      const currRev = revData[year];
      const prevRev = yearIdx > 0 ? revData[years[yearIdx - 1]] : null;
      if (currRev != null && prevRev != null && prevRev !== 0) return (currRev - prevRev) / Math.abs(prevRev);
      return null;
    }
    if (row.label === 'Gross Margin') {
      const gp = rows[2].data[year];
      const rev = revData[year];
      if (gp != null && rev != null && rev !== 0) return gp / rev;
      return null;
    }
    if (row.label === 'Op Margin') {
      const oi = rows[4].data[year];
      const rev = revData[year];
      if (oi != null && rev != null && rev !== 0) return oi / rev;
      return null;
    }
    if (row.label === 'FCF Margin') {
      const fcf = rows[8].data[year];
      const rev = revData[year];
      if (fcf != null && rev != null && rev !== 0) return fcf / rev;
      return null;
    }
    if (row.data) return row.data[year] ?? null;
    return null;
  }

  function fmtCell(val, format) {
    if (val == null) return '<span class="text-slate-300">\u2014</span>';
    if (format === 'pct') {
      const p = (val * 100).toFixed(1) + '%';
      const color = val >= 0 ? 'text-emerald-700' : 'text-red-700';
      return `<span class="${color}">${val > 0 ? '+' : ''}${p}</span>`;
    }
    // currency — show in millions
    const inM = val / 1e6;
    const neg = val < 0;
    const abs = Math.abs(inM);
    const str = abs >= 1000 ? '$' + (abs / 1000).toFixed(1) + 'B' : '$' + abs.toFixed(0) + 'M';
    return neg ? `<span class="text-red-700">(${str})</span>` : str;
  }

  const isMarginRow = (label) => /Growth|Margin/i.test(label);

  el.innerHTML = `
    <div class="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
      <div class="px-6 py-4 border-b border-slate-100">
        <h3 class="text-base font-bold text-slate-900">Financial Summary</h3>
        <p class="text-xs text-slate-400 mt-0.5">USD in millions unless noted</p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-slate-50 border-b border-slate-200">
              <th class="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider min-w-[160px]">Metric</th>
              ${years.map(y => `<th class="text-right px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider tabular-nums">${esc(y)}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${rows.map((row, ri) => {
              const isMargin = isMarginRow(row.label);
              const rowClass = isMargin ? 'bg-slate-50/50 text-xs italic' : (ri % 2 === 0 ? '' : 'bg-slate-50/30');
              return `
                <tr class="${rowClass} border-b border-slate-100/60">
                  <td class="px-4 py-2 font-medium ${isMargin ? 'text-slate-500 pl-8' : 'text-slate-800'}">${esc(row.label)}</td>
                  ${years.map((y, yi) => {
                    const val = cellVal(row, y, yi);
                    return `<td class="text-right px-4 py-2 tabular-nums">${fmtCell(val, row.format)}</td>`;
                  }).join('')}
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}


// ============================================================
// 5. Valuation & Scenario Analysis
// ============================================================

function renderValuationScenario(memo, headline, data) {
  const el = document.getElementById('memo-valuation');
  if (!el) return;

  const scenarios = memo.scenario_analysis || {};
  const hasScenariosData = scenarios.bull || scenarios.base || scenarios.bear;

  // Valuation multiples from headline
  const multiples = headline.filter(h => h.type === 'ratio');

  // Scenario cards
  const scenarioOrder = ['bull', 'base', 'bear'];
  const scenarioConfig = {
    bull: { label: 'Bull Case', color: 'border-emerald-500 bg-emerald-50/30', icon: '&#9650;', textColor: 'text-emerald-700' },
    base: { label: 'Base Case', color: 'border-blue-500 bg-blue-50/30', icon: '&#9644;', textColor: 'text-blue-700' },
    bear: { label: 'Bear Case', color: 'border-red-500 bg-red-50/30', icon: '&#9660;', textColor: 'text-red-700' },
  };

  el.innerHTML = `
    <div class="space-y-6">
      <!-- Valuation Multiples -->
      ${multiples.length ? `
        <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div class="px-6 py-4 border-b border-slate-100">
            <h3 class="text-base font-bold text-slate-900">Current Valuation</h3>
          </div>
          <div class="p-6">
            <div class="grid grid-cols-2 md:grid-cols-${Math.min(multiples.length, 4)} gap-4">
              ${multiples.map(m => `
                <div class="text-center p-4 bg-slate-50 rounded-lg">
                  <div class="text-[10px] uppercase tracking-wider text-slate-400 font-medium mb-1">${esc(m.label)}</div>
                  <div class="text-xl font-bold text-slate-900 tabular-nums">${esc(m.formatted)}</div>
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      ` : ''}

      <!-- Scenario Analysis -->
      ${hasScenariosData ? `
        <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div class="px-6 py-4 border-b border-slate-100">
            <h3 class="text-base font-bold text-slate-900">Scenario Analysis</h3>
          </div>
          <div class="p-6">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              ${scenarioOrder.filter(k => scenarios[k]).map(k => {
                const s = scenarios[k];
                const cfg = scenarioConfig[k];
                const price = data.company?.stock_price;
                const target = s.price_target;
                const upside = (price && target) ? ((target - price) / price) : null;
                return `
                  <div class="border-t-4 ${cfg.color} rounded-lg p-5">
                    <div class="flex items-center gap-2 mb-3">
                      <span class="${cfg.textColor} text-sm">${cfg.icon}</span>
                      <h4 class="text-sm font-bold ${cfg.textColor}">${esc(cfg.label)}</h4>
                      ${target != null ? `<span class="ml-auto text-base font-bold tabular-nums ${cfg.textColor}">$${numStr(target, 0)}</span>` : ''}
                    </div>
                    ${upside != null ? `<div class="text-xs ${cfg.textColor} font-semibold mb-2 tabular-nums">${upside >= 0 ? '+' : ''}${(upside * 100).toFixed(0)}% from current</div>` : ''}
                    ${s.thesis ? `<p class="text-sm text-slate-600 mb-3">${esc(s.thesis)}</p>` : ''}
                    ${s.assumptions?.length ? `
                      <div class="text-xs text-slate-500 space-y-1">
                        ${s.assumptions.map(a => `<div class="flex gap-1.5"><span class="text-slate-400">&bull;</span>${esc(a)}</div>`).join('')}
                      </div>
                    ` : ''}
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        </div>
      ` : `
        <div class="bg-white rounded-lg border border-slate-200 shadow-sm p-6">
          <h3 class="text-base font-bold text-slate-900 mb-2">Scenario Analysis</h3>
          <p class="text-sm text-slate-400 italic">Scenario data will be available after memo generation.</p>
        </div>
      `}
    </div>
  `;
}


// ============================================================
// 6. Catalysts Timeline
// ============================================================

function renderCatalysts(memo) {
  const el = document.getElementById('memo-catalysts');
  if (!el) return;

  const catalysts = memo.catalysts || [];
  if (!catalysts.length) {
    el.innerHTML = '';
    return;
  }

  el.innerHTML = `
    <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
      <div class="px-6 py-4 border-b border-slate-100">
        <h3 class="text-base font-bold text-slate-900">Catalysts & Upcoming Events</h3>
      </div>
      <div class="p-6">
        <div class="relative">
          <!-- Timeline line -->
          <div class="absolute left-4 top-0 bottom-0 w-px bg-slate-200"></div>

          <div class="space-y-4">
            ${catalysts.map(c => {
              const typeColors = {
                'earnings': 'bg-blue-500',
                'product': 'bg-purple-500',
                'macro': 'bg-amber-500',
                'regulatory': 'bg-red-500',
                'M&A': 'bg-emerald-500',
              };
              const dotColor = typeColors[c.type] || 'bg-slate-400';
              return `
                <div class="flex gap-4 relative">
                  <div class="flex-shrink-0 w-8 h-8 rounded-full ${dotColor} flex items-center justify-center z-10">
                    <span class="w-2 h-2 bg-white rounded-full"></span>
                  </div>
                  <div class="flex-1 pb-2">
                    <div class="flex items-center gap-2 mb-0.5">
                      <span class="text-xs text-slate-400 tabular-nums">${esc(c.date || c.timeframe || '')}</span>
                      ${c.type ? `<span class="text-[10px] uppercase tracking-wider font-medium text-slate-500">${esc(c.type)}</span>` : ''}
                    </div>
                    <h4 class="text-sm font-semibold text-slate-800">${esc(c.title || c.event || '')}</h4>
                    ${c.description ? `<p class="text-sm text-slate-500 mt-0.5">${esc(c.description)}</p>` : ''}
                    ${c.impact ? `<p class="text-xs text-blue-600 mt-1 font-medium">Impact: ${esc(c.impact)}</p>` : ''}
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      </div>
    </div>
  `;
}


// ============================================================
// 7. Risk-Mitigant Pairs
// ============================================================

function renderRiskMitigants(memo, narrative) {
  const el = document.getElementById('memo-risks');
  if (!el) return;

  const pairs = memo.risk_mitigant_pairs || [];
  const risksList = narrative.risks || [];

  // If we have structured pairs, use them
  if (pairs.length) {
    el.innerHTML = `
      <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
        <div class="px-6 py-4 border-b border-slate-100">
          <h3 class="text-base font-bold text-slate-900">Risk-Mitigant Analysis</h3>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-slate-50 border-b border-slate-200">
                <th class="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider w-12">Sev.</th>
                <th class="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Risk</th>
                <th class="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Mitigant</th>
              </tr>
            </thead>
            <tbody>
              ${pairs.map((p, i) => {
                const sc = SEVERITY_COLORS[p.severity] || SEVERITY_COLORS['Medium'];
                return `
                  <tr class="${i % 2 ? 'bg-slate-50/30' : ''} border-b border-slate-100/60">
                    <td class="px-4 py-3"><span class="text-xs font-bold px-2 py-0.5 rounded ${sc}">${esc(p.severity || 'Med')}</span></td>
                    <td class="px-4 py-3 text-slate-800">${esc(p.risk)}</td>
                    <td class="px-4 py-3 text-slate-600">${esc(p.mitigant)}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else if (risksList.length) {
    // Fallback: show risks from narrative
    el.innerHTML = `
      <div class="bg-white rounded-lg border border-slate-200 shadow-sm">
        <div class="px-6 py-4 border-b border-slate-100">
          <h3 class="text-base font-bold text-slate-900">Key Risks</h3>
        </div>
        <div class="p-6">
          <div class="space-y-3">
            ${risksList.map((r, i) => `
              <div class="flex gap-3 items-start">
                <span class="flex-shrink-0 w-5 h-5 rounded bg-red-100 text-red-600 text-xs font-bold flex items-center justify-center mt-0.5">${i + 1}</span>
                <p class="text-sm text-slate-700">${esc(r)}</p>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  } else {
    el.innerHTML = '';
  }
}


// ============================================================
// 8. Final Recommendation Box
// ============================================================

function renderRecommendation(memo, company, headline) {
  const el = document.getElementById('memo-recommendation');
  if (!el) return;

  const rec = memo.recommendation || {};
  if (!rec.rating) {
    el.innerHTML = '';
    return;
  }

  const rating = rec.rating;
  const rc = RATING_COLORS[rating] || RATING_COLORS['Hold'];
  const price = company.stock_price;
  const target = rec.price_target;
  const upside = (price && target) ? ((target - price) / price) : null;
  const conviction = rec.conviction || 'Medium';
  const timeHorizon = rec.time_horizon || '12 months';
  const positionSize = rec.position_size || null;
  const monitorMetrics = rec.monitor_metrics || [];

  el.innerHTML = `
    <div class="bg-white rounded-lg border-2 ${rc.border} shadow-sm overflow-hidden">
      <div class="px-6 py-4 ${rc.bg}">
        <h3 class="text-base font-bold ${rc.text}">Recommendation: ${esc(rating)}</h3>
      </div>
      <div class="p-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div class="text-center">
            <div class="text-[10px] uppercase tracking-wider text-slate-400 font-medium mb-1">Target Price</div>
            <div class="text-lg font-bold text-blue-700 tabular-nums">${target != null ? '$' + numStr(target, 2) : '\u2014'}</div>
          </div>
          <div class="text-center">
            <div class="text-[10px] uppercase tracking-wider text-slate-400 font-medium mb-1">Upside</div>
            <div class="text-lg font-bold tabular-nums ${upside != null && upside >= 0 ? 'text-emerald-700' : 'text-red-700'}">
              ${upside != null ? (upside >= 0 ? '+' : '') + (upside * 100).toFixed(1) + '%' : '\u2014'}
            </div>
          </div>
          <div class="text-center">
            <div class="text-[10px] uppercase tracking-wider text-slate-400 font-medium mb-1">Conviction</div>
            <div class="text-lg font-bold text-slate-900">${esc(conviction)}</div>
          </div>
          <div class="text-center">
            <div class="text-[10px] uppercase tracking-wider text-slate-400 font-medium mb-1">Time Horizon</div>
            <div class="text-lg font-bold text-slate-900">${esc(timeHorizon)}</div>
          </div>
        </div>

        ${positionSize ? `
          <div class="p-3 bg-blue-50 rounded-lg text-sm text-blue-800 mb-4">
            <span class="font-semibold">Position Sizing:</span> ${esc(positionSize)}
          </div>
        ` : ''}

        ${monitorMetrics.length ? `
          <div>
            <h4 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Key Metrics to Monitor</h4>
            <div class="flex flex-wrap gap-2">
              ${monitorMetrics.map(m => `<span class="px-2.5 py-1 text-xs font-medium bg-slate-100 text-slate-700 rounded-full">${esc(m)}</span>`).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    </div>
  `;
}
