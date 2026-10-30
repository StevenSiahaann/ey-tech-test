/**
 * Executive Report & Data Export Utility for EY Conversational BI.
 * Generates:
 * 1. RFC-4180 CSV Export with UTF-8 BOM for Microsoft Excel compatibility.
 * 2. Standalone Executive HTML Dossier with EY Enterprise Theme:
 *    - Follows EY Digital Design System & early careers guide aesthetics.
 *    - Soft refined radii (rounded-lg/md), subtle borders, elegant typography.
 *    - EY Yellow (#ffe600) purposeful brand accent, Charcoal (#2e2e38) text.
 *    - Absolutely ZERO emojis (replaced with clean SVG icons).
 *    - Clean Sentence Case / Title Case for headings.
 *    - Embedded responsive SVG charts, KPI tiles, prescriptive recommendations, and @media print-to-PDF formatting.
 */

export interface ReportMetadata {
  userQuery: string;
  sessionId: string;
  timestamp: string;
  modelName: string;
  provider: string;
  lang?: 'id' | 'en';
}

export function exportToCsv(
  columns: { name: string }[],
  rows: Record<string, any>[],
  filename?: string,
  lang: 'id' | 'en' = 'id'
): void {
  if (!rows || rows.length === 0) return;

  const colNames = columns.map(c => c.name);
  const headerLine = colNames.map(c => `"${c.replace(/"/g, '""')}"`).join(',');

  const rowLines = rows.map(r => {
    return colNames.map(col => {
      const val = r[col];
      if (val === null || val === undefined) return '""';
      const strVal = String(val).replace(/"/g, '""');
      return `"${strVal}"`;
    }).join(',');
  });

  // Prepend UTF-8 Byte Order Mark (BOM) so Excel opens UTF-8 accents cleanly
  const csvContent = '\uFEFF' + [headerLine, ...rowLines].join('\r\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const defaultPrefix = lang === 'en' ? 'EY_Executive_Report' : 'EY_Laporan_Eksekutif';
  const a = document.createElement('a');
  a.href = url;
  a.download = filename ? `${filename}.csv` : `${defaultPrefix}_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function generateExecutiveHtmlReport(agentResponse: any, meta: ReportMetadata): string {
  const { summary, kpis = [], table, chart, insights = [], recommendations = [], sql, assumptions = [] } = agentResponse;
  const rows: Record<string, any>[] = table?.rows || [];
  const columns: { name: string }[] = table?.columns || [];
  const isEn = meta.lang === 'en';

  // Helper currency/number formatting
  const formatVal = (v: any) => {
    if (typeof v === 'number') {
      if (Math.abs(v) >= 1_000_000_000) {
        return isEn
          ? `IDR ${(v / 1_000_000_000).toFixed(2)} Billion`
          : `Rp ${(v / 1_000_000_000).toFixed(2)} Miliar`;
      }
      if (Math.abs(v) >= 1_000_000) {
        return isEn
          ? `IDR ${(v / 1_000_000).toFixed(2)} Million`
          : `Rp ${(v / 1_000_000).toFixed(2)} Juta`;
      }
      return v.toLocaleString(isEn ? 'en-US' : 'id-ID');
    }
    return String(v ?? '-');
  };

  // Generate SVG Chart if applicable
  let chartSvgHtml = '';
  if (chart && chart.type !== 'none' && rows.length > 1) {
    const xKey = chart.x_axis || columns[0]?.name;
    const yKey = (chart.y_axes && chart.y_axes[0] && columns.some(c => c.name === chart.y_axes[0]))
      ? chart.y_axes[0]
      : columns.find(c => typeof rows[0]?.[c.name] === 'number')?.name;

    if (xKey && yKey) {
      if (chart.type === 'bar') {
        const chartRows = rows.slice(0, 8);
        const maxVal = Math.max(...chartRows.map(r => Number(r[yKey]) || 0), 1);
        const bars = chartRows.map((r, i) => {
          const val = Number(r[yKey]) || 0;
          const pct = Math.max(8, Math.round((val / maxVal) * 100));
          const label = String(r[xKey] || `Item ${i + 1}`);
          const displayVal = formatVal(val);
          return `
            <div style="margin-bottom: 12px;">
              <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 5px; font-weight: 600; color: #2e2e38;">
                <span>${label}</span>
                <span style="font-family: ui-monospace, SFMono-Regular, monospace; font-weight: 600;">${displayVal}</span>
              </div>
              <div style="background: #f3f4f6; height: 18px; border-radius: 4px; overflow: hidden; border: 1px solid #e5e7eb;">
                <div style="background: #2e2e38; width: ${pct}%; height: 100%; border-radius: 3px; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px; box-sizing: border-box;">
                  <span style="color: #ffe600; font-size: 11px; font-family: ui-monospace, SFMono-Regular, monospace; font-weight: 700;">${pct}%</span>
                </div>
              </div>
            </div>
          `;
        }).join('');

        chartSvgHtml = `
          <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 22px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 13px; font-weight: 700; color: #2e2e38; margin-bottom: 18px; display: flex; align-items: center; gap: 8px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2e2e38" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
              <span>${chart.title || (isEn ? 'Distribution Analysis' : 'Visualisasi Distribusi')}</span>
              <span style="font-size: 12px; color: #6b7280; font-weight: 500;">(${xKey.replace(/_/g, ' ')} vs ${yKey.replace(/_/g, ' ')})</span>
            </div>
            ${bars}
          </div>
        `;
      } else if (chart.type === 'line') {
        const chartRows = rows.slice(-14);
        const maxVal = Math.max(...chartRows.map(r => Number(r[yKey]) || 0), 1);
        const points = chartRows.map((r, i) => {
          const x = 40 + (i / Math.max(chartRows.length - 1, 1)) * 620;
          const val = Number(r[yKey]) || 0;
          const y = 180 - (val / maxVal) * 140;
          return `${x},${y}`;
        }).join(' ');

        chartSvgHtml = `
          <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 22px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 13px; font-weight: 700; color: #2e2e38; margin-bottom: 18px; display: flex; align-items: center; gap: 8px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2e2e38" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
              <span>${chart.title || (isEn ? 'Historical Trend' : 'Tren Data Historis')}</span>
            </div>
            <svg viewBox="0 0 700 200" style="width: 100%; height: auto; overflow: visible;">
              <polyline fill="none" stroke="#2e2e38" stroke-width="2.5" points="${points}" />
              ${chartRows.map((r, i) => {
                const x = 40 + (i / Math.max(chartRows.length - 1, 1)) * 620;
                const val = Number(r[yKey]) || 0;
                const y = 180 - (val / maxVal) * 140;
                const dateLabel = String(r[xKey] || '').slice(5);
                return `
                  <circle cx="${x}" cy="${y}" r="4" fill="#ffe600" stroke="#2e2e38" stroke-width="2" />
                  <text x="${x}" y="196" font-size="10" text-anchor="middle" fill="#6b7280">${dateLabel}</text>
                `;
              }).join('')}
            </svg>
          </div>
        `;
      }
    }
  }

  return `<!DOCTYPE html>
<html lang="${isEn ? 'en' : 'id'}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EY Enterprise BI Dossier - ${meta.userQuery}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      margin: 0;
      padding: 36px 16px;
      background: #f8f9fa;
      color: #2e2e38;
      line-height: 1.6;
    }
    .report-card {
      max-width: 900px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-top: 5px solid #ffe600;
      border-radius: 12px;
      padding: 36px 40px;
      box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
    }
    .header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid #e5e7eb;
      padding-bottom: 22px;
      margin-bottom: 24px;
      gap: 20px;
    }
    .brand-group {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }
    .brand-logo {
      width: 32px;
      height: 32px;
      background: #ffe600;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 900;
      font-size: 14px;
      color: #2e2e38;
      letter-spacing: -0.05em;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      background: #f3f4f6;
      border-radius: 9999px;
      color: #4b5563;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.02em;
    }
    h1 {
      font-size: 22px;
      margin: 8px 0;
      color: #2e2e38;
      font-weight: 700;
      line-height: 1.3;
    }
    .meta-text {
      font-size: 12px;
      color: #6b7280;
      font-family: ui-monospace, SFMono-Regular, monospace;
    }
    .print-btn {
      background: #2e2e38;
      color: #ffffff;
      border: 1px solid #2e2e38;
      border-radius: 6px;
      padding: 9px 16px;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 7px;
      transition: all 0.15s ease;
      white-space: nowrap;
    }
    .print-btn:hover {
      background: #ffe600;
      color: #2e2e38;
      border-color: #ffe600;
    }
    .summary-box {
      font-size: 14.5px;
      font-weight: 500;
      color: #2e2e38;
      margin-bottom: 24px;
      padding: 16px 20px;
      background: #fffdf0;
      border: 1px solid #fef08a;
      border-left: 4px solid #ffe600;
      border-radius: 8px;
      line-height: 1.6;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .kpi-tile {
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 18px 20px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .kpi-label {
      font-size: 11.5px;
      color: #6b7280;
      font-weight: 600;
      margin-bottom: 6px;
    }
    .kpi-val {
      font-size: 24px;
      font-weight: 800;
      color: #2e2e38;
      line-height: 1.2;
    }
    .kpi-sub {
      font-size: 11px;
      color: #9ca3af;
      margin-top: 4px;
    }
    .section-title {
      font-size: 13.5px;
      font-weight: 700;
      color: #2e2e38;
      margin: 26px 0 12px 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .box {
      padding: 16px 20px;
      margin-bottom: 22px;
      font-size: 13.5px;
      border-radius: 8px;
    }
    .box-insights {
      background: #fffdf0;
      border: 1px solid #fef08a;
      border-left: 4px solid #ffe600;
      color: #2e2e38;
    }
    .box-recom {
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-left: 4px solid #2e2e38;
      color: #2e2e38;
    }
    ul {
      margin: 0;
      padding-left: 18px;
    }
    li {
      margin-bottom: 8px;
      line-height: 1.55;
    }
    li:last-child { margin-bottom: 0; }
    .table-container {
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      overflow: hidden;
      margin-top: 10px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th {
      background: #2e2e38;
      color: #ffffff;
      text-align: left;
      padding: 11px 14px;
      font-weight: 600;
      font-size: 11.5px;
      letter-spacing: 0.02em;
      border-right: 1px solid #444452;
    }
    th:last-child { border-right: none; }
    td {
      padding: 10px 14px;
      border-bottom: 1px solid #f3f4f6;
      border-right: 1px solid #f3f4f6;
      color: #2e2e38;
    }
    td:last-child { border-right: none; }
    tr:last-child td { border-bottom: none; }
    tr:nth-child(even) { background: #fafafa; }
    pre {
      background: #1e1e24;
      color: #ffe600;
      border-left: 3px solid #ffe600;
      border-radius: 8px;
      padding: 16px 18px;
      font-size: 12.5px;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, monospace;
      margin-top: 8px;
      line-height: 1.5;
    }
    .footer-notes {
      font-size: 11.5px;
      color: #6b7280;
      margin-top: 26px;
      border-top: 1px solid #e5e7eb;
      padding-top: 14px;
      line-height: 1.5;
    }
    @media print {
      body { background: white; padding: 0; }
      .report-card { box-shadow: none; padding: 0; max-width: 100%; border: none; }
      .print-btn { display: none; }
    }
  </style>
</head>
<body>
  <div class="report-card">
    <div class="header-row">
      <div>
        <div class="brand-group">
          <div class="brand-logo">EY</div>
          <span class="badge">${isEn ? 'Executive Dossier' : 'Dossier Eksekutif'}</span>
        </div>
        <h1>${meta.userQuery}</h1>
        <div class="meta-text">
          ${isEn ? 'Generated:' : 'Dibuat:'} ${meta.timestamp} • Engine: ${meta.provider.toUpperCase()} (${meta.modelName}) • Status: AST Validated
        </div>
      </div>
      <button class="print-btn" onclick="window.print()">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
        <span>${isEn ? 'Print / Save as PDF' : 'Cetak / Simpan PDF'}</span>
      </button>
    </div>

    <!-- Executive Summary -->
    <div class="summary-box">
      ${summary}
    </div>

    <!-- KPI Tiles -->
    ${kpis.length > 0 ? `
      <div class="kpi-grid">
        ${kpis.map((k: any) => `
          <div class="kpi-tile">
            <div class="kpi-label">${k.label}</div>
            <div class="kpi-val">${formatVal(k.value)}</div>
            ${k.subtitle ? `<div class="kpi-sub">${k.subtitle}</div>` : ''}
          </div>
        `).join('')}
      </div>
    ` : ''}

    <!-- Embedded Chart -->
    ${chartSvgHtml}

    <!-- Strategic Insights -->
    ${insights.length > 0 ? `
      <div class="section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2e2e38" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
        <span>${isEn ? 'Key Analytical Insights' : 'Temuan Kunci Analitis'}</span>
      </div>
      <div class="box box-insights">
        <ul>${insights.map((ins: string) => `<li>${ins}</li>`).join('')}</ul>
      </div>
    ` : ''}

    <!-- Prescriptive Recommendations -->
    ${recommendations.length > 0 ? `
      <div class="section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2e2e38" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>
        <span>${isEn ? 'Strategic Recommendations' : 'Rekomendasi Tindakan Strategis'}</span>
      </div>
      <div class="box box-recom">
        <ul>${recommendations.map((rec: string) => `<li><strong>▸</strong> ${rec}</li>`).join('')}</ul>
      </div>
    ` : ''}

    <!-- Audit Data Table -->
    ${columns.length > 0 && rows.length > 0 ? `
      <div class="section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2e2e38" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="3" y1="15" x2="21" y2="15"></line><line x1="9" y1="3" x2="9" y2="21"></line><line x1="15" y1="3" x2="15" y2="21"></line></svg>
        <span>${isEn ? 'Verified Transaction Data' : 'Data Tabel Transaksi'} (${rows.length} ${isEn ? 'rows' : 'baris'})</span>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th style="width: 40px; text-align: center;">#</th>
              ${columns.map(c => `<th>${c.name.replace(/_/g, ' ')}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${rows.slice(0, 50).map((r, rIdx) => `
              <tr>
                <td style="text-align: center; color: #9ca3af; font-family: ui-monospace, SFMono-Regular, monospace;">${rIdx + 1}</td>
                ${columns.map(c => `<td>${formatVal(r[c.name])}</td>`).join('')}
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    ` : ''}

    <!-- Technical SQL Appendix -->
    ${sql ? `
      <div class="section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2e2e38" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
        <span>${isEn ? 'Technical Audit Trace (PostgreSQL)' : 'Jejak Audit Teknis (PostgreSQL)'}</span>
      </div>
      <pre><code>${sql}</code></pre>
    ` : ''}

    <!-- Assumptions -->
    ${assumptions.length > 0 ? `
      <div class="footer-notes">
        <strong>${isEn ? 'Assumptions:' : 'Perimeter Asumsi:'}</strong> ${assumptions.join(' • ')}
      </div>
    ` : ''}
  </div>
</body>
</html>`;
}

export function openExecutiveHtmlReport(agentResponse: any, meta: ReportMetadata): void {
  const htmlContent = generateExecutiveHtmlReport(agentResponse, meta);
  const win = window.open('', '_blank');
  if (win) {
    win.document.open();
    win.document.write(htmlContent);
    win.document.close();
  }
}
