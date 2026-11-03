import React, { useState, useRef, useEffect } from 'react';
import { ChatTurn, SessionRecord, StepEvent } from './types/chat';
import { TRANSLATIONS } from './constants/translations';
import { generateSafeSessionId } from './utils/formatters';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ChatView } from './components/ChatView';

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
    return generateSafeSessionId();
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
  const abortControllerRef = useRef<AbortController | null>(null);

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
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsProcessing(false);
    }
    const newId = generateSafeSessionId();
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

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
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
      if (err?.name === 'AbortError') return;
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
      abortControllerRef.current = null;
      setIsProcessing(false);
    }
  };

  const activeSessionRecord = sessions.find(s => s.id === sessionId);
  const currentTitle =
    activeSessionRecord?.title ||
    (turns.length > 0
      ? turns[0].userMessage
      : lang === 'en'
      ? 'Session: Sales & Revenue Analysis'
      : 'Sesi: Analisis Penjualan & Pendapatan');

  return (
    <div className="flex h-screen w-full bg-[#f8f9fa] font-sans antialiased overflow-hidden relative">
      {/* Sidebar */}
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onNewChat={handleNewChat}
        sessions={sessions}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        onSelectQuickQuery={(q) => {
          handleSendMessage(q);
          setIsSidebarOpen(false);
        }}
        isProcessing={isProcessing}
        t={t}
      />

      {/* Main Content Pane */}
      <main className="flex-1 flex flex-col h-full relative overflow-hidden bg-[#f8f9fa]">
        <Header
          currentTitle={currentTitle}
          lang={lang}
          onToggleLang={handleToggleLang}
          onOpenSidebar={() => setIsSidebarOpen(true)}
          t={t}
        />

        <ChatView
          turns={turns}
          sessionId={sessionId}
          lang={lang}
          t={t}
          inputValue={inputValue}
          setInputValue={setInputValue}
          isProcessing={isProcessing}
          onSendMessage={handleSendMessage}
          selectedProvider={selectedProvider}
          setSelectedProvider={setSelectedProvider}
          selectedModel={selectedModel}
          setSelectedModel={setSelectedModel}
          testState={testState}
          setTestState={setTestState}
          onTestConnection={handleTestConnection}
          messagesEndRef={messagesEndRef}
        />
      </main>
    </div>
  );
}

export default App;
