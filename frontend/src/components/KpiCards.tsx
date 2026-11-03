import React from 'react';
import { Sparkles, Table as TableIcon, TerminalSquare } from 'lucide-react';
import { KPICard, AgentResponse } from '../types/chat';
import { TranslationType } from '../constants/translations';
import { formatCurrency } from '../utils/formatters';

interface KpiCardsProps {
  res: AgentResponse;
  lang: 'id' | 'en';
  t: TranslationType;
  isConversationalCard: boolean;
  metricLabel: string;
  metricDisplay: string;
  secondaryKpis: KPICard[];
  tableRowsLength: number;
  activeTab: 'table' | 'sql';
  setActiveTab: (tab: 'table' | 'sql') => void;
}

export const KpiCards: React.FC<KpiCardsProps> = ({
  res,
  lang,
  t,
  isConversationalCard,
  metricLabel,
  metricDisplay,
  secondaryKpis,
  tableRowsLength,
  activeTab,
  setActiveTab
}) => {
  return (
    <div className="p-5 md:p-6 border-b border-[#e5e7eb] flex flex-col md:flex-row items-start md:items-center justify-between gap-4 bg-white">
      <div className="flex-1">
        {isConversationalCard ? (
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#fffdf0] border border-[#f0e08a] text-[#2e2e38] text-[11.5px] font-semibold mb-2.5">
              <Sparkles size={13} className="text-[#2e2e38]" />
              <span>
                {res.type === 'discussion'
                  ? lang === 'en'
                    ? 'Analytical Discussion & Advisory'
                    : 'Diskusi & Konsultasi Analitik'
                  : res.type === 'clarification'
                  ? lang === 'en'
                    ? 'Proactive Parameter Confirmation'
                    : 'Konfirmasi Parameter Analisis'
                  : res.type === 'refusal'
                  ? lang === 'en'
                    ? 'Domain Scope Guardrail'
                    : 'Batas Cakupan Analitik'
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

      {(!isConversationalCard || res.sql || tableRowsLength > 0) && (
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
  );
};

