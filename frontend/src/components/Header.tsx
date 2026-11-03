import React from 'react';
import { Menu } from 'lucide-react';
import { TranslationType } from '../constants/translations';

interface HeaderProps {
  currentTitle: string;
  lang: 'id' | 'en';
  onToggleLang: (lang: 'id' | 'en') => void;
  onOpenSidebar: () => void;
  t: TranslationType;
}

export const Header: React.FC<HeaderProps> = ({
  currentTitle,
  lang,
  onToggleLang,
  onOpenSidebar,
  t
}) => {
  return (
    <header className="bg-white h-[58px] md:h-[64px] border-b border-[#e5e7eb] flex items-center px-4 md:px-8 flex-shrink-0 justify-between">
      <div className="flex items-center gap-3">
        <button
          className="md:hidden text-[#2e2e38] hover:text-gray-600 transition-colors cursor-pointer"
          onClick={onOpenSidebar}
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
            onClick={() => onToggleLang('id')}
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
            onClick={() => onToggleLang('en')}
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
          <span className="hidden sm:inline-block">{t.dbConnected}</span>
        </div>
      </div>
    </header>
  );
};

