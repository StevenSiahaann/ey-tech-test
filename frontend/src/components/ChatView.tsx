import React, { RefObject } from 'react';
import { EyLogo } from './EyLogo';
import { Database, ArrowRight, Send } from 'lucide-react';
import { ChatTurn } from '../types/chat';
import { TranslationType } from '../constants/translations';
import { AgentMessageCard } from './AgentMessageCard';
import { LlmConfigBar } from './LlmConfigBar';
import { exportToCsv, openExecutiveHtmlReport } from '../utils/executiveReport';

interface ChatViewProps {
  turns: ChatTurn[];
  sessionId: string;
  lang: 'id' | 'en';
  t: TranslationType;
  inputValue: string;
  setInputValue: (val: string) => void;
  isProcessing: boolean;
  onSendMessage: (text?: string) => void;
  selectedProvider: string;
  setSelectedProvider: (provider: string) => void;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
  testState: {
    status: 'idle' | 'testing' | 'connected' | 'error';
    message?: string;
    latencyMs?: number;
  };
  setTestState: React.Dispatch<
    React.SetStateAction<{
      status: 'idle' | 'testing' | 'connected' | 'error';
      message?: string;
      latencyMs?: number;
    }>
  >;
  onTestConnection: () => void;
  messagesEndRef: RefObject<HTMLDivElement>;
}

export const ChatView: React.FC<ChatViewProps> = ({
  turns,
  sessionId,
  lang,
  t,
  inputValue,
  setInputValue,
  isProcessing,
  onSendMessage,
  selectedProvider,
  setSelectedProvider,
  selectedModel,
  setSelectedModel,
  testState,
  setTestState,
  onTestConnection,
  messagesEndRef
}) => {
  return (
    <div className="flex-1 flex flex-col h-full relative overflow-hidden bg-[#f8f9fa]">
      {/* Chat Stream Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8 bg-[#f8f9fa]">
        <div className="max-w-5xl mx-auto flex flex-col gap-6 w-full">
          {/* Welcome State when no messages */}
          {turns.length === 0 && (
            <div className="w-full max-w-4xl mx-auto my-auto py-6">
              <div className="bg-white border border-[#e5e7eb] rounded-2xl p-6 md:p-8 shadow-xs mb-6">
                <div className="flex items-center gap-3 mb-3">
                  <EyLogo className="w-8 h-8 shrink-0 shadow-xs" />
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
                      onClick={() => onSendMessage(persona.query)}
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
                      onSelectOption={(q) => onSendMessage(q)}
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
              onSendMessage();
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
          <LlmConfigBar
            selectedProvider={selectedProvider}
            setSelectedProvider={setSelectedProvider}
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
            testState={testState}
            setTestState={setTestState}
            onTestConnection={onTestConnection}
            t={t}
          />
        </div>
      </div>
    </div>
  );
};

