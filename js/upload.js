/**
 * upload.js — File Upload Handler & Client-Side Document Parser
 * Investment Group of Santa Barbara — Financial Analysis Platform
 *
 * Handles drag-and-drop / file-input uploads, parses PDF (via pdf.js),
 * Excel/CSV (via SheetJS), and plain text files client-side.
 * Exports parsed data for consumption by the analysis module.
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALLOWED_EXTENSIONS = ['pdf', 'xlsx', 'xls', 'csv', 'txt'];
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB

const TYPE_CONFIG = {
  pdf:  { badge: 'PDF',  bgClass: 'bg-red-50',     textClass: 'text-red-600'     },
  xlsx: { badge: 'XLSX', bgClass: 'bg-emerald-50',  textClass: 'text-emerald-600' },
  xls:  { badge: 'XLS',  bgClass: 'bg-emerald-50',  textClass: 'text-emerald-600' },
  csv:  { badge: 'CSV',  bgClass: 'bg-blue-50',     textClass: 'text-blue-600'    },
  txt:  { badge: 'TXT',  bgClass: 'bg-slate-100',   textClass: 'text-slate-600'   },
};

const TOAST_COLORS = {
  success: { icon: 'text-emerald-500', border: 'border-emerald-200', bg: 'bg-emerald-50' },
  error:   { icon: 'text-red-500',     border: 'border-red-200',     bg: 'bg-red-50'     },
  info:    { icon: 'text-blue-500',    border: 'border-blue-200',    bg: 'bg-blue-50'    },
  warning: { icon: 'text-amber-500',   border: 'border-amber-200',  bg: 'bg-amber-50'   },
};

const TOAST_ICONS = {
  success: `<svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
  </svg>`,
  error: `<svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/>
  </svg>`,
  info: `<svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"/>
  </svg>`,
  warning: `<svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
  </svg>`,
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const uploadedDocuments = [];
let nextSourceId = 100; // Starts at 100 to avoid conflicts with EDGAR sources

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

/**
 * Wire up all event listeners for file upload UI.
 * Call once from the main app controller after DOM is ready.
 */
export function initUpload() {
  const uploadZone = document.getElementById('upload-zone');
  const fileInput  = document.getElementById('file-input');

  if (!uploadZone || !fileInput) {
    console.warn('[upload] Could not find #upload-zone or #file-input — skipping init.');
    return;
  }

  // Click-to-browse (the inline onclick in index.html also does this, but
  // we wire it here too for completeness — the hidden input click is idempotent).
  uploadZone.addEventListener('click', () => fileInput.click());

  // File input change
  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
    // Reset so the same file can be re-selected
    fileInput.value = '';
  });

  // Drag-and-drop — the visual feedback classes are already handled inline
  // in index.html. Here we handle the actual drop.
  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    uploadZone.classList.remove('drop-zone-active');

    if (e.dataTransfer && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  });

  // Prevent default drag behaviour on the zone (in addition to inline handlers)
  ['dragenter', 'dragover'].forEach((evt) => {
    uploadZone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
  });
}

// ---------------------------------------------------------------------------
// File handling pipeline
// ---------------------------------------------------------------------------

/**
 * Process a FileList — validate, parse, and add each accepted file.
 * @param {FileList} files
 */
