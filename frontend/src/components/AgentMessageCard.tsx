import React, { useState } from 'react';
import {
  AlertCircle,
  Download,
  FileText,
  ThumbsUp,
  ThumbsDown
} from 'lucide-react';
import { ChatTurn } from '../types/chat';
import { TranslationType } from '../constants/translations';
import { formatCurrency } from '../utils/formatters';
import { TelemetryPanel } from './TelemetryPanel';
import { KpiCards } from './KpiCards';
import { DataTableVisualizer } from './DataTableVisualizer';

export interface AgentMessageCardProps {
  turn: ChatTurn;
  sessionId: string;
  lang: 'id' | 'en';
  t: TranslationType;
  onExportCsv: () => void;
  onExportHtml: () => void;
  onSelectOption?: (queryText: string) => void;
}

export const AgentMessageCard: React.FC<AgentMessageCardProps> = ({
  turn,
  sessionId,
  lang,
  t,
  onExportCsv,
  onExportHtml,
  onSelectOption
}) => {
  const [activeTab, setActiveTab] = useState<'table' | 'sql'>('table');
  const [isThinkingExpanded, setIsThinkingExpanded] = useState<boolean>(false);
  const [feedbackScore, setFeedbackScore] = useState<number | null>(null);

  const res = turn.agentResponse;
  if (!res) return null;

  const handleFeedback = async (score: number) => {
    setFeedbackScore(score);
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          trace_id: res.trace?.trace_id,
          score
        })
      });
    } catch (e) {}
  };

  const isConversationalCard =
    res.type === 'discussion' ||
    res.type === 'clarification' ||
    res.type === 'refusal' ||
    ((!res.kpis || res.kpis.length === 0) && (!res.table?.rows || res.table.rows.length === 0));

  const displaySteps =
    turn.steps && turn.steps.length > 0 ? turn.steps : res.trace?.steps || [];
  const totalMs =
    res.trace?.total_duration_ms ??
    (displaySteps.length > 0 ? displaySteps[displaySteps.length - 1].elapsed_ms : undefined);
  const plan = res.trace?.plan;

  // Extract primary metric
  const primaryKpi = res.kpis && res.kpis.length > 0 ? res.kpis[0] : null;
  const secondaryKpis = res.kpis && res.kpis.length > 1 ? res.kpis.slice(1) : [];

  const metricDisplay = primaryKpi
    ? primaryKpi.format === 'currency_idr' && typeof primaryKpi.value === 'number'
      ? formatCurrency(primaryKpi.value, lang)
      : primaryKpi.format === 'percentage'
      ? `${primaryKpi.value}%`
      : String(primaryKpi.value)
    : res.summary || (lang === 'en' ? 'Analysis Result' : 'Hasil Analisis');

  const metricLabel = primaryKpi
    ? primaryKpi.label
    : res.table?.rows
    ? `${res.table.rows.length} ${t.rowsFound}`
    : lang === 'en'
    ? 'Business Analysis'
    : 'Analisis Bisnis';

  const tableRows = res.table?.rows || [];

  return (
    <div className="w-full max-w-4xl flex flex-col mb-6 mt-1">
      {/* 1. Thinking Process & Observability Accordion */}
      <TelemetryPanel
        displaySteps={displaySteps}
        totalMs={totalMs}
        plan={plan}
        finalSql={res.sql}
        isExpanded={isThinkingExpanded}
        onToggle={() => setIsThinkingExpanded(!isThinkingExpanded)}
        t={t}
      />

      {/* 2. Main Card Content (Soft, Modernized EY Style) */}
      <div className="bg-white border border-[#e5e7eb] border-t-3 border-t-[#ffe600] rounded-xl shadow-xs hover:shadow-sm transition-shadow w-full overflow-hidden">
        {/* Header / Metric or Conversational Section */}
        <KpiCards
          res={res}
          lang={lang}
          t={t}
          isConversationalCard={isConversationalCard}
          metricLabel={metricLabel}
          metricDisplay={metricDisplay}
          secondaryKpis={secondaryKpis}
          tableRowsLength={tableRows.length}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />

        {/* Tab Content */}
        <DataTableVisualizer
          res={res}
          activeTab={activeTab}
          lang={lang}
          t={t}
          onSelectOption={onSelectOption}
        />

        {/* Footer / Actions */}
        <div className="p-4 bg-[#fafafa] border-t border-[#e5e7eb] flex flex-col xl:flex-row items-start xl:items-center justify-between gap-4">
          <div className="text-[12px] text-gray-600 flex items-center gap-2">
            <AlertCircle size={15} className="text-gray-500 shrink-0" />
            <span>
              <strong>{t.assumptionsPrefix}</strong>{' '}
              {res.assumptions && res.assumptions.length > 0
                ? res.assumptions.join(' | ')
                : t.assumptionsDefault}
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
                  title={
                    lang === 'en'
                      ? 'Helpful (Promote verified SQL to Vector Store)'
                      : 'Akurat (Simpan pola SQL ke Vector Store)'
                  }
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

