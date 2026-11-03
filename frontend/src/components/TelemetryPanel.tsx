import React from 'react';
import {
  ChevronDown,
  ChevronUp,
  Terminal,
  CheckCircle2,
  FileJson,
  Code
} from 'lucide-react';
import { StepEvent } from '../types/chat';
import { TranslationType } from '../constants/translations';

interface TelemetryPanelProps {
  displaySteps: StepEvent[];
  totalMs?: number;
  plan?: any;
  finalSql?: string;
  isExpanded: boolean;
  onToggle: () => void;
  t: TranslationType;
}

export const TelemetryPanel: React.FC<TelemetryPanelProps> = ({
  displaySteps,
  totalMs,
  plan,
  finalSql,
  isExpanded,
  onToggle,
  t
}) => {
  if (displaySteps.length === 0) return null;

  const reasoningLabel = isExpanded
    ? t.hideReasoning
    : t.showReasoning
        .replace('{count}', String(displaySteps.length))
        .replace('{time}', totalMs ? ` / ${(totalMs / 1000).toFixed(2)}s` : '');

  return (
    <div className="mb-3">
      <button
        onClick={onToggle}
        className="flex items-center gap-2 text-[13px] font-semibold text-[#2e2e38] bg-transparent hover:text-gray-600 transition-colors py-1 group cursor-pointer"
      >
        <span className="w-5 h-5 rounded-md flex items-center justify-center bg-gray-200 group-hover:bg-gray-300 transition-colors">
          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
        <span>{reasoningLabel}</span>
      </button>

      {isExpanded && (
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
          {finalSql && (
            <div className="p-5 md:p-6 bg-white">
              <h6 className="font-semibold text-[#2e2e38] mb-3 text-[13px] flex items-center gap-2">
                <Code size={15} className="text-[#2e2e38]" />
                <span>{t.finalSql}</span>
              </h6>
              <div className="bg-[#1e1e24] p-4 text-[#ffe600] font-mono text-[12.5px] overflow-x-auto whitespace-pre-wrap rounded-lg border border-[#2e2e38]">
                {finalSql}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