async function handleFiles(files) {
  for (const file of Array.from(files)) {
    const ext = getExtension(file.name);

    // Validate extension
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      showToast(
        `Unsupported file type: .${ext}. Accepted formats: PDF, XLSX, XLS, CSV, TXT.`,
        'error',
      );
      continue;
    }

    // Validate size
    if (file.size > MAX_FILE_SIZE) {
      showToast(
        `File "${file.name}" exceeds the 25 MB limit (${formatFileSize(file.size)}).`,
        'error',
      );
      continue;
    }

    // Check duplicate filenames
    if (uploadedDocuments.some((d) => d.filename === file.name)) {
      showToast(`"${file.name}" has already been uploaded.`, 'warning');
      continue;
    }

    // Create a placeholder entry so the UI can show "Parsing..."
    const docId = nextSourceId++;
    const docEntry = {
      id: docId,
      filename: file.name,
      fileSize: file.size,
      ext,
      status: 'parsing', // 'parsing' | 'ready' | 'error'
      parsedData: null,
      source: null,
      error: null,
    };
    uploadedDocuments.push(docEntry);
    renderFileList();

    // Parse
    try {
      const parsed = await parseFile(file);
      docEntry.parsedData = parsed;
      docEntry.status = 'ready';
      docEntry.source = {
        id: docEntry.id,
        type: 'uploaded_document',
        label: file.name,
        filename: file.name,
        parsedAt: new Date().toISOString(),
        reliability: 'medium',
      };
      showToast(`"${file.name}" parsed successfully.`, 'success');
      document.dispatchEvent(new CustomEvent('document-added', { detail: { document: docEntry } }));
    } catch (err) {
      docEntry.status = 'error';
      docEntry.error = err.message || 'Unknown parsing error';
      console.warn(`[upload] Failed to parse "${file.name}":`, err);
      showToast(`Failed to parse "${file.name}": ${docEntry.error}`, 'error');
    }

    renderFileList();
    updateSourceList();
    updateFooterSourceCount();
  }
}

// ---------------------------------------------------------------------------
// Parsing dispatcher
// ---------------------------------------------------------------------------

/**
 * Route a file to the appropriate parser based on extension.
 * @param {File} file
 * @returns {Promise<object>} Parsed data structure
 */
async function parseFile(file) {
  const ext = getExtension(file.name);

  switch (ext) {
    case 'pdf':
      return parsePDF(file);
    case 'xlsx':
    case 'xls':
    case 'csv':
      return parseSpreadsheet(file);
    case 'txt':
      return parseText(file);
    default:
      throw new Error(`No parser available for .${ext}`);
  }
}

// ---------------------------------------------------------------------------
// PDF Parsing (via pdf.js — window.pdfjsLib)
// ---------------------------------------------------------------------------

/**
 * Extract text content (and basic table heuristics) from a PDF file.
 * @param {File} file
 * @returns {Promise<object>}
 */
async function parsePDF(file) {
  const pdfjsLib = window.pdfjsLib;
  if (!pdfjsLib) {
    throw new Error('pdf.js library not loaded. Check CDN script in index.html.');
  }

  const arrayBuffer = await file.arrayBuffer();
  const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
  const pdf = await loadingTask.promise;

  const totalPages = pdf.numPages;
  let fullText = '';
  const tables = [];

  for (let pageNum = 1; pageNum <= totalPages; pageNum++) {
    const page = await pdf.getPage(pageNum);
    const textContent = await page.getTextContent();

    // Build lines from text items, grouping by approximate Y coordinate
    const lineMap = new Map();
    for (const item of textContent.items) {
      if (!item.str || item.str.trim() === '') continue;

      // Round Y to nearest integer to group items on the same line
      const y = Math.round(item.transform[5]);
      if (!lineMap.has(y)) {
        lineMap.set(y, []);
      }
      lineMap.get(y).push({
        text: item.str,
        x: item.transform[4],
        width: item.width,
      });
    }

    // Sort lines by descending Y (top of page = higher Y in PDF coords)
    const sortedYs = Array.from(lineMap.keys()).sort((a, b) => b - a);
    const pageLines = [];

    for (const y of sortedYs) {
      const items = lineMap.get(y).sort((a, b) => a.x - b.x);
      const lineText = items.map((i) => i.text).join(' ');
      pageLines.push({ text: lineText, items });
    }

    // Accumulate full text
    const pageText = pageLines.map((l) => l.text).join('\n');
    fullText += (pageNum > 1 ? '\n\n--- Page ' + pageNum + ' ---\n\n' : '') + pageText;

    // Basic table detection: lines with 3+ items that have consistent column
    // spacing, or lines containing tab / pipe delimiters
    const candidateTableLines = [];
    for (const line of pageLines) {
      const hasDelimiters = /\t|\|/.test(line.text);
      const hasMultipleColumns = line.items.length >= 3;

      if (hasDelimiters || hasMultipleColumns) {
        candidateTableLines.push(line);
      }
    }

    // Group consecutive candidate lines into tables
    if (candidateTableLines.length >= 2) {
      let currentTable = [];
      let lastIdx = -2;

      const lineIndices = pageLines.map((l) => l);
      for (const candidate of candidateTableLines) {
        const idx = pageLines.indexOf(candidate);
        if (idx - lastIdx <= 2) {
          // Consecutive or near-consecutive — same table
          currentTable.push(candidate.items.map((i) => i.text.trim()));
        } else {
          // Gap — flush previous table if substantial
          if (currentTable.length >= 2) {
            tables.push({
              page: pageNum,
              rows: currentTable,
            });
          }
          currentTable = [candidate.items.map((i) => i.text.trim())];
        }
        lastIdx = idx;
      }
      // Flush remaining
      if (currentTable.length >= 2) {
        tables.push({
          page: pageNum,
          rows: currentTable,
        });
      }
    }
  }

  return {
    filename: file.name,
    type: 'pdf',
    pages: totalPages,
    text: fullText,
    tables,
  };
}

