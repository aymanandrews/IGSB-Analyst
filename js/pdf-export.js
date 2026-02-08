/**
 * Folio — PDF Report Generator (pdfmake)
 * Generates professional equity research PDFs from AnalysisJSON data.
 */

// pdfmake is loaded globally via CDN <script> tags

// ---- Color palette (matches CSS custom properties) ----
const COLORS = {
  primary: '#1971C2',
  positive: '#0CA678',
  negative: '#E03131',
  textPrimary: '#0f172a',
  textSecondary: '#334155',
  textMuted: '#64748b',
  border: '#e2e8f0',
  borderSubtle: '#f1f5f9',
  bgLight: '#f8fafc',
  bgCard: '#ffffff',
};

// ---- Number formatting helpers ----

function fmtCurrency(val) {
  if (val == null || isNaN(val)) return '—';
  const abs = Math.abs(val);
  const neg = val < 0;
  let str;
  if (abs >= 1e9) str = `$${(abs / 1e9).toFixed(2)}B`;
  else if (abs >= 1e6) str = `$${(abs / 1e6).toFixed(1)}M`;
  else if (abs >= 1e3) str = `$${(abs / 1e3).toFixed(0)}K`;
  else str = `$${abs.toFixed(0)}`;
  return neg ? `(${str})` : str;
}

function fmtPercent(val) {
  if (val == null || isNaN(val)) return '—';
  return `${(val * 100).toFixed(1)}%`;
}

function fmtNumber(val, unit) {
  if (val == null || isNaN(val)) return '—';
  if (unit === 'percent') return fmtPercent(val);
  if (unit === 'USD') return fmtCurrency(val);
  if (unit === 'ratio') return `${val.toFixed(1)}x`;
  // Fallback: large numbers get abbreviated
  const abs = Math.abs(val);
  if (abs >= 1e9) return `${(val / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(val / 1e6).toFixed(1)}M`;
  return val.toLocaleString();
}

function fmtStatementValue(val, unit) {
  if (val == null || isNaN(val)) return { text: '—', color: COLORS.textMuted, italics: true };
  if (unit === 'percent') {
    return { text: fmtPercent(val), color: COLORS.textMuted, italics: true };
  }
  // USD values: accounting format — negatives in parens, red
  const neg = val < 0;
  const abs = Math.abs(val);
  let str;
  if (abs >= 1e9) str = `${(abs / 1e9).toFixed(2)}`;
  else if (abs >= 1e6) str = `${(abs / 1e6).toFixed(1)}`;
  else if (abs >= 1e3) str = `${(abs / 1e3).toFixed(1)}`;
  else str = abs.toFixed(0);
  const text = neg ? `(${str})` : str;
  return { text, color: neg ? COLORS.negative : COLORS.textPrimary };
}

function formatDate() {
  return new Date().toISOString().split('T')[0];
}

function formatDateReadable() {
  return new Date().toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  });
}

// ---- Detect row types for styling ----
const TOTAL_KEYWORDS = ['total assets', 'total liabilities', 'total stockholders', 'total equity', 'net income', 'net change in cash'];
const SUBTOTAL_KEYWORDS = ['gross profit', 'operating income', 'pre-tax income', 'total current assets', 'total current liabilities', 'cash from operating', 'cash from investing', 'cash from financing', 'total operating expenses', 'ebitda', 'free cash flow'];
const MARGIN_KEYWORDS = ['margin %', 'margin%', '% of revenue', 'sbc % of'];

function isTotal(label) {
  const l = label.toLowerCase();
  return TOTAL_KEYWORDS.some(k => l.includes(k));
}

function isSubtotal(label) {
  const l = label.toLowerCase();
  return SUBTOTAL_KEYWORDS.some(k => l.includes(k));
}

function isMarginRow(label) {
  const l = label.toLowerCase();
  return MARGIN_KEYWORDS.some(k => l.includes(k));
}

// ============================================================
// SECTION BUILDERS
// ============================================================

function buildCoverPage(data) {
  const company = data.company || {};
  const filing = data.metadata?.analysis_type === 'full' ? '10-K Annual Report' : 'Analysis';
  return [
    { text: '\n\n\n\n\n\n', fontSize: 12 },
    {
      canvas: [
        { type: 'rect', x: 0, y: 0, w: 515, h: 3, color: COLORS.primary },
      ],
    },
    { text: '\n' },
    { text: company.name || 'Company Analysis', fontSize: 28, bold: true, color: COLORS.textPrimary },
    { text: `${company.ticker || ''} — ${company.exchange || ''}`, fontSize: 14, color: COLORS.textMuted, margin: [0, 4, 0, 0] },
    { text: '\n' },
    { text: filing, fontSize: 16, color: COLORS.textSecondary },
    { text: company.industry || '', fontSize: 11, color: COLORS.textMuted, margin: [0, 4, 0, 0] },
    { text: '\n\n' },
    {
      columns: [
        { text: `Stock Price: ${company.stock_price ? '$' + company.stock_price.toFixed(2) : 'N/A'}`, fontSize: 11, color: COLORS.textSecondary },
        { text: `Market Cap: ${company.market_cap ? fmtCurrency(company.market_cap) : 'N/A'}`, fontSize: 11, color: COLORS.textSecondary },
        { text: `EV: ${company.enterprise_value ? fmtCurrency(company.enterprise_value) : 'N/A'}`, fontSize: 11, color: COLORS.textSecondary },
      ],
    },
    { text: '\n\n\n\n\n\n\n\n\n\n\n\n\n' },
    {
      canvas: [
        { type: 'rect', x: 0, y: 0, w: 515, h: 1, color: COLORS.border },
      ],
    },
    { text: '\n' },
    {
      columns: [
        { text: 'Folio — Equity Research Platform', fontSize: 9, color: COLORS.textMuted },
        { text: formatDateReadable(), fontSize: 9, color: COLORS.textMuted, alignment: 'right' },
      ],
    },
    { text: '', pageBreak: 'after' },
  ];
}

