import React, { useState } from 'react';
import {
  BarChart3,
  TrendingUp,
  Target,
  MessageSquare,
  ArrowRight
} from 'lucide-react';
import { AgentResponse } from '../types/chat';
import { TranslationType } from '../constants/translations';
import { formatValue } from '../utils/formatters';

interface DataTableVisualizerProps {
  res: AgentResponse;
  activeTab: 'table' | 'sql';
  lang: 'id' | 'en';
  t: TranslationType;
  onSelectOption?: (queryText: string) => void;
}

export const DataTableVisualizer: React.FC<DataTableVisualizerProps> = ({
  res,
  activeTab,
  lang,
  t,
  onSelectOption
}) => {
  const [isTableExpanded, setIsTableExpanded] = useState<boolean>(false);

  const tableRows = res.table?.rows || [];
  const tableCols = res.table?.columns || [];
  const displayedRows = isTableExpanded ? tableRows : tableRows.slice(0, 10);

  // Auto-Chart parameters
  const validNumCol =
    res.chart?.y_axes?.[0] && tableCols.some(c => c.name === res.chart?.y_axes?.[0])
      ? res.chart.y_axes[0]
      : tableCols.find(c => typeof tableRows[0]?.[c.name] === 'number')?.name;
  const numCol = validNumCol;
  const catCol = res.chart?.x_axis || tableCols.find(c => c.name !== numCol)?.name || tableCols[0]?.name;
  const chartRows = tableRows.slice(0, 8);
  const maxVal = Math.max(...chartRows.map(r => Number(r[numCol || '']) || 0), 1);

  return (
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
  );
};

