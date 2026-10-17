/* ─── Types: Conversations, Messages, and Tool Observability Traces ───── */

export type ToolAccessItem = {
  id: string;
  tool_name: string;
  tool_type: string;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  status: 'running' | 'success' | 'error';
  input_data?: unknown;
  output_data?: unknown;
  error?: string | null;
};

export type ChatMessage = {
  id: string;
  userMessage: string;
  assistantMessage: string;
  createdAt: number;
  traceId?: string;
  toolsAccessed?: ToolAccessItem[];
  skill?: string | null;
  skillTrigger?: string | null;
  intent?: string | null;
  mem0OptIn?: boolean;
  mem0SearchStatus?: 'not_requested' | 'succeeded' | 'failed' | 'timed_out';
  mem0SaveStatus?: 'not_requested' | 'saved' | 'not_attempted' | 'failed' | 'timed_out' | 'cancelled';
};

export type StageFailureDetail = {
  provider: 'openrouter' | 'mem0' | 'client' | 'internal';
  stage: 'mem0_search' | 'llm_generate' | 'mem0_add' | 'client_timeout';
  code: 'timeout' | 'upstream_error' | 'cancelled' | 'validation_error';
  message: string;
  retriable: boolean;
};

export type Conversation = {
  id: string;
  serverConversationId?: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
};

export type ThemePreference = 'light' | 'dark' | 'system';

export type AppState = {
  conversations: Record<string, Conversation>;
  activeConversationId: string | null;
  theme: ThemePreference;
};

export type PromptTrace = {
  id: string;
  user_id: string;
  conversation_id?: string | null;
  prompt: string;
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string | null;
  total_duration_ms?: number | null;
  tools_accessed: ToolAccessItem[];
  response_preview?: string | null;
  error?: string | null;
  skill?: string | null;
  skill_trigger?: string | null;
  intent?: string | null;
};

export type SkillItem = {
  name: string;
  description: string;
  keywords: string[];
  instructions: string;
  tools: string[];
  slash_command: string;
};

export type AdminStats = {
  total_prompts: number;
  total_tool_calls: number;
  avg_duration_ms: number;
  tool_breakdown: Record<string, number>;
};
