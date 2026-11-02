import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  Plus,
  Send,
  TerminalSquare,
  Table as TableIcon,
  Database,
  AlertCircle,
  Settings,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Terminal,
  Download,
  FileText,
  FileJson,
  Code,
  Menu,
  X,
  TrendingUp,
  BarChart3,
  Trash2,
  Zap,
  Target,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  ThumbsUp,
  ThumbsDown
} from 'lucide-react';
import { exportToCsv, openExecutiveHtmlReport } from './utils/executiveReport';

// --- TYPES ---
interface StepEvent {
  node: string;
  title: string;
  description: string;
  detail?: string;
  elapsed_ms?: number;
  status?: 'done' | 'active';
}

interface KPICard {
  label: string;
  value: any;
  format: string;
  subtitle?: string;
}

interface TableData {
  columns: { name: string; type: string }[];
  rows: Record<string, any>[];
  truncated?: boolean;
}

interface ChartConfig {
  type: 'bar' | 'line' | 'pie' | 'none';
  x_axis?: string;
  y_axes?: string[];
  title?: string;
}

interface AgentResponse {
  type: string;
  language?: string;
  summary: string;
  kpis?: KPICard[];
  table?: TableData;
  chart?: ChartConfig;
  insights?: string[];
  recommendations?: string[];
  sql?: string;
  assumptions?: string[];
  clarification?: {
    question?: string;
    options?: { label: string; value: string }[];
  };
  trace?: {
    steps?: StepEvent[];
    total_duration_ms?: number;
    plan?: any;
    row_count?: number;
    [key: string]: any;
  };
}

interface ChatTurn {
  id: string;
  userMessage: string;
  agentResponse?: AgentResponse;
  isLoading?: boolean;
  currentStep?: string;
  steps: StepEvent[];
}

interface SessionRecord {
  id: string;
  title: string;
  updatedAt: number;
  turns: ChatTurn[];
}

// --- BILINGUAL DICTIONARY (ID / EN) ---
const TRANSLATIONS = {
  id: {
    appTitle: "Data Agent AI",
    appSubtitle: "Enterprise NLQ Analytics",
    newChat: "Sesi Baru",
    chatHistory: "Riwayat Sesi Chat",
    untitledSession: "Sesi Tanpa Judul",
    newSession: "Sesi Baru",
    deleteSession: "Hapus sesi ini",
    quickStarters: "Contoh Pertanyaan Cepat",
    quickQueries: [
      "GMV MTD untuk region Jawa?",
      "Revenue dan margin MTD untuk FMCG di Jawa?",
      "Top 5 produk berdasarkan revenue bulan lalu?",
      "Channel dengan revenue tertinggi di Q1 2025?",
      "Cancel rate bulan ini?",
      "Segment customer dengan margin tertinggi YTD?",
      "Revenue POS vs E-commerce minggu ini?",
      "Store di Jakarta dengan revenue tertinggi bulan ini?",
      "Revenue anomaly: drop >30% vs 7-day average"
    ],
    poweredBy: "Powered by EY Enterprise BI",
    dbConnected: "Database Connected",
    welcomeTitle: "E-Commerce & Retail Conversational Data Agent",
    welcomeDesc: "Tanyakan metrik bisnis dalam Bahasa Indonesia atau Inggris. Sistem otomatis memetakan pertanyaan ke Semantic Layer, memvalidasi SQL AST, menerapkan batas keamanan read-only, dan menyajikan rekomendasi analitis.",
    personaHeader: "Pilih Persona & Pertanyaan Awal",
    personas: [
      {
        title: "Executive & Finance",
        desc: "Pemantauan profitabilitas, GMV, dan kesehatan omset seluruh kanal.",
        query: "GMV MTD untuk region Jawa?"
      },
      {
        title: "Merchandising & Product",
        desc: "Performa penjualan SKU, kategori terlaris, dan evaluasi produk lambat.",
        query: "Top 5 produk berdasarkan revenue bulan lalu?"
      },
      {
        title: "Operations & Risk Auditor",
        desc: "Pemantauan tingkat pembatalan (cancel rate), anomali penurunan omset, dan store.",
        query: "Cancel rate bulan ini?"
      }
    ],
    you: "You",
    dataAgent: "Data Agent",
    processing: "Memproses query analitis...",
    step: "Langkah",
    hideReasoning: "Sembunyikan Alur Penalaran",
    showReasoning: "Alur Penalaran & Observabilitas ({count} Langkah{time})",
    executionLog: "Execution Log Trace",
    structuredPlan: "Structured Query Plan (Deterministic Contract)",
    finalSql: "Query SQL Final (Validated AST)",
    dataTab: "Data",
    sqlTab: "SQL",
    distribution: "Distribusi",
    insightsTitle: "Temuan Analitis",
    recommendationsTitle: "Rekomendasi Tindakan Strategis",
    rowsFound: "baris data ditemukan",
    showingRows: "Menampilkan {displayed} dari {total} baris data",
    collapseRows: "Ciutkan ke 10 baris",
    showAllRows: "Tampilkan semua ({total} baris)",
    assumptionsPrefix: "Asumsi:",
    assumptionsDefault: "Evaluasi data berdasarkan rentang waktu transaksi historis.",
    downloadCsv: "Unduh CSV",
    downloadCsvTitle: "Unduh data dalam format CSV RFC-4180 (Kompatibel dengan Microsoft Excel)",
    execReport: "Laporan Eksekutif",
    execReportTitle: "Buka Executive Dossier interaktif (Dilengkapi grafik, KPI, dan format Cetak ke PDF)",
    inputPlaceholder: "Ajukan pertanyaan bisnis tentang data Anda (contoh: GMV MTD Jawa, Top 5 Produk)...",
    sendTooltip: "Kirim Pertanyaan",
    llmConfig: "Konfigurasi LLM",
    provider: "Provider:",
    model: "Model:",
    recommendedFast: "Rekomendasi Cepat",
    testConnection: "Test Connection",
    testing: "Menguji...",
    connected: "Connected",
    notConnected: "Not Connected",
    schemaAware: "Schema aware: customers, stores, products, orders, order_items",
    noSqlExecuted: "-- Tidak ada query SQL yang dieksekusi."
  },
  en: {
    appTitle: "Data Agent AI",
    appSubtitle: "Enterprise NLQ Analytics",
    newChat: "New Chat",
    chatHistory: "Chat History",
    untitledSession: "Untitled Session",
    newSession: "New Session",
    deleteSession: "Delete this session",
    quickStarters: "Quick Starter Queries",
    quickQueries: [
      "MTD GMV for Java region?",
      "MTD Revenue and margin for FMCG in Java?",
      "Top 5 products by revenue last month?",
      "Channel with highest revenue in Q1 2025?",
      "Cancel rate this month?",
      "Customer segment with highest margin YTD?",
      "POS vs E-commerce revenue this week?",
      "Store in Jakarta with highest revenue this month?",
      "Revenue anomaly: drop >30% vs 7-day average"
    ],
    poweredBy: "Powered by EY Enterprise BI",
    dbConnected: "Database Connected",
    welcomeTitle: "E-Commerce & Retail Conversational Data Agent",
    welcomeDesc: "Ask business metrics questions in natural language. The system automatically maps queries to the Semantic Layer, validates SQL AST, enforces read-only security boundaries, and provides prescriptive analytics.",
    personaHeader: "Select Persona & Starter Query",
    personas: [
      {
        title: "Executive & Finance",
        desc: "Monitor profitability, GMV trends, and revenue health across all sales channels.",
        query: "MTD GMV for Java region?"
      },
      {
        title: "Merchandising & Product",
        desc: "SKU sales performance, top revenue contributors, and slow-moving product evaluations.",
        query: "Top 5 products by revenue last month?"
      },
      {
        title: "Operations & Risk Auditor",
        desc: "Order cancellation rate tracking, sudden revenue anomalies, and store-level audits.",
        query: "Cancel rate this month?"
      }
    ],
    you: "You",
    dataAgent: "Data Agent",
    processing: "Processing analytical query...",
    step: "Step",
    hideReasoning: "Hide Reasoning Process",
    showReasoning: "Reasoning & Observability Process ({count} Steps{time})",
    executionLog: "Execution Log Trace",
    structuredPlan: "Structured Query Plan (Deterministic Contract)",
    finalSql: "Final Validated SQL Query",
    dataTab: "Data",
    sqlTab: "SQL",
    distribution: "Distribution",
    insightsTitle: "Analytical Insights",
    recommendationsTitle: "Strategic Recommendations",
    rowsFound: "rows found",
    showingRows: "Showing {displayed} of {total} rows",
    collapseRows: "Collapse to 10 rows",
    showAllRows: "Show all ({total} rows)",
    assumptionsPrefix: "Assumptions:",
    assumptionsDefault: "Data evaluated based on historical transaction timeframe.",
    downloadCsv: "Download CSV",
    downloadCsvTitle: "Download data in RFC-4180 CSV format (Excel compatible)",
    execReport: "Executive Report",
    execReportTitle: "Open interactive Executive Dossier (Includes charts, KPIs, and Print-to-PDF format)",
    inputPlaceholder: "Ask a business question about your data (e.g. Java MTD GMV, Top 5 Products)...",
    sendTooltip: "Send Query",
    llmConfig: "LLM Configuration",
    provider: "Provider:",
    model: "Model:",
    recommendedFast: "Fast Recommended",
    testConnection: "Test Connection",
    testing: "Testing...",
    connected: "Connected",
    notConnected: "Not Connected",
    schemaAware: "Schema aware: customers, stores, products, orders, order_items",
    noSqlExecuted: "-- No SQL query executed."
  }
};

