/* ─── Local storage persistence with migration ──────────────────────── */

import type { AppState, ChatMessage, Conversation, CustomSkill, ThemePreference } from './types';

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
    customSkills?: Record<string, CustomSkill>;
  };
};

function isThemePreference(value: unknown): value is ThemePreference {
  return (
    value === 'light' ||
    value === 'dark' ||
    value === 'system' ||
    value === 'high-contrast' ||
    value === 'dracula' ||
    value === 'mocha'
  );
}

function isConversation(value: unknown): value is Conversation {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<Conversation>;
  return typeof item.id === 'string'
    && typeof item.title === 'string'
    && typeof item.createdAt === 'number'
    && typeof item.updatedAt === 'number'
    && Array.isArray(item.messages)
    && item.messages.every((message) => (
      !!message
      && typeof message.id === 'string'
      && typeof message.userMessage === 'string'
      && typeof message.assistantMessage === 'string'
      && typeof message.createdAt === 'number'
    ));
}

export const DEFAULT_CUSTOM_SKILLS: Record<string, CustomSkill> = {
  'code-reviewer': {
    id: 'code-reviewer',
    name: 'Code Reviewer',
    description: 'Review code for performance, bugs, and edge cases',
    slash_command: 'code-reviewer',
    definition: `# Code Reviewer\n\nReview provided source code with precision:\n1. Check for logic flaws, race conditions, and unhandled edge cases\n2. Verify security issues and input validation\n3. Recommend concise, idiomatic improvements`,
    createdAt: 1710000000000,
    updatedAt: 1710000000000,
  },
};

const DEFAULT_STATE: AppState = {
  conversations: {},
  activeConversationId: null,
  theme: 'system',
  customSkills: DEFAULT_CUSTOM_SKILLS,
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
    const theme: ThemePreference = isThemePreference(data.theme) ? data.theme : 'system';
    const customSkills: Record<string, CustomSkill> =
      data.customSkills && typeof data.customSkills === 'object' && !Array.isArray(data.customSkills)
        ? data.customSkills
        : { ...DEFAULT_CUSTOM_SKILLS };

    // If already in new conversation format
    if (data.conversations && typeof data.conversations === 'object' && !Array.isArray(data.conversations)) {
      const conversations = Object.fromEntries(
        Object.entries(data.conversations).filter(([, value]) => isConversation(value))
      );
      const requestedActiveId = data.activeConversationId;
      const activeConversationId = typeof requestedActiveId === 'string' && conversations[requestedActiveId]
        ? requestedActiveId
        : Object.keys(conversations)[0] ?? null;
      return { conversations, activeConversationId, theme, customSkills };
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
        customSkills,
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
    return isThemePreference(parsed?.data?.theme) ? parsed.data.theme : 'system';
  } catch {
    return 'system';
  }
}
