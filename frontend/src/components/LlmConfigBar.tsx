import React from 'react';
import { Settings, Zap, CheckCircle2, AlertCircle, Database } from 'lucide-react';
import { TranslationType } from '../constants/translations';

interface LlmConfigBarProps {
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
  t: TranslationType;
}

export const LlmConfigBar: React.FC<LlmConfigBarProps> = ({
  selectedProvider,
  setSelectedProvider,
  selectedModel,
  setSelectedModel,
  testState,
  setTestState,
  onTestConnection,
  t
}) => {
  return (
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
          onClick={onTestConnection}
          disabled={testState.status === 'testing'}
          className="flex items-center gap-1.5 px-3 py-1 border border-gray-300 bg-white hover:bg-[#ffe600] hover:border-[#2e2e38] text-[#2e2e38] rounded-md transition-colors text-[11.5px] font-semibold disabled:opacity-50 cursor-pointer shadow-2xs"
          title="Uji koneksi ke LLM Provider & Model yang dipilih"
        >
          <Zap
            size={13}
            className={testState.status === 'testing' ? 'animate-pulse text-[#ffe600]' : 'text-[#2e2e38]'}
          />
          <span>{testState.status === 'testing' ? t.testing : t.testConnection}</span>
        </button>

        {/* Test Connection Result Badge */}
        {testState.status === 'connected' && (
          <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-800 bg-emerald-50 border border-emerald-300 px-2.5 py-0.5 rounded-full">
            <CheckCircle2 size={12} className="text-emerald-600" />
            <span>
              {t.connected} ({testState.latencyMs}ms)
            </span>
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
        <span className="truncate">{t.schemaAware}</span>
      </div>
    </div>
  );
};