// ---------------------------------------------------------------------------
// Excel / CSV Parsing (via SheetJS — window.XLSX)
// ---------------------------------------------------------------------------

/**
 * Parse an Excel workbook or CSV file into structured sheet data.
 * @param {File} file
 * @returns {Promise<object>}
 */
async function parseSpreadsheet(file) {
  const XLSX = window.XLSX;
  if (!XLSX) {
    throw new Error('SheetJS (XLSX) library not loaded. Check CDN script in index.html.');
  }

  const arrayBuffer = await file.arrayBuffer();
  const ext = getExtension(file.name);

  const workbook = XLSX.read(arrayBuffer, {
    type: 'array',
    cellDates: true,
    cellNF: true,    // Preserve number formats
    cellStyles: false,
  });

  const sheets = workbook.SheetNames.map((sheetName) => {
    const worksheet = workbook.Sheets[sheetName];

    // Convert to array-of-arrays (preserving raw values where possible)
    const rawData = XLSX.utils.sheet_to_json(worksheet, {
      header: 1,
      defval: '',
      raw: false, // Get formatted strings to preserve number formatting
    });

    // Also get raw values for numeric processing
    const rawValues = XLSX.utils.sheet_to_json(worksheet, {
      header: 1,
      defval: '',
      raw: true,
    });

    if (rawData.length === 0) {
      return {
        name: sheetName,
        headers: [],
        rows: [],
        rawRows: [],
        rowCount: 0,
      };
    }

    // First row treated as headers
    const headers = rawData[0].map((h) => (h != null ? String(h).trim() : ''));
    const rows = rawData.slice(1);
    const rawRows = rawValues.slice(1);

    return {
      name: sheetName,
      headers,
      rows,
      rawRows,
      rowCount: rows.length,
    };
  });

  return {
    filename: file.name,
    type: 'spreadsheet',
    sheets,
  };
}

// ---------------------------------------------------------------------------
// Plain Text Parsing
// ---------------------------------------------------------------------------

/**
 * Read a plain text file.
 * @param {File} file
 * @returns {Promise<object>}
 */
async function parseText(file) {
  const content = await file.text();
  const lineCount = content.split('\n').length;

  return {
    filename: file.name,
    type: 'text',
    content,
    lineCount,
  };
}

// ---------------------------------------------------------------------------
// Document removal
// ---------------------------------------------------------------------------

/**
 * Remove a document by its source ID.
 * @param {number} id
 */
export function removeDocument(id) {
  const idx = uploadedDocuments.findIndex((d) => d.id === id);
  if (idx === -1) return;

  const removed = uploadedDocuments.splice(idx, 1)[0];
  renderFileList();
  updateSourceList();
  updateFooterSourceCount();

  document.dispatchEvent(
    new CustomEvent('document-removed', { detail: { document: removed } }),
  );

  showToast(`"${removed.filename}" removed.`, 'info');
}

// ---------------------------------------------------------------------------
// Data export for analysis module
// ---------------------------------------------------------------------------

