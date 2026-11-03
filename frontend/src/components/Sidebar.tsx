import React from 'react';
import { Plus, X, MessageSquare, Trash2 } from 'lucide-react';
import { EyLogo } from './EyLogo';
import { SessionRecord } from '../types/chat';
import { TranslationType } from '../constants/translations';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
  sessions: SessionRecord[];
  activeSessionId: string;
  onSelectSession: (session: SessionRecord) => void;
  onDeleteSession: (e: React.MouseEvent, id: string) => void;
  onSelectQuickQuery: (query: string) => void;
  isProcessing: boolean;
  t: TranslationType;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  onNewChat,
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  onSelectQuickQuery,
  isProcessing,
  t
}) => {
  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-[#2e2e38]/60 z-40 md:hidden backdrop-blur-xs"
          onClick={onClose}
        />
      )}

      {/* Sidebar Panel */}
      <aside
        className={`absolute z-50 h-full transition-transform duration-300 ease-in-out transform ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } md:relative md:translate-x-0 w-[280px] md:w-[250px] lg:w-[290px] bg-[#2e2e38] text-white flex flex-col flex-shrink-0 border-r border-[#1a1a20]`}
      >
        <div className="p-4 md:p-5 border-b border-[#3e3e4a] flex justify-between items-start">
          <div>
            <h1 className="text-[17px] md:text-[18px] font-bold tracking-tight flex items-center gap-2.5 text-white">
              <EyLogo className="w-6 h-6 shrink-0 shadow-xs" />
              <span>{t.appTitle}</span>
            </h1>
            <p className="text-[#a0a0ab] text-[12px] mt-1">{t.appSubtitle}</p>
          </div>
          <button
            className="md:hidden text-white hover:text-gray-300 cursor-pointer"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-3.5">
          <button
            onClick={onNewChat}
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
                  const isActive = s.id === activeSessionId;
                  return (
                    <li key={s.id} className="relative group">
                      <div
                        role="button"
                        tabIndex={0}
                        onClick={() => onSelectSession(s)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            onSelectSession(s);
                          }
                        }}
                        className={`w-full text-left text-[13px] leading-snug p-2.5 rounded-md transition-colors flex items-center justify-between gap-2 cursor-pointer select-none ${
                          isActive
                            ? 'bg-[#3e3e4c] text-white font-medium border-l-3 border-[#ffe600]'
                            : 'text-gray-300 hover:text-white hover:bg-[#363642]'
                        }`}
                      >
                        <div className="flex items-center gap-2 truncate flex-1 min-w-0">
                          <MessageSquare
                            size={14}
                            className={isActive ? 'text-[#ffe600] shrink-0' : 'text-gray-400 shrink-0'}
                          />
                          <span className="truncate">{s.title || t.untitledSession}</span>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => onDeleteSession(e, s.id)}
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
                    onClick={() => onSelectQuickQuery(item)}
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
    </>
  );
};