function buildKPISection(data) {
  const kpis = data.kpis || [];
  const headlines = data.headline_metrics || [];
  if (!kpis.length && !headlines.length) return [];

  const content = [
    { text: 'Key Performance Indicators', style: 'sectionHeader' },
  ];

  // Headline metrics as a single-row table
  if (headlines.length) {
    content.push({
      table: {
        headerRows: 0,
        widths: headlines.map(() => '*'),
        body: [
          headlines.map(m => ({
            text: [
              { text: m.label + '\n', fontSize: 7, color: COLORS.textMuted },
              { text: m.formatted || '—', fontSize: 11, bold: true, color: COLORS.textPrimary },
            ],
            alignment: 'center',
            margin: [4, 6, 4, 6],
          })),
        ],
      },
      layout: {
        hLineWidth: () => 0.5,
        vLineWidth: () => 0.5,
        hLineColor: () => COLORS.border,
        vLineColor: () => COLORS.border,
        paddingLeft: () => 4,
        paddingRight: () => 4,
        paddingTop: () => 4,
        paddingBottom: () => 4,
      },
      margin: [0, 0, 0, 12],
    });
  }

  // KPI cards as a 3-column table
  if (kpis.length) {
    const rows = [];
    for (let i = 0; i < kpis.length; i += 3) {
      const row = [];
      for (let j = 0; j < 3; j++) {
        const kpi = kpis[i + j];
        if (!kpi) {
          row.push({ text: '', border: [false, false, false, false] });
          continue;
        }
        const trendColor = kpi.trend === 'up' ? COLORS.positive : kpi.trend === 'down' ? COLORS.negative : COLORS.textMuted;
        row.push({
          stack: [
            { text: kpi.label, fontSize: 8, color: COLORS.textMuted },
            { text: kpi.formatted || '—', fontSize: 13, bold: true, color: COLORS.textPrimary, margin: [0, 2, 0, 0] },
            { text: kpi.change_formatted || '', fontSize: 8, color: trendColor, margin: [0, 1, 0, 0] },
          ],
          margin: [6, 6, 6, 6],
        });
      }
      rows.push(row);
    }

    content.push({
      table: {
        headerRows: 0,
        widths: ['*', '*', '*'],
        body: rows,
      },
      layout: {
        hLineWidth: () => 0.5,
        vLineWidth: () => 0.5,
        hLineColor: () => COLORS.border,
        vLineColor: () => COLORS.border,
        paddingLeft: () => 4,
        paddingRight: () => 4,
        paddingTop: () => 2,
        paddingBottom: () => 2,
      },
      margin: [0, 0, 0, 8],
    });
  }

  content.push({ text: '\n' });
  return content;
}

function buildStatementTable(title, stmt) {
  if (!stmt || !stmt.line_items?.length) return [];

  const periods = stmt.periods || [];
  // Determine scale label
  const firstUSDItem = stmt.line_items.find(i => i.unit === 'USD');
  let scaleLabel = '';
  if (firstUSDItem) {
    const maxVal = Math.max(...Object.values(firstUSDItem.values || {}).map(v => Math.abs(v || 0)));
    if (maxVal >= 1e9) scaleLabel = '($ in billions)';
    else if (maxVal >= 1e6) scaleLabel = '($ in millions)';
    else if (maxVal >= 1e3) scaleLabel = '($ in thousands)';
  }

  // Header row
  const headerRow = [
    { text: title + (scaleLabel ? '  ' + scaleLabel : ''), style: 'tableHeaderCell', alignment: 'left' },
    ...periods.map(p => ({ text: p, style: 'tableHeaderCell', alignment: 'right' })),
  ];

  // Data rows
  const body = [headerRow];
  for (const item of stmt.line_items) {
    const label = item.label;
    const unit = item.unit;
    const isTot = isTotal(label);
    const isSub = isSubtotal(label);
    const isMargin = isMarginRow(label);

    const labelCell = {
      text: isMargin ? `  ${label}` : isSub ? label : isTot ? label : `  ${label}`,
      fontSize: isMargin ? 7.5 : 8,
      bold: isTot || isSub,
      italics: isMargin,
      color: isMargin ? COLORS.textMuted : isTot ? COLORS.textPrimary : COLORS.textSecondary,
    };

    const valCells = periods.map(p => {
      const val = item.values?.[p];
      const formatted = fmtStatementValue(val, unit);
      return {
        text: formatted.text || '—',
        fontSize: isMargin ? 7.5 : 8,
        bold: isTot || isSub,
        italics: isMargin || formatted.italics,
        color: formatted.color || COLORS.textPrimary,
        alignment: 'right',
      };
    });

    body.push([labelCell, ...valCells]);
  }

  return [
    { text: '', pageBreak: body.length > 10 ? 'before' : undefined },
    {
      table: {
        headerRows: 1,
        widths: ['*', ...periods.map(() => 65)],
        body,
        dontBreakRows: true,
      },
      layout: {
        hLineWidth: (i, node) => {
          if (i === 0) return 0; // no top border
          if (i === 1) return 1.5; // thick line under header
          // Check if current row is a total
          const rowData = node.table.body[i];
          const prevRow = node.table.body[i - 1];
          if (!rowData || !prevRow) return 0.25;
          const prevLabel = typeof prevRow[0] === 'object' ? prevRow[0].text : '';
          if (isTotal(prevLabel)) return 1;
          if (isSubtotal(prevLabel)) return 0.5;
          return 0.25;
        },
        vLineWidth: () => 0,
        hLineColor: (i) => i === 1 ? COLORS.textSecondary : COLORS.borderSubtle,
        paddingLeft: (i) => i === 0 ? 4 : 3,
        paddingRight: (i) => 3,
        paddingTop: () => 2.5,
        paddingBottom: () => 2.5,
        fillColor: (rowIndex) => {
          if (rowIndex === 0) return null;
          return rowIndex % 2 === 0 ? '#fafbfc' : null;
        },
      },
      margin: [0, 0, 0, 16],
    },
  ];
}