/**
 * Return all successfully parsed documents in a format ready for the
 * analysis pipeline.
 * @returns {Array<object>}
 */
export function getParsedData() {
  return uploadedDocuments
    .filter((d) => d.status === 'ready' && d.parsedData)
    .map((d) => ({
      sourceId: d.id,
      filename: d.filename,
      ...d.parsedData,
    }));
}

// ---------------------------------------------------------------------------
// UI: File list rendering
// ---------------------------------------------------------------------------

function renderFileList() {
  const container = document.getElementById('file-list');
  if (!container) return;

  if (uploadedDocuments.length === 0) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = uploadedDocuments
    .map((doc) => {
      const cfg = TYPE_CONFIG[doc.ext] || TYPE_CONFIG.txt;
      const statusHtml = buildStatusBadge(doc.status, doc.error);
      const truncatedName =
        doc.filename.length > 28
          ? doc.filename.slice(0, 25) + '...'
          : doc.filename;

      return `
        <div class="flex items-center gap-2 p-2 text-xs bg-slate-50 rounded-md group" data-doc-id="${doc.id}">
          <span class="px-1.5 py-0.5 font-semibold ${cfg.bgClass} ${cfg.textClass} rounded text-[10px] flex-shrink-0">
            ${cfg.badge}
          </span>
          <span class="flex-1 truncate text-slate-700" title="${escapeHtml(doc.filename)}">
            ${escapeHtml(truncatedName)}
          </span>
          <span class="text-[10px] text-slate-400 flex-shrink-0">
            ${formatFileSize(doc.fileSize)}
          </span>
          ${statusHtml}
          <button
            class="text-slate-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
            data-remove-id="${doc.id}"
            title="Remove file"
          >&times;</button>
        </div>`;
    })
    .join('');

  // Wire remove buttons
  container.querySelectorAll('[data-remove-id]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = parseInt(btn.getAttribute('data-remove-id'), 10);
      removeDocument(id);
    });
  });
}

/**
 * Build the small status badge HTML for a document entry.
 */
function buildStatusBadge(status, errorMsg) {
  switch (status) {
    case 'parsing':
      return `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium bg-amber-50 text-amber-600 rounded flex-shrink-0">
        <span class="spinner" style="width:10px;height:10px;border-width:1.5px;"></span>
        Parsing...
      </span>`;
    case 'ready':
      return `<span class="px-1.5 py-0.5 text-[10px] font-medium bg-emerald-50 text-emerald-600 rounded flex-shrink-0">Ready</span>`;
    case 'error':
      return `<span class="px-1.5 py-0.5 text-[10px] font-medium bg-red-50 text-red-600 rounded flex-shrink-0" title="${escapeHtml(errorMsg || '')}">Error</span>`;
    default:
      return '';
  }
}

// ---------------------------------------------------------------------------
// UI: Source list in sidebar
// ---------------------------------------------------------------------------

function updateSourceList() {
  const container = document.getElementById('source-list');
  if (!container) return;

  const readyDocs = uploadedDocuments.filter((d) => d.status === 'ready');

  if (readyDocs.length === 0) {
    // Only reset to empty state if there are no EDGAR sources already rendered.
    // We check by looking for child elements that are not ours.
    const existingNonUpload = container.querySelectorAll('[data-source-type]:not([data-source-type="uploaded_document"])');
    if (existingNonUpload.length === 0) {
      container.innerHTML = '<p class="text-xs text-slate-400 italic py-2 text-center">No data sources loaded</p>';
    } else {
      // Just remove our upload entries
      container.querySelectorAll('[data-source-type="uploaded_document"]').forEach((el) => el.remove());
    }
    return;
  }

  // Remove existing upload source entries
  container.querySelectorAll('[data-source-type="uploaded_document"]').forEach((el) => el.remove());

  // Remove the empty-state message if present
  const emptyMsg = container.querySelector('p.text-xs.italic');
  if (emptyMsg) emptyMsg.remove();

  // Append source entries for each ready document
  for (const doc of readyDocs) {
    const cfg = TYPE_CONFIG[doc.ext] || TYPE_CONFIG.txt;

    const el = document.createElement('div');
    el.className = 'flex items-center gap-2 p-2 bg-slate-50 rounded-md text-xs';
    el.setAttribute('data-source-type', 'uploaded_document');
    el.setAttribute('data-source-id', String(doc.id));

    el.innerHTML = `
      <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0"></span>
      <svg class="w-3.5 h-3.5 text-slate-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125
             1.125 0 0113.5 7.125v-1.5a3.375 3.375 0
             00-3.375-3.375H8.25m2.25 0H5.625c-.621
             0-1.125.504-1.125 1.125v17.25c0
             .621.504 1.125 1.125 1.125h12.75c.621
             0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>
      </svg>
      <span class="flex-1 truncate text-slate-700">${escapeHtml(doc.filename)}</span>
      <span class="px-1.5 py-0.5 text-[10px] font-medium ${cfg.bgClass} ${cfg.textClass} rounded">${cfg.badge}</span>
    `;

    container.appendChild(el);
  }
}

