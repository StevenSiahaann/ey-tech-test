export interface StepEvent {
  node: string;
  title: string;
  description: string;
  detail?: string;
  elapsed_ms?: number;
  status?: 'done' | 'active';
}

export interface KPICard {
  label: string;
  value: any;
  format: string;
  subtitle?: string;
}

export interface TableData {
  columns: { name: string; type: string }[];
  rows: Record<string, any>[];
  truncated?: boolean;
}

export interface ChartConfig {
  type: 'bar' | 'line' | 'pie' | 'none';
  x_axis?: string;
  y_axes?: string[];
  title?: string;
}

export interface AgentResponse {
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
    trace_id?: string;
    [key: string]: any;
  };
}

export interface ChatTurn {
  id: string;
  userMessage: string;
  agentResponse?: AgentResponse;
  isLoading?: boolean;
  currentStep?: string;
  steps: StepEvent[];
}

export interface SessionRecord {
  id: string;
  title: string;
  updatedAt: number;
  turns: ChatTurn[];
}

export type LanguageMode = 'id' | 'en';