function buildDerivedMetrics(data) {
  const dm = data.derived_metrics;
  if (!dm) return [];

  const content = [
    { text: 'Derived Metrics & Ratios', style: 'sectionHeader', pageBreak: 'before' },
  ];

  const categories = [
    ['Profitability', dm.profitability],
    ['Liquidity', dm.liquidity],
    ['Leverage', dm.leverage],
    ['Efficiency', dm.efficiency],
  ];

  for (const [catName, metrics] of categories) {
    if (!metrics) continue;
    const rows = [
      [
        { text: catName, style: 'tableHeaderCell', alignment: 'left' },
        { text: 'Value', style: 'tableHeaderCell', alignment: 'right' },
        { text: 'Period', style: 'tableHeaderCell', alignment: 'right' },
        { text: 'Trend', style: 'tableHeaderCell', alignment: 'right' },
      ],
    ];

    for (const [key, m] of Object.entries(metrics)) {
      if (!m) continue;
      const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      let valStr;
      if (key.includes('margin') || key.includes('roe') || key.includes('roa') || key.includes('roic') || key.includes('yield') || key.includes('pct') || key.includes('ratio') && m.value < 1) {
        valStr = fmtPercent(m.value);
      } else if (key.includes('capital') || key.includes('debt') || key.includes('net_debt')) {
        valStr = fmtCurrency(m.value);
      } else {
        valStr = typeof m.value === 'number' ? m.value.toFixed(2) : String(m.value);
      }

      const trendColor = m.trend === 'up' ? COLORS.positive : m.trend === 'down' ? COLORS.negative : COLORS.textMuted;
      const trendSymbol = m.trend === 'up' ? 'Up' : m.trend === 'down' ? 'Down' : 'Stable';

      rows.push([
        { text: label, fontSize: 8, color: COLORS.textSecondary },
        { text: valStr, fontSize: 8, color: COLORS.textPrimary, alignment: 'right', bold: true },
        { text: m.period || '', fontSize: 8, color: COLORS.textMuted, alignment: 'right' },
        { text: trendSymbol, fontSize: 8, color: trendColor, alignment: 'right' },
      ]);
    }

    content.push({
      table: {
        headerRows: 1,
        widths: ['*', 70, 60, 50],
        body: rows,
        dontBreakRows: true,
      },
      layout: {
        hLineWidth: (i) => i === 0 ? 0 : i === 1 ? 1 : 0.25,
        vLineWidth: () => 0,
        hLineColor: (i) => i === 1 ? COLORS.textSecondary : COLORS.borderSubtle,
        paddingLeft: () => 4,
        paddingRight: () => 4,
        paddingTop: () => 3,
        paddingBottom: () => 3,
        fillColor: (i) => i === 0 ? null : i % 2 === 0 ? '#fafbfc' : null,
      },
      margin: [0, 0, 0, 12],
    });
  }

  return content;
}

function buildNarrative(data) {
  const narrative = data.narrative;
  if (!narrative) return [];

  const content = [
    { text: 'Investment Analysis', style: 'sectionHeader', pageBreak: 'before' },
  ];

  // Summary
  if (narrative.summary) {
    content.push(
      { text: 'Executive Summary', style: 'subsectionHeader' },
      { text: narrative.summary, fontSize: 9, color: COLORS.textSecondary, lineHeight: 1.5, margin: [0, 0, 0, 12] },
    );
  }

  // Sections
  if (narrative.sections?.length) {
    for (const section of narrative.sections) {
      const sentimentColor = section.sentiment === 'positive' ? COLORS.positive
        : section.sentiment === 'negative' ? COLORS.negative
        : section.sentiment === 'mixed' ? '#d97706'
        : COLORS.textMuted;

      content.push(
        {
          columns: [
            { text: section.title, style: 'subsectionHeader', width: '*' },
            {
              text: (section.sentiment || '').toUpperCase(),
              fontSize: 7,
              color: sentimentColor,
              bold: true,
              alignment: 'right',
              margin: [0, 14, 0, 0],
              width: 'auto',
            },
          ],
        },
        { text: section.content, fontSize: 9, color: COLORS.textSecondary, lineHeight: 1.5, margin: [0, 0, 0, 12] },
      );
    }
  }

  // Risks
  if (narrative.risks?.length) {
    content.push(
      { text: 'Key Risk Factors', style: 'subsectionHeader' },
      {
        ul: narrative.risks.map(r => ({ text: r, fontSize: 9, color: COLORS.textSecondary, margin: [0, 2, 0, 2] })),
        margin: [8, 0, 0, 12],
      },
    );
  }

  // Outlook
  if (narrative.outlook) {
    content.push(
      { text: 'Forward Outlook', style: 'subsectionHeader' },
      { text: narrative.outlook, fontSize: 9, color: COLORS.textSecondary, lineHeight: 1.5, margin: [0, 0, 0, 12] },
    );
  }

  return content;
}