// ---------------------------------------------------------------------------
// UI: Footer source count
// ---------------------------------------------------------------------------

function updateFooterSourceCount() {
  const el = document.getElementById('footer-source-count');
  if (!el) return;

  const readyCount = uploadedDocuments.filter((d) => d.status === 'ready').length;
  // Keep a simple label — other modules (edgar.js) may also update this
  const noun = readyCount === 1 ? 'source' : 'sources';

  el.innerHTML = `
    <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round"
        d="M20.25 6.375c0 2.278-3.694 4.125-8.25
           4.125S3.75 8.653 3.75 6.375m16.5
           0c0-2.278-3.694-4.125-8.25-4.125S3.75
           4.097 3.75 6.375m16.5 0v11.25c0
           2.278-3.694 4.125-8.25
           4.125s-8.25-1.847-8.25-4.125V6.375"/>
    </svg>
    ${readyCount} ${noun} loaded
  `;
}

// ---------------------------------------------------------------------------
// Toast notifications
// ---------------------------------------------------------------------------

/**
 * Display a toast notification.
 * @param {string} message
 * @param {'success'|'error'|'info'|'warning'} type
 */
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const colors = TOAST_COLORS[type] || TOAST_COLORS.info;
  const icon = TOAST_ICONS[type] || TOAST_ICONS.info;

  const toast = document.createElement('div');
  toast.className = `toast pointer-events-auto flex items-start gap-3 max-w-sm px-4 py-3 bg-white border ${colors.border} rounded-lg shadow-lg`;

  toast.innerHTML = `
    <span class="${colors.icon}">${icon}</span>
    <p class="text-sm text-slate-700 leading-snug flex-1">${escapeHtml(message)}</p>
    <button class="text-slate-400 hover:text-slate-600 ml-2 flex-shrink-0 text-lg leading-none">&times;</button>
  `;

  // Close button
  const closeBtn = toast.querySelector('button');
  closeBtn.addEventListener('click', () => dismissToast(toast));

  container.appendChild(toast);

  // Auto-dismiss after 4 seconds
  const timer = setTimeout(() => dismissToast(toast), 4000);
  toast._dismissTimer = timer;
}

/**
 * Animate out and remove a toast element.
 */
function dismissToast(toast) {
  if (!toast || !toast.parentNode) return;
  if (toast._dismissTimer) clearTimeout(toast._dismissTimer);

  toast.classList.remove('toast');
  toast.classList.add('toast-exit');

  toast.addEventListener('animationend', () => {
    if (toast.parentNode) toast.parentNode.removeChild(toast);
  });
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

/**
 * Get lowercase file extension from a filename.
 * @param {string} filename
 * @returns {string}
 */
function getExtension(filename) {
  const parts = filename.split('.');
  return parts.length > 1 ? parts.pop().toLowerCase() : '';
}

/**
 * Format byte size into human-readable string.
 * @param {number} bytes
 * @returns {string}
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Minimal HTML escaping to prevent XSS in rendered strings.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export { uploadedDocuments };