// --- CURRENCY & FORMATTING HELPERS ---
const formatCurrency = (val: number, lang: 'id' | 'en' = 'id') => {
  if (Math.abs(val) >= 1_000_000_000) {
    return lang === 'en'
      ? `IDR ${(val / 1_000_000_000).toFixed(2)} Billion`
      : `Rp ${(val / 1_000_000_000).toFixed(2)} Miliar`;
  } else if (Math.abs(val) >= 1_000_000) {
    return lang === 'en'
      ? `IDR ${(val / 1_000_000).toFixed(2)} Million`
      : `Rp ${(val / 1_000_000).toFixed(2)} Juta`;
  }
  return lang === 'en'
    ? `IDR ${Number(val).toLocaleString('en-US')}`
    : `Rp ${Number(val).toLocaleString('id-ID')}`;
};

const formatValue = (val: any, colName: string = '', lang: 'id' | 'en' = 'id'): string => {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'number') {
    const isCurrency = colName.includes('revenue') || colName.includes('gmv') || colName.includes('margin') || colName.includes('cogs') || colName.includes('price');
    if (isCurrency) return formatCurrency(val, lang);
    if (colName.includes('rate') || colName.includes('pct') || colName.includes('percentage')) return `${val}%`;
    return val.toLocaleString(lang === 'en' ? 'en-US' : 'id-ID');
  }
  return String(val);
};

// --- AGENT MESSAGE CARD COMPONENT ---
interface AgentMessageCardProps {
  turn: ChatTurn;
  sessionId: string;
  lang: 'id' | 'en';
  t: typeof TRANSLATIONS['id'];
  onExportCsv: () => void;
  onExportHtml: () => void;
  onSelectOption?: (queryText: string) => void;
}