function buildInvestmentMemo(data) {
  const memo = data.investment_memo;
  if (!memo) return [];

  const rec = memo.recommendation || {};
  const company = data.company || {};
  const price = company.stock_price;
  const target = rec.price_target;
  const upside = (price && target) ? ((target - price) / price) : null;

  const content = [
    { text: 'Investment Memo', style: 'sectionHeader', pageBreak: 'before' },
  ];

  // -- Recommendation header row --
  const ratingColor = (rec.rating === 'Buy' || rec.rating === 'Strong Buy') ? COLORS.positive
    : (rec.rating === 'Sell' || rec.rating === 'Strong Sell') ? COLORS.negative
    : '#d97706';

  content.push({
    table: {
      headerRows: 0,
      widths: ['*', '*', '*', '*', '*'],
      body: [[
        { text: [{ text: 'Rating\n', fontSize: 7, color: COLORS.textMuted }, { text: rec.rating || '—', fontSize: 13, bold: true, color: ratingColor }], alignment: 'center', margin: [4, 6, 4, 6] },
        { text: [{ text: 'Target Price\n', fontSize: 7, color: COLORS.textMuted }, { text: target != null ? `$${target}` : '—', fontSize: 13, bold: true, color: COLORS.primary }], alignment: 'center', margin: [4, 6, 4, 6] },
        { text: [{ text: 'Upside\n', fontSize: 7, color: COLORS.textMuted }, { text: upside != null ? `${(upside * 100).toFixed(1)}%` : '—', fontSize: 13, bold: true, color: upside >= 0 ? COLORS.positive : COLORS.negative }], alignment: 'center', margin: [4, 6, 4, 6] },
        { text: [{ text: 'Conviction\n', fontSize: 7, color: COLORS.textMuted }, { text: rec.conviction || '—', fontSize: 13, bold: true, color: COLORS.textPrimary }], alignment: 'center', margin: [4, 6, 4, 6] },
        { text: [{ text: 'Horizon\n', fontSize: 7, color: COLORS.textMuted }, { text: rec.time_horizon || '12 months', fontSize: 11, bold: true, color: COLORS.textPrimary }], alignment: 'center', margin: [4, 6, 4, 6] },
      ]],
    },
    layout: {
      hLineWidth: () => 0.5, vLineWidth: () => 0.5,
      hLineColor: () => COLORS.border, vLineColor: () => COLORS.border,
      paddingLeft: () => 4, paddingRight: () => 4, paddingTop: () => 4, paddingBottom: () => 4,
    },
    margin: [0, 0, 0, 12],
  });

  // -- Executive Summary --
  if (memo.executive_summary) {
    content.push(
      { text: 'Executive Summary', style: 'subsectionHeader' },
      { text: memo.executive_summary, fontSize: 9, color: COLORS.textSecondary, lineHeight: 1.5, margin: [0, 0, 0, 8] },
    );
  }

  // -- Thesis Bullets --
  if (memo.thesis_bullets?.length) {
    content.push({
      ol: memo.thesis_bullets.map(b => ({ text: b, fontSize: 9, color: COLORS.textSecondary, margin: [0, 2, 0, 2] })),
      margin: [8, 0, 0, 12],
    });
  }

  // -- Thesis Pillars --
  if (memo.thesis_pillars?.length) {
    content.push({ text: 'Thesis Pillars', style: 'subsectionHeader' });
    for (const p of memo.thesis_pillars) {
      const sentColor = p.sentiment === 'positive' ? COLORS.positive : p.sentiment === 'negative' ? COLORS.negative : '#d97706';
      content.push(
        {
          columns: [
            { text: p.title, fontSize: 10, bold: true, color: COLORS.textPrimary, width: '*' },
            p.metric != null ? { text: `${p.metric_label || ''}: ${p.metric}`, fontSize: 9, bold: true, color: COLORS.primary, alignment: 'right', width: 'auto' } : { text: '', width: 0 },
          ],
          margin: [0, 6, 0, 2],
        },
        {
          canvas: [{ type: 'rect', x: 0, y: 0, w: 3, h: 0.1, color: sentColor }],
        },
        { text: p.description, fontSize: 8.5, color: COLORS.textSecondary, lineHeight: 1.4, margin: [0, 0, 0, 6] },
      );
    }
  }

  // -- Scenario Analysis --
  if (memo.scenario_analysis) {
    content.push({ text: 'Scenario Analysis', style: 'subsectionHeader', pageBreak: 'before' });
    const scenarios = memo.scenario_analysis;
    const scenarioOrder = [
      { key: 'bull', label: 'Bull Case', color: COLORS.positive },
      { key: 'base', label: 'Base Case', color: COLORS.primary },
      { key: 'bear', label: 'Bear Case', color: COLORS.negative },
    ];

    const scenarioRows = [
      [
        { text: 'Scenario', style: 'tableHeaderCell', alignment: 'left' },
        { text: 'Price Target', style: 'tableHeaderCell', alignment: 'right' },
        { text: 'vs Current', style: 'tableHeaderCell', alignment: 'right' },
        { text: 'Thesis', style: 'tableHeaderCell', alignment: 'left' },
      ],
    ];

    for (const s of scenarioOrder) {
      const sc = scenarios[s.key];
      if (!sc) continue;
      const scUpside = (price && sc.price_target) ? ((sc.price_target - price) / price) : null;
      scenarioRows.push([
        { text: s.label, fontSize: 9, bold: true, color: s.color },
        { text: sc.price_target != null ? `$${sc.price_target}` : '—', fontSize: 9, bold: true, color: s.color, alignment: 'right' },
        { text: scUpside != null ? `${(scUpside * 100).toFixed(0)}%` : '—', fontSize: 9, color: s.color, alignment: 'right' },
        { text: sc.thesis || '', fontSize: 8, color: COLORS.textSecondary },
      ]);
    }

    content.push({
      table: {
        headerRows: 1,
        widths: [70, 65, 55, '*'],
        body: scenarioRows,
        dontBreakRows: true,
      },
      layout: {
        hLineWidth: (i) => i === 0 ? 0 : i === 1 ? 1 : 0.25,
        vLineWidth: () => 0,
        hLineColor: (i) => i === 1 ? COLORS.textSecondary : COLORS.borderSubtle,
        paddingLeft: () => 4, paddingRight: () => 4, paddingTop: () => 4, paddingBottom: () => 4,
        fillColor: (i) => i === 0 ? null : i % 2 === 0 ? '#fafbfc' : null,
      },
      margin: [0, 0, 0, 12],
    });

    // Assumptions for each scenario
    for (const s of scenarioOrder) {
      const sc = scenarios[s.key];
      if (!sc?.assumptions?.length) continue;
      content.push(
        { text: `${s.label} Assumptions`, fontSize: 8, bold: true, color: s.color, margin: [0, 2, 0, 2] },
        { ul: sc.assumptions.map(a => ({ text: a, fontSize: 8, color: COLORS.textSecondary, margin: [0, 1, 0, 1] })), margin: [8, 0, 0, 8] },
      );
    }
  }

  // -- Catalysts --
  if (memo.catalysts?.length) {
    content.push({ text: 'Catalysts & Upcoming Events', style: 'subsectionHeader' });
    for (const c of memo.catalysts) {
      content.push(
        {
          columns: [
            { text: c.date || '', fontSize: 8, bold: true, color: COLORS.primary, width: 80 },
            {
              stack: [
                { text: c.title || c.event || '', fontSize: 9, bold: true, color: COLORS.textPrimary },
                c.description ? { text: c.description, fontSize: 8, color: COLORS.textSecondary, margin: [0, 1, 0, 0] } : null,
                c.impact ? { text: `Impact: ${c.impact}`, fontSize: 7.5, color: COLORS.primary, italics: true, margin: [0, 1, 0, 0] } : null,
              ].filter(Boolean),
              width: '*',
            },
          ],
          margin: [0, 3, 0, 3],
        },
      );
    }
    content.push({ text: '\n' });
  }

  // -- Risk-Mitigant Pairs --
  if (memo.risk_mitigant_pairs?.length) {
    content.push({ text: 'Risk-Mitigant Analysis', style: 'subsectionHeader', pageBreak: 'before' });

    const riskRows = [
      [
        { text: 'Sev.', style: 'tableHeaderCell', alignment: 'center' },
        { text: 'Risk', style: 'tableHeaderCell', alignment: 'left' },
        { text: 'Mitigant', style: 'tableHeaderCell', alignment: 'left' },
      ],
    ];

    for (const p of memo.risk_mitigant_pairs) {
      const sevColor = p.severity === 'High' ? COLORS.negative : p.severity === 'Medium' ? '#d97706' : COLORS.textMuted;
      riskRows.push([
        { text: p.severity || 'Med', fontSize: 8, bold: true, color: sevColor, alignment: 'center' },
        { text: p.risk || '', fontSize: 8, color: COLORS.textPrimary },
        { text: p.mitigant || '', fontSize: 8, color: COLORS.textSecondary },
      ]);
    }

    content.push({
      table: {
        headerRows: 1,
        widths: [35, '*', '*'],
        body: riskRows,
        dontBreakRows: true,
      },
      layout: {
        hLineWidth: (i) => i === 0 ? 0 : i === 1 ? 1 : 0.25,
        vLineWidth: () => 0,
        hLineColor: (i) => i === 1 ? COLORS.textSecondary : COLORS.borderSubtle,
        paddingLeft: () => 4, paddingRight: () => 4, paddingTop: () => 3, paddingBottom: () => 3,
        fillColor: (i) => i === 0 ? null : i % 2 === 0 ? '#fafbfc' : null,
      },
      margin: [0, 0, 0, 12],
    });
  }

  // -- Position sizing --
  if (rec.position_size) {
    content.push({
      text: [
        { text: 'Position Sizing: ', fontSize: 9, bold: true, color: COLORS.textPrimary },
        { text: rec.position_size, fontSize: 9, color: COLORS.textSecondary },
      ],
      margin: [0, 0, 0, 8],
    });
  }

  // -- Monitor Metrics --
  if (rec.monitor_metrics?.length) {
    content.push(
      { text: 'Key Metrics to Monitor', fontSize: 9, bold: true, color: COLORS.textPrimary, margin: [0, 4, 0, 4] },
      { ul: rec.monitor_metrics.map(m => ({ text: m, fontSize: 8, color: COLORS.textSecondary, margin: [0, 1, 0, 1] })), margin: [8, 0, 0, 12] },
    );
  }

  return content;
}

