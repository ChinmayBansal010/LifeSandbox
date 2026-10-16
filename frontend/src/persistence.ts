/* ─── Local storage persistence with migration ──────────────────────── */

import type { AppState, ChatMessage, Conversation, ThemePreference } from './types';

const STORAGE_KEY = 'life-sandbox-state';
const STORAGE_VERSION = 2;

type LegacyScenarioNode = {
  id: string;
  parentId: string | null;
  userMessage: string;
  assistantMessage: string;
  createdAt: number;
};

type LegacyScenario = {
  id: string;
  title: string;
  nodeIds: string[];
  createdAt: number;
  updatedAt: number;
};

type StoredPayload = {
  version?: number;
  data?: {
    conversations?: Record<string, Conversation>;
    activeConversationId?: string | null;
    scenarios?: Record<string, LegacyScenario>;
    nodes?: Record<string, LegacyScenarioNode>;
    activeScenarioId?: string | null;
    theme?: ThemePreference;
  };
};

const DEFAULT_STATE: AppState = {
  conversations: {},
  activeConversationId: null,
  theme: 'system',
};

/**
 * Load application state from localStorage with backward-compatible migration.
 */
export function loadState(): AppState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_STATE };

    const parsed: StoredPayload = JSON.parse(raw);
    if (!parsed || !parsed.data) {
      return { ...DEFAULT_STATE };
    }

    const { data } = parsed;
    const theme: ThemePreference = data.theme ?? 'system';

    // If already in new conversation format
    if (data.conversations && typeof data.conversations === 'object') {
      return {
        conversations: data.conversations,
        activeConversationId: data.activeConversationId ?? Object.keys(data.conversations)[0] ?? null,
        theme,
      };
    }

    // Auto-migrate from legacy branching scenario tree format
    if (data.scenarios && typeof data.scenarios === 'object') {
      const migratedConversations: Record<string, Conversation> = {};
      const legacyNodes = data.nodes ?? {};

      for (const [id, sc] of Object.entries(data.scenarios)) {
        const messages: ChatMessage[] = (sc.nodeIds || [])
          .map((nid) => legacyNodes[nid])
          .filter(Boolean)
          .sort((a, b) => a.createdAt - b.createdAt)
          .map((n) => ({
            id: n.id,
            userMessage: n.userMessage,
            assistantMessage: n.assistantMessage,
            createdAt: n.createdAt,
          }));

        migratedConversations[id] = {
          id: sc.id || id,
          title: sc.title || 'Untitled Chat',
          messages,
          createdAt: sc.createdAt || Date.now(),
          updatedAt: sc.updatedAt || Date.now(),
        };
      }

      const activeId = data.activeScenarioId && migratedConversations[data.activeScenarioId]
        ? data.activeScenarioId
        : Object.keys(migratedConversations)[0] ?? null;

      const migratedState: AppState = {
        conversations: migratedConversations,
        activeConversationId: activeId,
        theme,
      };

      saveState(migratedState);
      return migratedState;
    }

    return { ...DEFAULT_STATE };
  } catch {
    return { ...DEFAULT_STATE };
  }
}

/**
 * Save application state to localStorage.
 */
export function saveState(state: AppState): void {
  try {
    const stored = {
      version: STORAGE_VERSION,
      data: state,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
  } catch {
    console.warn('Failed to persist state to localStorage');
  }
}

/**
 * Fast-path theme loader.
 */
export function loadThemePreference(): ThemePreference {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return 'system';
    const parsed = JSON.parse(raw);
    return parsed?.data?.theme ?? 'system';
  } catch {
    return 'system';
  }
}