const AgentMessageCard: React.FC<AgentMessageCardProps> = ({ turn, sessionId, lang, t, onExportCsv, onExportHtml, onSelectOption }) => {
  const [activeTab, setActiveTab] = useState<'table' | 'sql'>('table');
  const [isThinkingExpanded, setIsThinkingExpanded] = useState<boolean>(false);
  const [isTableExpanded, setIsTableExpanded] = useState<boolean>(false);
  const [feedbackScore, setFeedbackScore] = useState<number | null>(null);

  const handleFeedback = async (score: number) => {
    setFeedbackScore(score);
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          score
        })
      });
    } catch (e) {}
  };

  const res = turn.agentResponse;
  if (!res) return null;

  const isConversationalCard =
    res.type === 'discussion' ||
    res.type === 'clarification' ||
    res.type === 'refusal' ||
    ((!res.kpis || res.kpis.length === 0) && (!res.table?.rows || res.table.rows.length === 0));

  const displaySteps = (turn.steps && turn.steps.length > 0)
    ? turn.steps
    : (res.trace?.steps || []);
  const totalMs = res.trace?.total_duration_ms ??
    (displaySteps.length > 0 ? displaySteps[displaySteps.length - 1].elapsed_ms : undefined);
  const plan = res.trace?.plan;

  // Extract primary metric
  const primaryKpi = res.kpis && res.kpis.length > 0 ? res.kpis[0] : null;
  const secondaryKpis = res.kpis && res.kpis.length > 1 ? res.kpis.slice(1) : [];

  let metricDisplay = primaryKpi
    ? (primaryKpi.format === 'currency_idr' && typeof primaryKpi.value === 'number'
        ? formatCurrency(primaryKpi.value, lang)
        : primaryKpi.format === 'percentage'
        ? `${primaryKpi.value}%`
        : String(primaryKpi.value))
    : (res.summary || (lang === 'en' ? 'Analysis Result' : 'Hasil Analisis'));

  let metricLabel = primaryKpi
    ? primaryKpi.label
    : (res.table?.rows ? `${res.table.rows.length} ${t.rowsFound}` : (lang === 'en' ? 'Business Analysis' : 'Analisis Bisnis'));

  const tableRows = res.table?.rows || [];
  const tableCols = res.table?.columns || [];
  const displayedRows = isTableExpanded ? tableRows : tableRows.slice(0, 10);

  // Auto-Chart parameters
  const validNumCol = (res.chart?.y_axes?.[0] && tableCols.some(c => c.name === res.chart?.y_axes?.[0]))
    ? res.chart.y_axes[0]
    : tableCols.find(c => typeof tableRows[0]?.[c.name] === 'number')?.name;
  const numCol = validNumCol;
  const catCol = res.chart?.x_axis || tableCols.find(c => c.name !== numCol)?.name || tableCols[0]?.name;
  const chartRows = tableRows.slice(0, 8);
  const maxVal = Math.max(...chartRows.map(r => Number(r[numCol || '']) || 0), 1);

  const reasoningLabel = isThinkingExpanded
    ? t.hideReasoning
    : t.showReasoning
        .replace('{count}', String(displaySteps.length))
        .replace('{time}', totalMs ? ` / ${(totalMs / 1000).toFixed(2)}s` : '');

  return (
    <div className="w-full max-w-4xl flex flex-col mb-6 mt-1">
      {/* 1. Thinking Process & Observability Accordion */}
      {displaySteps.length > 0 && (
        <div className="mb-3">
          <button
            onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
            className="flex items-center gap-2 text-[13px] font-semibold text-[#2e2e38] bg-transparent hover:text-gray-600 transition-colors py-1 group cursor-pointer"
          >
            <span className="w-5 h-5 rounded-md flex items-center justify-center bg-gray-200 group-hover:bg-gray-300 transition-colors">
              {isThinkingExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </span>
            <span>{reasoningLabel}</span>
          </button>

          {isThinkingExpanded && (
            <div className="mt-2.5 bg-white border border-[#e5e7eb] rounded-xl shadow-xs overflow-hidden flex flex-col">
              {/* Execution Log Trace */}
              <div className="p-5 md:p-6 bg-[#fafafa] border-b border-[#e5e7eb]">
                <h6 className="font-semibold text-[#2e2e38] mb-4 text-[13px] flex items-center gap-2">
                  <Terminal size={15} className="text-[#2e2e38]" />
                  <span>{t.executionLog}</span>
                </h6>
                <div className="space-y-4">
                  {displaySteps.map((step, idx) => (
                    <div key={idx} className="relative">
                      {idx !== displaySteps.length - 1 && (
                        <div className="absolute left-[10px] top-6 bottom-[-20px] w-[2px] bg-[#e5e7eb]"></div>
                      )}
                      <div className="flex items-start gap-3.5">
                        <div className="w-5 h-5 rounded-full bg-white border-2 border-[#2e2e38] flex items-center justify-center shrink-0 z-10 mt-0.5 shadow-2xs">
                          <CheckCircle2 size={12} className="text-[#2e2e38]" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2.5 mb-1">
                            <span className="font-semibold text-[#2e2e38] text-[13.5px]">{step.title || step.node}</span>
                            {step.elapsed_ms != null && (
                              <span className="text-[11px] bg-gray-100 text-gray-700 px-2 py-0.5 rounded font-mono border border-gray-200">
                                +{step.elapsed_ms}ms
                              </span>
                            )}
                          </div>
                          <p className="text-[12.5px] text-gray-600 mb-2 leading-relaxed">{step.description}</p>
                          {step.detail && (
                            <div className="bg-[#f8f9fa] border border-[#e2e4e8] border-l-3 border-l-[#ffe600] p-3 text-[#2e2e38] font-mono text-[12px] rounded-r-md overflow-x-auto shadow-2xs leading-relaxed">
                              {step.detail}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Structured Query Plan JSON */}
              {plan && (
                <div className="p-5 md:p-6 bg-white border-b border-[#e5e7eb]">
                  <h6 className="font-semibold text-[#2e2e38] mb-3 text-[13px] flex items-center gap-2">
                    <FileJson size={15} className="text-[#2e2e38]" />
                    <span>{t.structuredPlan}</span>
                  </h6>
                  <div className="bg-[#f8f9fa] p-4 text-[#2e2e38] font-mono text-[12px] overflow-x-auto border border-[#e5e7eb] rounded-lg">
                    <pre>{JSON.stringify(plan, null, 2)}</pre>
                  </div>
                </div>
              )}

              {/* Validated AST / Final SQL Preview */}
              {res.sql && (
                <div className="p-5 md:p-6 bg-white">
                  <h6 className="font-semibold text-[#2e2e38] mb-3 text-[13px] flex items-center gap-2">
                    <Code size={15} className="text-[#2e2e38]" />
                    <span>{t.finalSql}</span>
                  </h6>
                  <div className="bg-[#1e1e24] p-4 text-[#ffe600] font-mono text-[12.5px] overflow-x-auto whitespace-pre-wrap rounded-lg border border-[#2e2e38]">
                    {res.sql}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 2. Main Card Content (Soft, Modernized EY Style) */}
      <div className="bg-white border border-[#e5e7eb] border-t-3 border-t-[#ffe600] rounded-xl shadow-xs hover:shadow-sm transition-shadow w-full overflow-hidden">
        {/* Header / Metric or Conversational Section */}
        <div className="p-5 md:p-6 border-b border-[#e5e7eb] flex flex-col md:flex-row items-start md:items-center justify-between gap-4 bg-white">
          <div className="flex-1">
            {isConversationalCard ? (
              <div>
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#fffdf0] border border-[#f0e08a] text-[#2e2e38] text-[11.5px] font-semibold mb-2.5">
                  <Sparkles size={13} className="text-[#2e2e38]" />
                  <span>
                    {res.type === 'discussion'
                      ? (lang === 'en' ? 'Analytical Discussion & Advisory' : 'Diskusi & Konsultasi Analitik')
                      : res.type === 'clarification'
                      ? (lang === 'en' ? 'Proactive Parameter Confirmation' : 'Konfirmasi Parameter Analisis')
                      : res.type === 'refusal'
                      ? (lang === 'en' ? 'Domain Scope Guardrail' : 'Batas Cakupan Analitik')
                      : metricLabel}
                  </span>
                </div>
                <p className="text-[15.5px] md:text-[16.5px] font-semibold text-[#2e2e38] leading-relaxed">
                  {res.summary}
                </p>
              </div>
            ) : (
              <>
                <h3 className="text-[22px] md:text-[28px] font-bold text-[#2e2e38] leading-tight mb-1">
                  {metricDisplay}
                </h3>
                <p className="text-[12px] md:text-[13px] text-gray-500 font-medium">
                  {metricLabel}
                </p>
                {secondaryKpis.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {secondaryKpis.map((kpi, kIdx) => (
                      <div key={kIdx} className="bg-[#f8f9fa] border border-[#e5e7eb] rounded-md px-3 py-1 text-[12px] text-[#2e2e38]">
                        <span className="text-gray-500 font-medium">{kpi.label}: </span>
                        <span className="font-semibold font-mono">
                          {kpi.format === 'currency_idr' && typeof kpi.value === 'number'
                            ? formatCurrency(kpi.value, lang)
                            : String(kpi.value)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {(!isConversationalCard || res.sql || tableRows.length > 0) && (
            <div className="flex bg-[#f3f4f6] p-1 rounded-lg border border-[#e5e7eb] w-full md:w-auto shrink-0">
              <button
                onClick={() => setActiveTab('table')}
                className={`flex-1 md:flex-none px-3.5 py-1.5 text-[12.5px] font-semibold rounded-md flex items-center justify-center md:justify-start gap-2 transition-colors cursor-pointer ${
                  activeTab === 'table' ? 'bg-white text-[#2e2e38] shadow-xs' : 'text-gray-600 hover:text-[#2e2e38]'
                }`}
              >
                <TableIcon size={15} />
                <span>{t.dataTab}</span>
              </button>
              <button
                onClick={() => setActiveTab('sql')}
                className={`flex-1 md:flex-none px-3.5 py-1.5 text-[12.5px] font-semibold rounded-md flex items-center justify-center md:justify-start gap-2 transition-colors cursor-pointer ${
                  activeTab === 'sql' ? 'bg-white text-[#2e2e38] shadow-xs' : 'text-gray-600 hover:text-[#2e2e38]'
                }`}
              >
                <TerminalSquare size={15} />
                <span>{t.sqlTab}</span>
              </button>
            </div>
          )}
        </div>

        {/* Tab Content */}
        <div className="p-0 bg-white w-full">
          {activeTab === 'table' && (
            <div className="overflow-x-auto w-full">
              {/* Auto-Chart Visualizer (Only when comparing 2 or more entities) */}
              {tableRows.length > 1 && numCol && catCol && res.chart?.type !== 'none' && (
                <div className="p-5 md:p-6 border-b border-[#e5e7eb] bg-[#fafafa]">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <BarChart3 size={16} className="text-[#2e2e38]" />
                      <span className="font-semibold text-[13px] text-[#2e2e38]">
                        {res.chart?.title || `${t.distribution} ${numCol.replace(/_/g, ' ')}`}
                      </span>
                    </div>
                    <span className="text-[11.5px] text-gray-500 font-mono">
                      {catCol.replace(/_/g, ' ')} vs {numCol.replace(/_/g, ' ')}
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    {chartRows.map((r, rIdx) => {
                      const val = Number(r[numCol]) || 0;
                      const pct = Math.max(4, Math.round((val / maxVal) * 100));
                      const label = String(r[catCol] ?? '-');
                      const formattedVal = formatValue(val, numCol, lang);

                      return (
                        <div key={rIdx} className="flex items-center gap-3 text-[13px]">
                          <span className="w-36 md:w-48 truncate font-medium text-[#2e2e38]" title={label}>
                            {label}
                          </span>
                          <div className="flex-1 bg-gray-200 h-4.5 rounded overflow-hidden border border-gray-300">
                            <div
                              className="bg-[#2e2e38] h-full rounded-sm flex items-center justify-end pr-2 transition-all duration-500"
                              style={{ width: `${pct}%`, minWidth: '24px' }}
                            >
                              <span className="text-[10px] text-[#ffe600] font-mono font-bold">{pct}%</span>
                            </div>
                          </div>
                          <span className="w-28 md:w-36 text-right font-mono font-semibold text-[#2e2e38]">
                            {formattedVal}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Analytical Insights */}
              {res.insights && res.insights.length > 0 && (
                <div className="p-5 md:p-6 border-b border-[#e5e7eb] bg-[#fffdf0]">
                  <h6 className="text-[13px] font-semibold text-[#2e2e38] mb-3 flex items-center gap-2">
                    <TrendingUp size={15} className="text-[#2e2e38]" />
                    <span>{t.insightsTitle}</span>
                  </h6>
                  <ul className="space-y-2">
                    {res.insights.map((insight, idx) => (
                      <li key={idx} className="flex items-start gap-3 text-[13.5px] text-[#2e2e38] leading-relaxed">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#2e2e38] mt-2 shrink-0"></div>
                        <span>{insight}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Prescriptive Strategic Recommendations */}
              {res.recommendations && res.recommendations.length > 0 && (
                <div className="p-5 md:p-6 border-b border-[#e5e7eb] bg-[#f9fafb]">
                  <h6 className="text-[13px] font-semibold text-[#2e2e38] mb-3 flex items-center gap-2">
                    <Target size={15} className="text-[#2e2e38]" />
                    <span>{t.recommendationsTitle}</span>
                  </h6>
                  <ul className="space-y-2">
                    {res.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-2.5 text-[13.5px] text-[#2e2e38] leading-relaxed">
                        <span className="text-gray-500 font-bold mt-0.5">▸</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Interactive Clarification & Follow-Up Action Chips */}
              {res.clarification?.options && res.clarification.options.length > 0 && (
                <div className="p-5 md:p-6 border-b border-[#e5e7eb] bg-white">
                  {res.clarification.question && (
                    <div className="text-[12.5px] font-semibold text-gray-600 mb-3 flex items-center gap-2">
                      <MessageSquare size={14} className="text-[#2e2e38]" />
                      <span>{res.clarification.question}</span>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2.5">
                    {res.clarification.options.map((opt, oIdx) => (
                      <button
                        key={oIdx}
                        type="button"
                        onClick={() => onSelectOption && onSelectOption(opt.value)}
                        className="flex items-center gap-2 px-3.5 py-2 rounded-lg border border-[#d1d5db] bg-[#fafafa] hover:bg-[#ffe600] hover:border-[#2e2e38] text-[#2e2e38] text-[13px] font-medium transition-all shadow-2xs cursor-pointer text-left"
                      >
                        <ArrowRight size={13} className="text-[#2e2e38] shrink-0" />
                        <span>{opt.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Data Table */}
              {tableRows.length > 0 && (
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#f8f9fa] border-b border-[#e5e7eb]">
                      <th className="p-3 md:p-3.5 text-[12px] font-semibold text-[#2e2e38] border-r border-[#e5e7eb] w-12 text-center">
                        #
                      </th>
                      {tableCols.map((col, idx) => (
                        <th
                          key={idx}
                          className="p-3 md:p-3.5 text-[12px] font-semibold text-[#2e2e38] border-r border-[#e5e7eb] last:border-r-0"
                        >
                          {col.name.replace(/_/g, ' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {displayedRows.map((row, rIdx) => (
                      <tr key={rIdx} className="border-b border-[#f3f4f6] last:border-b-0 hover:bg-[#fafafa] transition-colors">
                        <td className="p-3 text-[12.5px] text-gray-400 font-mono text-center border-r border-[#f3f4f6]">
                          {rIdx + 1}
                        </td>
                        {tableCols.map((col, cIdx) => (
                          <td
                            key={cIdx}
                            className="p-3 text-[13.5px] text-[#2e2e38] border-r border-[#f3f4f6] last:border-r-0 whitespace-nowrap"
                          >
                            {formatValue(row[col.name], col.name, lang)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {tableRows.length > 10 && (
                <div className="p-3 bg-[#fafafa] border-t border-[#e5e7eb] flex items-center justify-between text-[12px] text-gray-600">
                  <span>
                    {t.showingRows
                      .replace('{displayed}', String(displayedRows.length))
                      .replace('{total}', String(tableRows.length))}
                  </span>
                  <button
                    onClick={() => setIsTableExpanded(!isTableExpanded)}
                    className="font-semibold text-[#2e2e38] hover:underline cursor-pointer"
                  >
                    {isTableExpanded
                      ? t.collapseRows
                      : t.showAllRows.replace('{total}', String(tableRows.length))}
                  </button>
                </div>
              )}
            </div>
          )}

          {activeTab === 'sql' && (
            <div className="bg-[#1e1e24] p-5 md:p-6 text-[#ffe600] font-mono text-[13.5px] overflow-x-auto whitespace-pre-wrap min-h-[180px]">
              {res.sql || t.noSqlExecuted}
            </div>
          )}
        </div>

        {/* Footer / Actions */}
        <div className="p-4 bg-[#fafafa] border-t border-[#e5e7eb] flex flex-col xl:flex-row items-start xl:items-center justify-between gap-4">
          <div className="text-[12px] text-gray-600 flex items-center gap-2">
            <AlertCircle size={15} className="text-gray-500 shrink-0" />
            <span>
              <strong>{t.assumptionsPrefix}</strong> {res.assumptions && res.assumptions.length > 0 ? res.assumptions.join(' | ') : t.assumptionsDefault}
            </span>
          </div>
          <div className="flex flex-col sm:flex-row items-center gap-2.5 w-full xl:w-auto shrink-0">
            {res.sql && (
              <div className="flex items-center gap-1.5 mr-1">
                <button
                  type="button"
                  onClick={() => handleFeedback(1)}
                  className={`p-2 rounded-md border transition-colors cursor-pointer ${
                    feedbackScore === 1
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                      : 'bg-white border-gray-300 text-gray-500 hover:text-[#2e2e38] hover:bg-gray-50'
                  }`}
                  title={lang === 'en' ? 'Helpful (Promote verified SQL to Vector Store)' : 'Akurat (Simpan pola SQL ke Vector Store)'}
                >
                  <ThumbsUp size={14} />
                </button>
                <button
                  type="button"
                  onClick={() => handleFeedback(-1)}
                  className={`p-2 rounded-md border transition-colors cursor-pointer ${
                    feedbackScore === -1
                      ? 'bg-red-50 border-red-300 text-red-700'
                      : 'bg-white border-gray-300 text-gray-500 hover:text-[#2e2e38] hover:bg-gray-50'
                  }`}
                  title={lang === 'en' ? 'Report issue' : 'Kurang tepat'}
                >
                  <ThumbsDown size={14} />
                </button>
              </div>
            )}
            {tableRows.length > 0 && (
              <button
                onClick={onExportCsv}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-3.5 py-2 border border-gray-300 bg-white hover:bg-gray-50 text-[#2e2e38] transition-colors text-[12.5px] font-semibold rounded-md shadow-2xs cursor-pointer"
                title={t.downloadCsvTitle}
              >
                <Download size={15} />
                <span>{t.downloadCsv}</span>
              </button>
            )}
            <button
              onClick={onExportHtml}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 border border-[#d6c100] bg-[#ffe600] hover:bg-[#ecd500] text-[#2e2e38] transition-colors text-[12.5px] font-semibold rounded-md shadow-2xs cursor-pointer"
              title={t.execReportTitle}
            >
              <FileText size={15} />
              <span>{t.execReport}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- MAIN APPLICATION COMPONENT ---
export function App() {
  // 1. Language State (Persisted in localStorage)
  const [lang, setLang] = useState<'id' | 'en'>(() => {
    try {
      const saved = localStorage.getItem('ey_bi_lang');
      if (saved === 'id' || saved === 'en') return saved;
    } catch (e) {}
    return 'id';
  });

  const handleToggleLang = (newLang: 'id' | 'en') => {
    setLang(newLang);
    try {
      localStorage.setItem('ey_bi_lang', newLang);
    } catch (e) {}
  };

  const t = TRANSLATIONS[lang];

  // 2. Persistent Multi-Session State via localStorage (Best Practice)
  const [sessions, setSessions] = useState<SessionRecord[]>(() => {
    try {
      const saved = localStorage.getItem('ey_bi_chat_sessions_v1');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return [];
  });

  const [sessionId, setSessionId] = useState<string>(() => {
    try {
      const active = localStorage.getItem('ey_bi_active_session_id');
      if (active) return active;
    } catch (e) {}
    return `session-${Math.random().toString(36).substring(2, 9)}`;
  });

  const [turns, setTurns] = useState<ChatTurn[]>(() => {
    try {
      const active = localStorage.getItem('ey_bi_active_session_id');
      const saved = localStorage.getItem('ey_bi_chat_sessions_v1');
      if (saved && active) {
        const parsed: SessionRecord[] = JSON.parse(saved);
        const match = parsed.find(s => s.id === active);
        if (match && match.turns) return match.turns;
      }
    } catch (e) {}
    return [];
  });

  const [inputValue, setInputValue] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);

  // Model & Provider Configuration
  const [selectedProvider, setSelectedProvider] = useState<string>('gemini');
  const [selectedModel, setSelectedModel] = useState<string>('gemini-3.1-flash-lite');

  // Test Connection State
  const [testState, setTestState] = useState<{
    status: 'idle' | 'testing' | 'connected' | 'error';
    message?: string;
    latencyMs?: number;
  }>({ status: 'idle' });

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [turns]);

  // Load configured models from backend
  useEffect(() => {
    fetch('/api/models')
      .then(res => res.json())
      .then(data => {
        if (data?.current_provider) setSelectedProvider(data.current_provider);
        if (data?.current_model) setSelectedModel(data.current_model);
      })
      .catch(() => {});
  }, []);

  // Sync active turns with localStorage multi-session list
  useEffect(() => {
    if (!sessionId) return;
    setSessions(prev => {
      const existingIdx = prev.findIndex(s => s.id === sessionId);
      const firstUserMsg = turns.find(t => t.userMessage)?.userMessage;
      let newTitle = t.newSession;
      if (firstUserMsg) {
        newTitle = firstUserMsg.length > 28 ? firstUserMsg.substring(0, 26) + '...' : firstUserMsg;
      }

      let updatedList: SessionRecord[];
      if (existingIdx >= 0) {
        const curr = prev[existingIdx];
        updatedList = [...prev];
        updatedList[existingIdx] = {
          ...curr,
          title: (curr.title && curr.title !== "Sesi Baru" && curr.title !== "New Session") ? curr.title : newTitle,
          updatedAt: Date.now(),
          turns
        };
      } else {
        if (turns.length === 0) return prev;
        updatedList = [{ id: sessionId, title: newTitle, updatedAt: Date.now(), turns }, ...prev];
      }

      try {
        localStorage.setItem('ey_bi_chat_sessions_v1', JSON.stringify(updatedList));
        localStorage.setItem('ey_bi_active_session_id', sessionId);
      } catch (e) {}
      return updatedList;
    });
  }, [turns, sessionId, t.newSession]);

  // Session Management Actions
  const handleNewChat = () => {
    const newId = `session-${Math.random().toString(36).substring(2, 9)}`;
    setSessionId(newId);
    setTurns([]);
    setInputValue('');
    try {
      localStorage.setItem('ey_bi_active_session_id', newId);
    } catch (e) {}
    setIsSidebarOpen(false);
  };

  const handleSelectSession = (s: SessionRecord) => {
    setSessionId(s.id);
    setTurns(s.turns || []);
    setInputValue('');
    try {
      localStorage.setItem('ey_bi_active_session_id', s.id);
    } catch (e) {}
    setIsSidebarOpen(false);
  };

  const handleDeleteSession = (e: React.MouseEvent, idToDelete: string) => {
    e.stopPropagation();
    fetch(`/api/sessions/${idToDelete}`, { method: 'DELETE' }).catch(() => {});
    const updated = sessions.filter(s => s.id !== idToDelete);
    setSessions(updated);
    try {
      localStorage.setItem('ey_bi_chat_sessions_v1', JSON.stringify(updated));
    } catch (e) {}

    if (idToDelete === sessionId) {
      if (updated.length > 0) {
        setSessionId(updated[0].id);
        setTurns(updated[0].turns || []);
        localStorage.setItem('ey_bi_active_session_id', updated[0].id);
      } else {
        handleNewChat();
      }
    }
  };

  // Test LLM Connection Action
  const handleTestConnection = async () => {
    setTestState({ status: 'testing', message: t.testing });
    try {
      const res = await fetch('/api/models/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          model: selectedModel
        })
      });
      const data = await res.json();
      if (data.status === 'connected') {
        setTestState({
          status: 'connected',
          message: data.message,
          latencyMs: data.latency_ms
        });
      } else {
        setTestState({
          status: 'error',
          message: data.message || 'Connection failed.'
        });
      }
    } catch (err: any) {
      setTestState({
        status: 'error',
        message: err.message || 'Failed to connect to API server.'
      });
    }

    setTimeout(() => {
      setTestState(prev => prev.status === 'connected' ? { status: 'idle' } : prev);
    }, 6000);
  };

  const handleSendMessage = async (queryText?: string) => {
    const textToSend = (queryText || inputValue).trim();
    if (!textToSend || isProcessing) return;

    const turnId = `turn-${Date.now()}`;
    const newTurn: ChatTurn = {
      id: turnId,
      userMessage: textToSend,
      isLoading: true,
      currentStep: t.processing,
      steps: []
    };

    setTurns(prev => [...prev, newTurn]);
    if (!queryText) setInputValue('');
    setIsProcessing(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: textToSend,
          session_id: sessionId,
          llm_provider: selectedProvider,
          model_name: selectedModel,
          language: lang
        })
      });

      if (!response.ok || !response.body) {
        throw new Error(`Server status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;

          const jsonStr = trimmed.replace(/^data:\s*/, '');
          if (!jsonStr) continue;

          try {
            const parsed = JSON.parse(jsonStr);

            if (parsed.type === 'step') {
              setTurns(prev => prev.map(t => {
                if (t.id !== turnId) return t;
                const newStep: StepEvent = {
                  node: parsed.node,
                  title: parsed.title,
                  description: parsed.description,
                  detail: parsed.detail,
                  elapsed_ms: parsed.elapsed_ms,
                  status: 'active'
                };
                const prevSteps = (t.steps || []).map(s => ({ ...s, status: 'done' as const }));
                return {
                  ...t,
                  currentStep: parsed.description || parsed.title,
                  steps: [...prevSteps, newStep]
                };
              }));
            } else if (
              parsed.type === 'answer' ||
              parsed.type === 'refusal' ||
              parsed.type === 'clarification' ||
              parsed.type === 'final' ||
              parsed.type === 'response' ||
              (parsed.summary && !parsed.node)
            ) {
              const respPayload = parsed.data || parsed;
              setTurns(prev => prev.map(t => {
                if (t.id !== turnId) return t;
                const completedSteps = (t.steps || []).map(s => ({ ...s, status: 'done' as const }));
                return {
                  ...t,
                  isLoading: false,
                  currentStep: undefined,
                  steps: completedSteps,
                  agentResponse: respPayload
                };
              }));
            } else if (parsed.type === 'error') {
              setTurns(prev => prev.map(t => {
                if (t.id !== turnId) return t;
                return {
                  ...t,
                  isLoading: false,
                  currentStep: undefined,
                  steps: (t.steps || []).map(s => ({ ...s, status: 'done' as const })),
                  agentResponse: parsed.summary ? parsed : {
                    type: 'error',
                    summary: parsed.message || 'Terjadi kesalahan sistem.',
                    insights: [parsed.detail || 'Periksa kembali parameter atau struktur query.'],
                    assumptions: []
                  }
                };
              }));
            }
          } catch (e) {
            // Ignore partial SSE chunk parse error
          }
        }
      }
    } catch (err: any) {
      setTurns(prev => prev.map(t =>
        t.id === turnId ? {
          ...t,
          isLoading: false,
          currentStep: undefined,
          steps: (t.steps || []).map(s => ({ ...s, status: 'done' as const })),
          agentResponse: {
            type: 'error',
            summary: lang === 'en' ? 'Failed to connect to backend server.' : 'Gagal terhubung ke server backend.',
            insights: [err?.message || (lang === 'en' ? 'Ensure backend FastAPI is running on port 8000.' : 'Pastikan backend FastAPI telah berjalan di port 8000.')],
            assumptions: []
          }
        } : t
      ));
    } finally {
      setIsProcessing(false);
    }
  };

  const activeSessionRecord = sessions.find(s => s.id === sessionId);
  const currentTitle = activeSessionRecord?.title || (turns.length > 0 ? turns[0].userMessage : (lang === 'en' ? 'Session: Sales & Revenue Analysis' : 'Sesi: Analisis Penjualan & Pendapatan'));

  return (
    <div className="flex h-screen w-full bg-[#f8f9fa] font-sans antialiased overflow-hidden relative">
      {/* --- MOBILE OVERLAY --- */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-[#2e2e38]/60 z-40 md:hidden backdrop-blur-xs"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* --- SIDEBAR --- */}
      <aside
        className={`absolute z-50 h-full transition-transform duration-300 ease-in-out transform ${
          isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } md:relative md:translate-x-0 w-[280px] md:w-[250px] lg:w-[290px] bg-[#2e2e38] text-white flex flex-col flex-shrink-0 border-r border-[#1a1a20]`}
      >
        <div className="p-4 md:p-5 border-b border-[#3e3e4a] flex justify-between items-start">
          <div>
            <h1 className="text-[17px] md:text-[18px] font-bold tracking-tight flex items-center gap-2.5 text-white">
              <span className="w-6 h-6 rounded bg-[#ffe600] text-[#2e2e38] font-black text-[12px] flex items-center justify-center">
                EY
              </span>
              <span>{t.appTitle}</span>
            </h1>
            <p className="text-[#a0a0ab] text-[12px] mt-1">{t.appSubtitle}</p>
          </div>
          <button
            className="md:hidden text-white hover:text-gray-300 cursor-pointer"
            onClick={() => setIsSidebarOpen(false)}
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-3.5">
          <button
            onClick={handleNewChat}
            className="w-full bg-[#ffe600] text-[#2e2e38] font-semibold text-[13.5px] py-2.5 px-4 rounded-md flex items-center justify-center gap-2 hover:bg-[#e6d000] transition-colors shadow-2xs cursor-pointer"
          >
            <Plus size={18} />
            <span>{t.newChat}</span>
          </button>
        </div>

        {/* Saved Sessions List */}
        <div className="flex-1 overflow-y-auto px-3.5 py-1">
          {sessions.length > 0 && (
            <div className="mb-5">
              <h3 className="text-[#a0a0ab] text-[11.5px] font-semibold mb-2 px-1">
                {t.chatHistory} ({sessions.length})
              </h3>
              <ul className="space-y-1">
                {sessions.map((s) => {
                  const isActive = s.id === sessionId;
                  return (
                    <li key={s.id} className="relative group">
                      <div
                        role="button"
                        tabIndex={0}
                        onClick={() => handleSelectSession(s)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handleSelectSession(s);
                          }
                        }}
                        className={`w-full text-left text-[13px] leading-snug p-2.5 rounded-md transition-colors flex items-center justify-between gap-2 cursor-pointer select-none ${
                          isActive
                            ? 'bg-[#3e3e4c] text-white font-medium border-l-3 border-[#ffe600]'
                            : 'text-gray-300 hover:text-white hover:bg-[#363642]'
                        }`}
                      >
                        <div className="flex items-center gap-2 truncate flex-1 min-w-0">
                          <MessageSquare size={14} className={isActive ? 'text-[#ffe600] shrink-0' : 'text-gray-400 shrink-0'} />
                          <span className="truncate">{s.title || t.untitledSession}</span>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => handleDeleteSession(e, s.id)}
                          className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-400 p-1 transition-opacity cursor-pointer shrink-0 rounded"
                          title={t.deleteSession}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {/* Quick Starters Section */}
          <div>
            <h3 className="text-[#a0a0ab] text-[11.5px] font-semibold mb-2 px-1">
              {t.quickStarters}
            </h3>
            <ul className="space-y-1">
              {t.quickQueries.map((item, index) => (
                <li key={index}>
                  <button
                    onClick={() => {
                      handleSendMessage(item);
                      setIsSidebarOpen(false);
                    }}
                    disabled={isProcessing}
                    className="w-full text-left text-[12px] leading-snug text-gray-400 hover:text-white hover:bg-[#363642] p-2 rounded-md transition-colors flex items-center gap-2 truncate cursor-pointer"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-[#ffe600] shrink-0"></span>
                    <span className="truncate">{item}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="p-3.5 border-t border-[#3e3e4a] text-center">
          <p className="text-[11.5px] text-[#a0a0ab]">{t.poweredBy}</p>
        </div>
      </aside>

      {/* --- MAIN CONTENT --- */}
      <main className="flex-1 flex flex-col h-full relative overflow-hidden bg-[#f8f9fa]">
        {/* Header */}
        <header className="bg-white h-[58px] md:h-[64px] border-b border-[#e5e7eb] flex items-center px-4 md:px-8 flex-shrink-0 justify-between">
          <div className="flex items-center gap-3">
            <button
              className="md:hidden text-[#2e2e38] hover:text-gray-600 transition-colors cursor-pointer"
              onClick={() => setIsSidebarOpen(true)}
            >
              <Menu size={22} />
            </button>
            <h2 className="text-[#2e2e38] text-[14px] md:text-[15.5px] font-semibold tracking-tight truncate max-w-[180px] sm:max-w-xs md:max-w-none">
              {currentTitle}
            </h2>
          </div>

          <div className="flex items-center gap-3 md:gap-4">
            {/* Language Switcher Toggle (ID / EN) */}
            <div className="flex items-center bg-[#f3f4f6] rounded-full p-0.5 border border-[#e5e7eb]">
              <button
                onClick={() => handleToggleLang('id')}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-full transition-all cursor-pointer ${
                  lang === 'id'
                    ? 'bg-[#2e2e38] text-[#ffe600] shadow-2xs'
                    : 'text-gray-600 hover:text-[#2e2e38]'
                }`}
                title="Beralih ke Bahasa Indonesia"
              >
                ID
              </button>
              <button
                onClick={() => handleToggleLang('en')}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-full transition-all cursor-pointer ${
                  lang === 'en'
                    ? 'bg-[#2e2e38] text-[#ffe600] shadow-2xs'
                    : 'text-gray-600 hover:text-[#2e2e38]'
                }`}
                title="Switch to English"
              >
                EN
              </button>
            </div>

            {/* Database Status Indicator */}
            <div className="flex items-center gap-2 bg-emerald-50 text-emerald-800 border border-emerald-200 px-3 py-1 rounded-full text-[11.5px] font-medium">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
              <span className="hidden sm:inline-block">
                {t.dbConnected}
              </span>
            </div>
          </div>
        </header>

        {/* Chat Stream Area */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 bg-[#f8f9fa]">
          <div className="max-w-5xl mx-auto flex flex-col gap-6 w-full">
            {/* Welcome State when no messages */}
            {turns.length === 0 && (
              <div className="w-full max-w-4xl mx-auto my-auto py-6">
                <div className="bg-white border border-[#e5e7eb] rounded-2xl p-6 md:p-8 shadow-xs mb-6">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-8 h-8 rounded-md bg-[#ffe600] text-[#2e2e38] flex items-center justify-center font-black text-[13px]">
                      EY
                    </div>
                    <h3 className="text-[19px] md:text-[22px] font-bold text-[#2e2e38]">
                      {t.welcomeTitle}
                    </h3>
                  </div>
                  <p className="text-[13.5px] text-gray-600 leading-relaxed mb-6">
                    {t.welcomeDesc}
                  </p>

                  <div className="text-[12px] font-semibold text-gray-500 mb-3">
                    {t.personaHeader}:
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {t.personas.map((persona, pIdx) => (
                      <div
                        key={pIdx}
                        className="border border-[#e5e7eb] rounded-xl p-4.5 bg-[#fafafa] hover:border-[#ffe600] hover:bg-white transition-all cursor-pointer flex flex-col justify-between shadow-2xs"
                        onClick={() => handleSendMessage(persona.query)}
                      >
                        <div>
                          <h4 className="font-semibold text-[13.5px] text-[#2e2e38] mb-1.5">{persona.title}</h4>
                          <p className="text-[12px] text-gray-500 mb-3 leading-relaxed">{persona.desc}</p>
                        </div>
                        <div className="text-[12px] font-mono text-[#2e2e38] font-semibold flex items-center gap-1.5 pt-2 border-t border-gray-100">
                          <ArrowRight size={13} className="text-[#ffe600] shrink-0" />
                          <span className="truncate">{persona.query}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Turns List */}
            {turns.map(turn => (
              <div key={turn.id} className="flex flex-col gap-4 w-full">
                {/* User Message */}
                <div className="flex justify-end w-full">
                  <div className="bg-white border border-[#e5e7eb] rounded-2xl rounded-tr-sm p-4 md:p-5 max-w-[85%] md:max-w-2xl text-[#2e2e38] text-[14px] md:text-[15px] leading-relaxed shadow-xs break-words">
                    <div className="font-semibold text-[11px] text-gray-400 mb-1">
                      {t.you}
                    </div>
                    {turn.userMessage}
                  </div>
                </div>

                {/* Agent Response */}
                <div className="w-full flex gap-3 md:gap-4">
                  <div className="w-8 h-8 rounded-lg bg-[#ffe600] text-[#2e2e38] flex items-center justify-center shrink-0 mt-1 shadow-2xs">
                    <Database size={17} className="text-[#2e2e38]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-[11px] text-gray-500 mb-1 ml-1">
                      {t.dataAgent}
                    </div>

                    {/* Live Processing Indicator during SSE streaming */}
                    {turn.isLoading && (
                      <div className="bg-white border border-[#e5e7eb] rounded-xl p-4 mb-3 shadow-xs">
                        <div className="flex items-center gap-3">
                          <div className="w-2.5 h-2.5 rounded-full bg-[#ffe600] border border-[#2e2e38] pulse-indicator"></div>
                          <span className="font-medium text-[13.5px] text-[#2e2e38]">
                            {turn.currentStep || t.processing}
                          </span>
                          <span className="text-[11px] bg-gray-100 text-gray-700 px-2 py-0.5 rounded font-mono border border-gray-200">
                            {t.step} {turn.steps.length}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Agent Message Card */}
                    {turn.agentResponse && (
                      <AgentMessageCard
                        turn={turn}
                        sessionId={sessionId}
                        lang={lang}
                        t={t}
                        onSelectOption={(q) => handleSendMessage(q)}
                        onExportCsv={() =>
                          exportToCsv(
                            turn.agentResponse?.table?.columns || [],
                            turn.agentResponse?.table?.rows || [],
                            `EY_data_export_${turn.id}`,
                            lang
                          )
                        }
                        onExportHtml={() =>
                          openExecutiveHtmlReport(turn.agentResponse, {
                            userQuery: turn.userMessage,
                            sessionId,
                            timestamp: new Date().toLocaleString(lang === 'en' ? 'en-US' : 'id-ID'),
                            modelName: selectedModel,
                            provider: selectedProvider,
                            lang
                          })
                        }
                      />
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input & LLM Configuration Area */}
        <div className="bg-white border-t border-[#e5e7eb] p-4 md:p-5 flex-shrink-0">
          <div className="max-w-5xl mx-auto relative">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex gap-2 md:gap-3"
            >
              <div className="relative flex-1">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder={t.inputPlaceholder}
                  className="w-full bg-white border border-[#d1d5db] focus:border-[#2e2e38] focus:ring-2 focus:ring-[#ffe600]/40 rounded-xl py-3 md:py-3.5 pl-3.5 md:pl-4 pr-12 text-[14px] md:text-[15px] text-[#2e2e38] placeholder-gray-400 focus:outline-none transition-all shadow-2xs"
                  disabled={isProcessing}
                />
                <button
                  type="submit"
                  className="absolute right-1.5 md:right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg text-[#2e2e38] hover:bg-[#ffe600] transition-colors disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer"
                  disabled={!inputValue.trim() || isProcessing}
                  title={t.sendTooltip}
                >
                  <Send size={18} />
                </button>
              </div>
            </form>

            {/* Configuration Bar */}
            <div className="mt-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 border-t border-gray-100 pt-3">
              <div className="flex flex-wrap items-center gap-3 md:gap-4">
                <div className="flex items-center gap-1.5">
                  <Settings size={14} className="text-gray-500" />
                  <span className="text-[12px] font-semibold text-[#2e2e38]">
                    {t.llmConfig}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <label className="text-[11.5px] font-medium text-gray-500">
                    {t.provider}
                  </label>
                  <select
                    value={selectedProvider}
                    onChange={(e) => {
                      const prov = e.target.value;
                      setSelectedProvider(prov);
                      setTestState({ status: 'idle' });
                      if (prov === 'azure') {
                        setSelectedModel('gpt-4o-mini');
                      } else {
                        setSelectedModel('gemini-3.1-flash-lite');
                      }
                    }}
                    className="text-[12px] border border-gray-300 rounded-md bg-white text-[#2e2e38] px-2.5 py-1 focus:outline-none focus:border-[#2e2e38] cursor-pointer font-medium"
                  >
                    <option value="gemini">Google Gemini</option>
                    <option value="azure">Azure OpenAI</option>
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <label className="text-[11.5px] font-medium text-gray-500">
                    {t.model}
                  </label>
                  <select
                    value={selectedModel}
                    onChange={(e) => {
                      setSelectedModel(e.target.value);
                      setTestState({ status: 'idle' });
                    }}
                    className="text-[12px] border border-gray-300 rounded-md bg-white text-[#2e2e38] px-2.5 py-1 focus:outline-none focus:border-[#2e2e38] cursor-pointer font-medium"
                  >
                    {selectedProvider === 'gemini' ? (
                      <>
                        <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite ({t.recommendedFast})</option>
                        <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                        <option value="gemini-1.5-pro">gemini-1.5-pro</option>
                      </>
                    ) : (
                      <>
                        <option value="gpt-4o-mini">gpt-4o-mini</option>
                        <option value="gpt-4o">gpt-4o</option>
                      </>
                    )}
                  </select>
                </div>

                {/* Test Connection Button */}
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testState.status === 'testing'}
                  className="flex items-center gap-1.5 px-3 py-1 border border-gray-300 bg-white hover:bg-[#ffe600] hover:border-[#2e2e38] text-[#2e2e38] rounded-md transition-colors text-[11.5px] font-semibold disabled:opacity-50 cursor-pointer shadow-2xs"
                  title="Uji koneksi ke LLM Provider & Model yang dipilih"
                >
                  <Zap size={13} className={testState.status === 'testing' ? 'animate-pulse text-[#ffe600]' : 'text-[#2e2e38]'} />
                  <span>{testState.status === 'testing' ? t.testing : t.testConnection}</span>
                </button>

                {/* Test Connection Result Badge */}
                {testState.status === 'connected' && (
                  <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-800 bg-emerald-50 border border-emerald-300 px-2.5 py-0.5 rounded-full">
                    <CheckCircle2 size={12} className="text-emerald-600" />
                    <span>{t.connected} ({testState.latencyMs}ms)</span>
                  </span>
                )}

                {testState.status === 'error' && (
                  <span
                    className="flex items-center gap-1 text-[11px] font-semibold text-red-700 bg-red-50 border border-red-200 px-2.5 py-0.5 rounded-full"
                    title={testState.message}
                  >
                    <AlertCircle size={12} className="text-red-500 shrink-0" />
                    <span>{t.notConnected}</span>
                  </span>
                )}
              </div>

              <div className="text-[11px] text-gray-500 flex items-center gap-1.5 max-w-full md:max-w-[40%]">
                <Database size={13} className="text-gray-400 shrink-0" />
                <span className="truncate">
                  {t.schemaAware}
                </span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