function buildValuationSection(data) {
  const headlines = data.headline_metrics || [];
  const dm = data.derived_metrics || {};
  const narrative = data.narrative || {};

  const valuationMetrics = headlines.filter(m =>
    ['P/E Ratio', 'EV / Revenue', 'EV / EBITDA', 'Market Cap', 'Enterprise Value', 'Stock Price'].includes(m.label)
  );

  if (!valuationMetrics.length && !dm.profitability && !dm.efficiency) return [];

  const content = [
    { text: 'Valuation & Metrics', style: 'sectionHeader', pageBreak: 'before' },
  ];

  // Valuation multiples
  if (valuationMetrics.length) {
    content.push({
      table: {
        headerRows: 0,
        widths: valuationMetrics.map(() => '*'),
        body: [
          valuationMetrics.map(m => ({
            text: [
              { text: m.label + '\n', fontSize: 7, color: COLORS.textMuted },
              { text: m.formatted || '—', fontSize: 11, bold: true, color: COLORS.textPrimary },
            ],
            alignment: 'center',
            margin: [4, 6, 4, 6],
          })),
        ],
      },
      layout: {
        hLineWidth: () => 0.5, vLineWidth: () => 0.5,
        hLineColor: () => COLORS.border, vLineColor: () => COLORS.border,
        paddingLeft: () => 4, paddingRight: () => 4, paddingTop: () => 4, paddingBottom: () => 4,
      },
      margin: [0, 0, 0, 12],
    });
  }

  // Profitability + Efficiency metrics tables
  const categories = [
    ['Profitability', dm.profitability],
    ['Efficiency & Returns', dm.efficiency],
  ];

  for (const [catName, metrics] of categories) {
    if (!metrics) continue;
    const rows = [
      [
        { text: catName, style: 'tableHeaderCell', alignment: 'left' },
        { text: 'Value', style: 'tableHeaderCell', alignment: 'right' },
        { text: 'Trend', style: 'tableHeaderCell', alignment: 'right' },
      ],
    ];

    for (const [key, m] of Object.entries(metrics)) {
      if (!m) continue;
      const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      let valStr;
      if (key.includes('margin') || key.includes('roe') || key.includes('roa') || key.includes('roic') || key.includes('yield')) {
        valStr = fmtPercent(m.value);
      } else if (key.includes('capital') || key.includes('debt') || key.includes('net_debt')) {
        valStr = fmtCurrency(m.value);
      } else {
        valStr = typeof m.value === 'number' ? m.value.toFixed(2) : String(m.value);
      }
      const trendColor = m.trend === 'up' ? COLORS.positive : m.trend === 'down' ? COLORS.negative : COLORS.textMuted;
      rows.push([
        { text: label, fontSize: 8, color: COLORS.textSecondary },
        { text: valStr, fontSize: 8, bold: true, color: COLORS.textPrimary, alignment: 'right' },
        { text: m.trend === 'up' ? 'Up' : m.trend === 'down' ? 'Down' : 'Stable', fontSize: 8, color: trendColor, alignment: 'right' },
      ]);
    }

    content.push({
      table: {
        headerRows: 1,
        widths: ['*', 80, 50],
        body: rows,
        dontBreakRows: true,
      },
      layout: {
        hLineWidth: (i) => i === 0 ? 0 : i === 1 ? 1 : 0.25,
        vLineWidth: () => 0,
        hLineColor: (i) => i === 1 ? COLORS.textSecondary : COLORS.borderSubtle,
        paddingLeft: () => 4, paddingRight: () => 4, paddingTop: () => 3, paddingBottom: () => 3,
        fillColor: (i) => i === 0 ? null : i % 2 === 0 ? '#fafbfc' : null,
      },
      margin: [0, 0, 0, 12],
    });
  }

  // Valuation-related narrative
  if (narrative.sections) {
    const relevant = narrative.sections.filter(s =>
      /profit|cash|capital|balance|valuation|margin/i.test(s.title)
    );
    for (const section of relevant) {
      const sentColor = section.sentiment === 'positive' ? COLORS.positive
        : section.sentiment === 'negative' ? COLORS.negative
        : section.sentiment === 'mixed' ? '#d97706' : COLORS.textMuted;
      content.push(
        {
          columns: [
            { text: section.title, style: 'subsectionHeader', width: '*' },
            { text: (section.sentiment || '').toUpperCase(), fontSize: 7, color: sentColor, bold: true, alignment: 'right', margin: [0, 14, 0, 0], width: 'auto' },
          ],
        },
        { text: section.content, fontSize: 9, color: COLORS.textSecondary, lineHeight: 1.5, margin: [0, 0, 0, 8] },
      );
    }
  }

  return content;
}

function buildCompetitorsSection(data) {
  const narrative = data.narrative || {};
  const company = data.company || {};

  const competitiveNarr = narrative.sections?.filter(s =>
    /compet|market|position|risk|growth|revenue/i.test(s.title)
  ) || [];

  if (!competitiveNarr.length && !narrative.risks?.length) return [];

  const content = [
    { text: 'Competitive Landscape', style: 'sectionHeader', pageBreak: 'before' },
    { text: `Industry: ${company.industry || 'N/A'}`, fontSize: 9, color: COLORS.textMuted, margin: [0, 0, 0, 12] },
  ];

  for (const section of competitiveNarr) {
    const sentColor = section.sentiment === 'positive' ? COLORS.positive
      : section.sentiment === 'negative' ? COLORS.negative
      : section.sentiment === 'mixed' ? '#d97706' : COLORS.textMuted;
    content.push(
      {
        columns: [
          { text: section.title, style: 'subsectionHeader', width: '*' },
          { text: (section.sentiment || '').toUpperCase(), fontSize: 7, color: sentColor, bold: true, alignment: 'right', margin: [0, 14, 0, 0], width: 'auto' },
        ],
      },
      { text: section.content, fontSize: 9, color: COLORS.textSecondary, lineHeight: 1.5, margin: [0, 0, 0, 8] },
    );
  }

  if (narrative.risks?.length) {
    content.push(
      { text: 'Competitive Risk Factors', style: 'subsectionHeader' },
      {
        ul: narrative.risks.map(r => ({ text: r, fontSize: 9, color: COLORS.textSecondary, margin: [0, 2, 0, 2] })),
        margin: [8, 0, 0, 12],
      },
    );
  }

  return content;
}

function buildManagementSection(data) {
  const company = data.company || {};
  const narrative = data.narrative || {};
  const dm = data.derived_metrics || {};
  const liquidity = dm.liquidity || {};
  const leverage = dm.leverage || {};

  const content = [
    { text: 'Management & Company Overview', style: 'sectionHeader', pageBreak: 'before' },
  ];

  // Company details table
  const detailRows = [
    ['Name', company.name || 'N/A'],
    ['Ticker / Exchange', `${company.ticker || 'N/A'} / ${company.exchange || 'N/A'}`],
    ['Sector / Industry', `${company.sector || 'N/A'} / ${company.industry || 'N/A'}`],
    ['Fiscal Year End', company.fiscal_year_end || 'N/A'],
    ['Market Cap', company.market_cap ? fmtCurrency(company.market_cap) : 'N/A'],
    ['Shares Outstanding', company.shares_outstanding ? fmtNumber(company.shares_outstanding) : 'N/A'],
    ['Current Ratio', liquidity.current_ratio?.value != null ? liquidity.current_ratio.value.toFixed(2) + 'x' : 'N/A'],
    ['Debt to Equity', leverage.debt_to_equity?.value != null ? leverage.debt_to_equity.value.toFixed(2) + 'x' : 'N/A'],
  ];

  content.push({
    table: {
      headerRows: 0,
      widths: [120, '*'],
      body: detailRows.map(([label, val]) => [
        { text: label, fontSize: 8, color: COLORS.textMuted, bold: true },
        { text: val, fontSize: 8, color: COLORS.textPrimary },
      ]),
    },
    layout: {
      hLineWidth: (i) => i === 0 ? 0 : 0.25,
      vLineWidth: () => 0,
      hLineColor: () => COLORS.borderSubtle,
      paddingLeft: () => 4, paddingRight: () => 4, paddingTop: () => 3, paddingBottom: () => 3,
      fillColor: (i) => i % 2 === 0 ? '#fafbfc' : null,
    },
    margin: [0, 0, 0, 16],
  });

  // Outlook
  if (narrative.outlook) {
    content.push(
      { text: 'Forward Outlook', style: 'subsectionHeader' },
      { text: narrative.outlook, fontSize: 9, color: COLORS.textSecondary, lineHeight: 1.5, margin: [0, 0, 0, 12] },
    );
  }

  return content;
}

function buildIRSection(data) {
  const sources = data.sources || [];
  const dq = data.data_quality || {};
  const meta = data.metadata || {};
  const company = data.company || {};

  const content = [
    { text: 'Investor Relations & Data Sources', style: 'sectionHeader', pageBreak: 'before' },
  ];

  // SEC filings
  const secSources = sources.filter(s => s.type === 'sec_filing');
  if (secSources.length) {
    content.push({ text: 'SEC Filings', style: 'subsectionHeader' });
    for (const s of secSources) {
      content.push({
        text: [
          { text: s.label || '', fontSize: 9, bold: true, color: COLORS.textPrimary },
          s.date ? { text: `  (${s.date})`, fontSize: 8, color: COLORS.textMuted } : null,
          s.url ? { text: `  ${s.url}`, fontSize: 7, color: COLORS.primary, link: s.url } : null,
        ].filter(Boolean),
        margin: [0, 2, 0, 2],
      });
    }
    content.push({ text: '\n' });
  }

  // All sources
  if (sources.length) {
    content.push({ text: 'All Data Sources', style: 'subsectionHeader' });
    const srcRows = [
      [
        { text: 'ID', style: 'tableHeaderCell' },
        { text: 'Source', style: 'tableHeaderCell' },
        { text: 'Type', style: 'tableHeaderCell' },
        { text: 'Reliability', style: 'tableHeaderCell', alignment: 'right' },
      ],
    ];
    for (const s of sources) {
      srcRows.push([
        { text: s.id || '', fontSize: 7, color: COLORS.primary, bold: true },
        { text: s.label || '', fontSize: 8, color: COLORS.textSecondary },
        { text: s.type?.replace(/_/g, ' ') || '', fontSize: 7, color: COLORS.textMuted },
        { text: s.reliability || '', fontSize: 7, color: COLORS.textMuted, alignment: 'right' },
      ]);
    }
    content.push({
      table: {
        headerRows: 1,
        widths: [25, '*', 70, 50],
        body: srcRows,
        dontBreakRows: true,
      },
      layout: {
        hLineWidth: (i) => i === 0 ? 0 : i === 1 ? 1 : 0.25,
        vLineWidth: () => 0,
        hLineColor: (i) => i === 1 ? COLORS.textSecondary : COLORS.borderSubtle,
        paddingLeft: () => 4, paddingRight: () => 4, paddingTop: () => 2, paddingBottom: () => 2,
      },
      margin: [0, 0, 0, 12],
    });
  }

  // Data quality
  if (dq.overall_confidence || dq.completeness != null) {
    content.push(
      { text: 'Data Quality', style: 'subsectionHeader' },
      {
        text: [
          { text: 'Confidence: ', fontSize: 9, bold: true, color: COLORS.textMuted },
          { text: (dq.overall_confidence || 'N/A').toUpperCase(), fontSize: 9, color: COLORS.textPrimary, bold: true },
          { text: '   Completeness: ', fontSize: 9, bold: true, color: COLORS.textMuted },
          { text: dq.completeness != null ? `${(dq.completeness * 100).toFixed(0)}%` : 'N/A', fontSize: 9, color: COLORS.textPrimary, bold: true },
        ],
        margin: [0, 0, 0, 8],
      },
    );
  }

  if (dq.warnings?.length) {
    content.push(
      { text: 'Warnings', fontSize: 9, bold: true, color: '#d97706', margin: [0, 4, 0, 4] },
      { ul: dq.warnings.map(w => ({ text: w, fontSize: 8, color: COLORS.textSecondary, margin: [0, 1, 0, 1] })), margin: [8, 0, 0, 8] },
    );
  }

  if (dq.missing_data?.length) {
    content.push(
      { text: 'Missing Data', fontSize: 9, bold: true, color: COLORS.textMuted, margin: [0, 4, 0, 4] },
      { ul: dq.missing_data.map(m => ({ text: m, fontSize: 8, color: COLORS.textMuted, margin: [0, 1, 0, 1] })), margin: [8, 0, 0, 8] },
    );
  }

  // Analysis metadata
  if (meta.analysis_id || meta.timestamp || meta.model) {
    content.push({ text: 'Analysis Metadata', style: 'subsectionHeader' });
    const metaRows = [
      ['Analysis ID', meta.analysis_id || 'N/A'],
      ['Timestamp', meta.timestamp ? new Date(meta.timestamp).toLocaleDateString() : 'N/A'],
      ['Model', meta.model || 'N/A'],
      ['Schema Version', meta.prompt_version || 'N/A'],
    ];
    content.push({
      table: {
        headerRows: 0,
        widths: [100, '*'],
        body: metaRows.map(([label, val]) => [
          { text: label, fontSize: 8, color: COLORS.textMuted, bold: true },
          { text: val, fontSize: 8, color: COLORS.textPrimary },
        ]),
      },
      layout: {
        hLineWidth: () => 0.25, vLineWidth: () => 0,
        hLineColor: () => COLORS.borderSubtle,
        paddingLeft: () => 4, paddingRight: () => 4, paddingTop: () => 3, paddingBottom: () => 3,
      },
      margin: [0, 0, 0, 12],
    });
  }

  return content;
}

function buildSourcesAndDisclaimer(data) {
  const sources = data.sources || [];
  const dq = data.data_quality || {};

  const content = [
    {
      canvas: [
        { type: 'rect', x: 0, y: 0, w: 515, h: 0.5, color: COLORS.border },
      ],
      margin: [0, 8, 0, 8],
    },
    { text: 'Sources & Data Quality', fontSize: 10, bold: true, color: COLORS.textPrimary, margin: [0, 0, 0, 6] },
  ];

  if (sources.length) {
    for (const src of sources) {
      content.push({
        text: [
          { text: `[${src.id}] `, fontSize: 7, bold: true, color: COLORS.primary },
          { text: src.label, fontSize: 8, color: COLORS.textSecondary },
          { text: src.date ? ` (${src.date})` : '', fontSize: 7, color: COLORS.textMuted },
        ],
        margin: [0, 1, 0, 1],
      });
    }
  }

  if (dq.overall_confidence || dq.completeness) {
    content.push({ text: '\n' });
    content.push({
      text: [
        { text: 'Confidence: ', fontSize: 8, bold: true, color: COLORS.textMuted },
        { text: (dq.overall_confidence || 'N/A').toUpperCase(), fontSize: 8, color: COLORS.textPrimary },
        { text: '  |  Completeness: ', fontSize: 8, bold: true, color: COLORS.textMuted },
        { text: dq.completeness ? `${(dq.completeness * 100).toFixed(0)}%` : 'N/A', fontSize: 8, color: COLORS.textPrimary },
      ],
    });
  }

  if (dq.warnings?.length) {
    content.push({ text: '\n' });
    content.push({ text: 'Warnings:', fontSize: 8, bold: true, color: COLORS.textMuted });
    for (const w of dq.warnings) {
      content.push({ text: `  - ${w}`, fontSize: 7.5, color: COLORS.textMuted, margin: [0, 1, 0, 0] });
    }
  }

  // Disclaimer
  content.push(
    { text: '\n\n' },
    {
      canvas: [
        { type: 'rect', x: 0, y: 0, w: 515, h: 0.5, color: COLORS.border },
      ],
      margin: [0, 0, 0, 6],
    },
    {
      text: 'This report was generated by Folio, an equity research platform. Financial data is sourced from SEC EDGAR filings and may contain estimates. This is not investment advice. Verify all figures independently before making investment decisions.',
      fontSize: 7,
      color: COLORS.textMuted,
      italics: true,
      lineHeight: 1.4,
    },
  );

  return content;
}

// ============================================================
// MAIN EXPORT FUNCTION
// ============================================================

/**
 * Generate and download a PDF report from AnalysisJSON data.
 * @param {object} analysisResult - The AnalysisJSON object
 * @param {string} ticker - Company ticker for filename
 */
export function generatePDF(analysisResult, ticker = 'analysis') {
  if (!analysisResult) {
    console.warn('[PDF] No analysis result to export');
    return;
  }

  // Check pdfmake is loaded
  if (typeof pdfMake === 'undefined') {
    console.error('[PDF] pdfMake not loaded. Ensure CDN scripts are included.');
    return;
  }

  const stmts = analysisResult.financial_statements || {};
  const companyName = analysisResult.company?.name || ticker;

  const docDefinition = {
    pageSize: 'LETTER',
    pageMargins: [40, 55, 40, 45],

    // Header (skip cover page)
    header: (currentPage, pageCount) => {
      if (currentPage === 1) return null;
      return {
        columns: [
          { text: `${companyName} (${ticker})`, fontSize: 7.5, color: COLORS.textMuted, margin: [40, 25, 0, 0] },
          { text: formatDateReadable(), fontSize: 7.5, color: COLORS.textMuted, alignment: 'right', margin: [0, 25, 40, 0] },
        ],
      };
    },

    // Footer with page numbers (skip cover)
    footer: (currentPage, pageCount) => {
      if (currentPage === 1) return null;
      return {
        columns: [
          { text: 'Folio — Equity Research Platform', fontSize: 7, color: COLORS.textMuted, margin: [40, 0, 0, 0] },
          { text: `Page ${currentPage} of ${pageCount}`, fontSize: 7, color: COLORS.textMuted, alignment: 'right', margin: [0, 0, 40, 0] },
        ],
        margin: [0, 10, 0, 0],
      };
    },

    content: [
      ...buildCoverPage(analysisResult),
      ...buildInvestmentMemo(analysisResult),
      ...buildKPISection(analysisResult),
      ...buildStatementTable('Income Statement', stmts.income_statement),
      ...buildStatementTable('Balance Sheet', stmts.balance_sheet),
      ...buildStatementTable('Cash Flow Statement', stmts.cash_flow_statement),
      ...buildDerivedMetrics(analysisResult),
      ...buildNarrative(analysisResult),
      ...buildValuationSection(analysisResult),
      ...buildCompetitorsSection(analysisResult),
      ...buildManagementSection(analysisResult),
      ...buildIRSection(analysisResult),
      ...buildSourcesAndDisclaimer(analysisResult),
    ],

    defaultStyle: {
      font: 'Roboto',
      fontSize: 9,
      color: COLORS.textPrimary,
    },

    styles: {
      sectionHeader: {
        fontSize: 14,
        bold: true,
        color: COLORS.textPrimary,
        margin: [0, 16, 0, 8],
      },
      subsectionHeader: {
        fontSize: 11,
        bold: true,
        color: COLORS.textPrimary,
        margin: [0, 10, 0, 4],
      },
      tableHeaderCell: {
        fontSize: 7.5,
        bold: true,
        color: COLORS.textMuted,
      },
    },
  };

  const filename = `${ticker.toLowerCase()}-report-${formatDate()}.pdf`;
  pdfMake.createPdf(docDefinition).download(filename);
  console.log(`[PDF] Downloaded ${filename}`);
}
