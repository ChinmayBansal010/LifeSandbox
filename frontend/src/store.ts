/* ─── Application store hook: Sequential Chats & State Orchestration ─── */

import { useCallback, useEffect, useSyncExternalStore } from 'react';
import type { AppState, ChatMessage, Conversation, CustomSkill, FileAttachment, ThemePreference } from './types';
import { createId } from './graph-utils';
import { loadState, saveState } from './persistence';

export function isUUID(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}

/**
 * Converts a sequence of server role/content messages into user/assistant ChatMessage pairs.
 */
export function parseBackendMessages(
  items: Array<{ id: string; role: string; content: string; created_at?: string }>
): ChatMessage[] {
  const result: ChatMessage[] = [];
  let pendingUser: { id: string; content: string; createdAt: number } | null = null;

  for (const item of items) {
    const createdAt = item.created_at ? new Date(item.created_at).getTime() || Date.now() : Date.now();
    if (item.role === 'user') {
      if (pendingUser) {
        result.push({
          id: pendingUser.id,
          userMessage: pendingUser.content,
          assistantMessage: '',
          createdAt: pendingUser.createdAt,
        });
      }
      pendingUser = { id: item.id, content: item.content, createdAt };
    } else if (item.role === 'assistant') {
      if (pendingUser) {
        result.push({
          id: pendingUser.id,
          userMessage: pendingUser.content,
          assistantMessage: item.content,
          createdAt: pendingUser.createdAt,
        });
        pendingUser = null;
      } else {
        result.push({
          id: item.id,
          userMessage: '',
          assistantMessage: item.content,
          createdAt,
        });
      }
    }
  }

  if (pendingUser) {
    result.push({
      id: pendingUser.id,
      userMessage: pendingUser.content,
      assistantMessage: '',
      createdAt: pendingUser.createdAt,
    });
  }

  return result;
}

/**
 * Reconciles parsed backend messages with any existing rich client metadata (traces, attachments, badges).
 */
export function reconcileMessages(
  backendMessages: ChatMessage[],
  existingMessages: ChatMessage[]
): ChatMessage[] {
  return backendMessages.map((bMsg) => {
    const existing = existingMessages.find(
      (e) => (e.id === bMsg.id) || (e.userMessage.trim() === bMsg.userMessage.trim() && e.assistantMessage.trim() === bMsg.assistantMessage.trim())
    );
    if (existing) {
      return {
        ...bMsg,
        traceId: existing.traceId ?? bMsg.traceId,
        toolsAccessed: existing.toolsAccessed ?? bMsg.toolsAccessed,
        skill: existing.skill ?? bMsg.skill,
        skillTrigger: existing.skillTrigger ?? bMsg.skillTrigger,
        intent: existing.intent ?? bMsg.intent,
        mem0OptIn: existing.mem0OptIn ?? bMsg.mem0OptIn,
        mem0SearchStatus: existing.mem0SearchStatus ?? bMsg.mem0SearchStatus,
        mem0SaveStatus: existing.mem0SaveStatus ?? bMsg.mem0SaveStatus,
        attachments: existing.attachments ?? bMsg.attachments,
      };
    }
    return bMsg;
  });
}

// ─── Singleton store state ─────────────────────────────────────────
let state: AppState = loadState();
let isPending = false;
let conversationsLoading = false;
let conversationsError: string | null = null;
let messagesLoading: Record<string, boolean> = {};
let messagesError: Record<string, string | null> = {};
let deletingId: string | null = null;
let deleteError: string | null = null;

const listeners = new Set<() => void>();

function getState(): AppState {
  return state;
}

function notify() {
  listeners.forEach((l) => l());
}

function setState(next: AppState) {
  state = next;
  saveState(state);
  notify();
}

function setIsPending(pending: boolean) {
  isPending = pending;
  notify();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function resetStoreForTesting(initialState?: AppState) {
  state = initialState || loadState();
  conversationsLoading = false;
  conversationsError = null;
  messagesLoading = {};
  messagesError = {};
  deletingId = null;
  deleteError = null;
  loadConversationsPromise = null;
  inFlightMessageFetches.clear();
  notify();
}

// ─── Server Sync & Actions ─────────────────────────────────────────
let loadConversationsPromise: Promise<void> | null = null;

export async function loadConversations(): Promise<void> {
  if (loadConversationsPromise) {
    return loadConversationsPromise;
  }

  conversationsLoading = true;
  conversationsError = null;
  notify();

  loadConversationsPromise = (async () => {
    try {
      const response = await fetch('/api/v1/conversations');
      if (!response.ok) {
        throw new Error(`Failed to load conversations (HTTP ${response.status})`);
      }
      const data = await response.json();
      const serverItems: Array<{ id: string; title: string; created_at: string; updated_at: string }> =
        Array.isArray(data.items) ? data.items : [];

      const currentConversations = { ...state.conversations };
      const serverIdSet = new Set(serverItems.map((s) => s.id));
      const nextConversations: Record<string, Conversation> = {};

      // 1. Incorporate server conversations
      for (const item of serverItems) {
        const existing = currentConversations[item.id] ||
          Object.values(currentConversations).find((c) => c.serverConversationId === item.id);

        const createdAt = item.created_at ? new Date(item.created_at).getTime() || Date.now() : Date.now();
        const updatedAt = item.updated_at ? new Date(item.updated_at).getTime() || Date.now() : Date.now();

        if (existing) {
          nextConversations[item.id] = {
            ...existing,
            id: item.id,
            serverConversationId: item.id,
            title: item.title || existing.title,
            createdAt: existing.createdAt || createdAt,
            updatedAt: Math.max(existing.updatedAt, updatedAt),
            isLocalOnly: false,
          };
        } else {
          nextConversations[item.id] = {
            id: item.id,
            serverConversationId: item.id,
            title: item.title || 'New chat',
            messages: [],
            createdAt,
            updatedAt,
            isLocalOnly: false,
            hasLoadedMessages: false,
          };
        }
      }

      // 2. Preserve any local-only conversations from browser localStorage
      for (const [id, conv] of Object.entries(currentConversations)) {
        if (!serverIdSet.has(id) && (!conv.serverConversationId || !serverIdSet.has(conv.serverConversationId))) {
          nextConversations[id] = {
            ...conv,
            isLocalOnly: true,
          };
        }
      }

      // 3. Reconcile active conversation ID
      let nextActiveId = state.activeConversationId;
      if (nextActiveId && !nextConversations[nextActiveId]) {
        nextActiveId = Object.keys(nextConversations)[0] ?? null;
      } else if (!nextActiveId && Object.keys(nextConversations).length > 0) {
        nextActiveId = Object.keys(nextConversations)[0];
      }

      state = {
        ...state,
        conversations: nextConversations,
        activeConversationId: nextActiveId,
      };
      saveState(state);
      conversationsLoading = false;
      conversationsError = null;
      notify();

      // Automatically fetch messages for the active conversation if it hasn't loaded yet
      if (
        nextActiveId &&
        nextConversations[nextActiveId] &&
        !nextConversations[nextActiveId].isLocalOnly &&
        !nextConversations[nextActiveId].hasLoadedMessages
      ) {
        void fetchMessages(nextActiveId);
      }
    } catch (err) {
      conversationsLoading = false;
      conversationsError = err instanceof Error ? err.message : 'Failed to load conversations';
      notify();
    } finally {
      loadConversationsPromise = null;
    }
  })();

  return loadConversationsPromise;
}

const inFlightMessageFetches = new Map<string, Promise<void>>();

export async function fetchMessages(conversationId: string, force = false): Promise<void> {
  const conv = state.conversations[conversationId];
  if (!conv) return;

  if (conv.isLocalOnly && !conv.serverConversationId) {
    if (!conv.hasLoadedMessages) {
      state = {
        ...state,
        conversations: {
          ...state.conversations,
          [conversationId]: { ...conv, hasLoadedMessages: true },
        },
      };
      notify();
    }
    return;
  }

  if (!force && inFlightMessageFetches.has(conversationId)) {
    return inFlightMessageFetches.get(conversationId);
  }

  if (!force && conv.hasLoadedMessages && conv.messages.length > 0) {
    return;
  }

  messagesLoading = { ...messagesLoading, [conversationId]: true };
  messagesError = { ...messagesError, [conversationId]: null };
  notify();

  const promise = (async () => {
    try {
      const targetId = conv.serverConversationId || conv.id;
      const res = await fetch(`/api/v1/conversations/${encodeURIComponent(targetId)}/messages`);
      if (!res.ok) {
        if (res.status === 404) {
          throw new Error('Conversation not found on server');
        }
        throw new Error(`Failed to load messages (HTTP ${res.status})`);
      }
      const data = await res.json();
      const items = Array.isArray(data.items) ? data.items : [];
      const backendMessages = parseBackendMessages(items);

      const currentConv = state.conversations[conversationId];
      if (currentConv) {
        const reconciled = reconcileMessages(backendMessages, currentConv.messages);
        state = {
          ...state,
          conversations: {
            ...state.conversations,
            [conversationId]: {
              ...currentConv,
              messages: reconciled,
              hasLoadedMessages: true,
            },
          },
        };
        saveState(state);
      }
      messagesLoading = { ...messagesLoading, [conversationId]: false };
      messagesError = { ...messagesError, [conversationId]: null };
      notify();
    } catch (err) {
      messagesLoading = { ...messagesLoading, [conversationId]: false };
      messagesError = {
        ...messagesError,
        [conversationId]: err instanceof Error ? err.message : 'Failed to load messages',
      };
      notify();
    } finally {
      inFlightMessageFetches.delete(conversationId);
    }
  })();

  inFlightMessageFetches.set(conversationId, promise);
  return promise;
}

export async function createConversation(title?: string): Promise<Conversation> {
  const now = Date.now();
  let serverId: string | null = null;
  let serverTitle = title || 'New chat';

  try {
    const res = await fetch('/api/v1/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (res.ok) {
      const data = await res.json();
      if (data && typeof data.id === 'string') {
        serverId = data.id;
        if (!title && data.title) {
          serverTitle = data.title;
        }
      }
    }
  } catch {
    // Offline or server down: fallback safely to local
  }

  const id = serverId || createId();
  const conversation: Conversation = {
    id,
    serverConversationId: serverId ?? undefined,
    title: serverTitle,
    messages: [],
    createdAt: now,
    updatedAt: now,
    isLocalOnly: !serverId,
    hasLoadedMessages: true,
  };

  state = {
    ...state,
    conversations: { ...state.conversations, [id]: conversation },
    activeConversationId: id,
  };
  saveState(state);
  notify();
  return conversation;
}

export async function deleteConversation(conversationId: string): Promise<boolean> {
  const conv = state.conversations[conversationId];
  if (!conv) return false;

  deletingId = conversationId;
  deleteError = null;
  notify();

  try {
    const isLocal = conv.isLocalOnly && !conv.serverConversationId;
    if (!isLocal) {
      const targetId = conv.serverConversationId || conv.id;
      const res = await fetch(`/api/v1/conversations/${encodeURIComponent(targetId)}`, {
        method: 'DELETE',
      });
      if (!res.ok && res.status !== 404) {
        let errMessage = `Server error (${res.status})`;
        try {
          const body = await res.json();
          errMessage = body.detail?.message || body.detail || errMessage;
        } catch {
          // ignore parse error
        }
        throw new Error(errMessage);
      }
    }

    // Only update state after server has confirmed deletion
    const newConversations = { ...state.conversations };
    delete newConversations[conversationId];

    const convIds = Object.keys(newConversations);
    state = {
      ...state,
      conversations: newConversations,
      activeConversationId:
        state.activeConversationId === conversationId
          ? convIds[0] ?? null
          : state.activeConversationId,
    };
    saveState(state);
    notify();
    return true;
  } catch (err) {
    deleteError = err instanceof Error ? err.message : 'Failed to delete conversation';
    notify();
    throw err;
  } finally {
    deletingId = null;
    notify();
  }
}

export function setActiveConversation(conversationId: string) {
  if (!state.conversations[conversationId]) return;
  state = { ...state, activeConversationId: conversationId };
  notify();

  const conv = state.conversations[conversationId];
  if (conv && !conv.isLocalOnly && !conv.hasLoadedMessages) {
    void fetchMessages(conversationId);
  }
}

export async function renameConversation(conversationId: string, title: string): Promise<void> {
  const conv = state.conversations[conversationId];
  if (!conv) return;

  const trimmed = title.trim();
  if (!trimmed) return;

  state = {
    ...state,
    conversations: {
      ...state.conversations,
      [conversationId]: { ...conv, title: trimmed, updatedAt: Date.now() },
    },
  };
  saveState(state);
  notify();

  if (!conv.isLocalOnly || conv.serverConversationId) {
    const targetId = conv.serverConversationId || conv.id;
    try {
      await fetch(`/api/v1/conversations/${encodeURIComponent(targetId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: trimmed }),
      });
    } catch {
      // Offline fallback: retains local title
    }
  }
}

export function clearDeleteError() {
  deleteError = null;
  notify();
}

function setTheme(theme: ThemePreference) {
  setState({ ...state, theme });
}

function saveCustomSkill(skill: {
  id?: string;
  name: string;
  description?: string;
  slash_command?: string;
  definition: string;
}): CustomSkill {
  const currentSkills = { ...(state.customSkills || {}) };
  const id = skill.id || createId();
  const now = Date.now();
  const existing = currentSkills[id];
  const slugified = (skill.slash_command || skill.name)
    .toLowerCase()
    .trim()
    .replace(/^[/]+/, '')
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'custom-skill';

  const newSkill: CustomSkill = {
    id,
    name: skill.name.trim(),
    description: (skill.description || '').trim(),
    slash_command: slugified,
    definition: skill.definition,
    createdAt: existing?.createdAt || now,
    updatedAt: now,
  };

  currentSkills[id] = newSkill;
  setState({ ...state, customSkills: currentSkills });
  return newSkill;
}

function deleteCustomSkill(id: string) {
  const currentSkills = { ...(state.customSkills || {}) };
  if (!currentSkills[id]) return;
  delete currentSkills[id];
  setState({ ...state, customSkills: currentSkills });
}

// ─── Hook ─────────────────────────────────────────────────────────
export function useStore() {
  const appState = useSyncExternalStore(subscribe, getState, getState);

  const activeConversation = appState.activeConversationId
    ? appState.conversations[appState.activeConversationId] ?? null
    : null;

  const sendMessage = useCallback(
    async (
      conversationId: string,
      userMessage: string,
      remember = false,
      browse = false,
      attachments: FileAttachment[] = [],
    ) => {
      if (isPending) return '{}';
      setIsPending(true);

      const messageId = createId();
      const now = Date.now();
      const currentConv = getState().conversations[conversationId];
      if (!currentConv) {
        setIsPending(false);
        return '{}';
      }

      const pendingMessage: ChatMessage = {
        id: messageId,
        userMessage,
        assistantMessage: '',
        createdAt: now,
        attachments,
      };

      const updatedTitle =
        currentConv.messages.length === 0
          ? userMessage.length > 35
            ? userMessage.slice(0, 35) + '…'
            : userMessage
          : currentConv.title;

      const updatedConversation: Conversation = {
        ...currentConv,
        title: updatedTitle,
        messages: [...currentConv.messages, pendingMessage],
        updatedAt: now,
      };

      setState({
        ...getState(),
        conversations: {
          ...getState().conversations,
          [conversationId]: updatedConversation,
        },
      });

      const controller = new AbortController();
      const requestTimeout = window.setTimeout(() => controller.abort(), 105_000);
      try {
        const history = currentConv.messages
          .filter((m) => m.assistantMessage.trim())
          .flatMap((m) => [
            { role: 'user', content: m.userMessage },
            { role: 'assistant', content: m.assistantMessage },
          ])
          .slice(-12);

        const targetServerId = currentConv.serverConversationId ?? (isUUID(currentConv.id) ? currentConv.id : null);

        const response = await fetch('/api/v1/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            message: userMessage,
            conversation_id: targetServerId,
            history,
            remember,
            browse,
            attachment_ids: attachments.map((file) => file.id),
          }),
        });

        const rawText = await response.text();
        let payload: any = null;
        if (rawText.trim()) {
          try {
            payload = JSON.parse(rawText);
          } catch {
            payload = null;
          }
        }

        if (!response.ok) {
          if (payload?.error?.failure_detail) {
            const detail = payload.error.failure_detail;
            throw Object.assign(new Error(payload.error.message || 'The assistant request failed.'), { failureDetail: detail });
          }
          const serverError =
            payload?.error?.message ??
            payload?.detail?.message ??
            payload?.detail ??
            (typeof payload?.error === 'string' ? payload.error : null) ??
            (rawText.length > 0 && rawText.length < 250 ? rawText : null) ??
            (response.status === 502 || response.status === 504
              ? 'Backend API server is not responding. Please make sure the FastAPI backend is running.'
              : `Server error (HTTP ${response.status} ${response.statusText || ''})`.trim());
          throw new Error(serverError || 'The assistant request failed.');
        }

        if (!payload || typeof payload.reply !== 'string' || !payload.reply.trim()) {
          throw new Error('The assistant returned an empty response.');
        }

        const returnedServerId = typeof payload.conversation_id === 'string' ? payload.conversation_id : null;
        const currentState = getState();
        const convToUpdate = currentState.conversations[conversationId];
        if (convToUpdate) {
          const updatedMessages = convToUpdate.messages.map((m) =>
            m.id === messageId
              ? {
                  ...m,
                  assistantMessage: payload.reply as string,
                  traceId: payload.trace_id as string | undefined,
                  toolsAccessed: payload.tools_accessed,
                  skill: payload.skill as string | undefined,
                  skillTrigger: payload.skill_trigger as string | undefined,
                  intent: payload.intent as string | undefined,
                  mem0OptIn: payload.mem0_opt_in as boolean | undefined,
                  mem0SearchStatus: payload.mem0_search_status,
                  mem0SaveStatus: payload.mem0_save_status,
                }
              : m
          );

          const canonicalId = returnedServerId || conversationId;
          const reconciledConv: Conversation = {
            ...convToUpdate,
            id: canonicalId,
            serverConversationId: returnedServerId || convToUpdate.serverConversationId,
            isLocalOnly: false,
            hasLoadedMessages: true,
            messages: updatedMessages,
            updatedAt: Date.now(),
          };

          const newConversations = { ...currentState.conversations };
          if (canonicalId !== conversationId) {
            delete newConversations[conversationId];
          }
          newConversations[canonicalId] = reconciledConv;

          setState({
            ...currentState,
            conversations: newConversations,
            activeConversationId:
              currentState.activeConversationId === conversationId
                ? canonicalId
                : currentState.activeConversationId,
          });
        }
        return JSON.stringify({ saved: payload.mem0_save_status === 'saved', search: payload.mem0_search_status, save: payload.mem0_save_status });
      } catch (error) {
        const currentState = getState();
        const convToUpdate = currentState.conversations[conversationId];
        const errorCode = error instanceof Error && error.name === 'AbortError'
          ? 'CHAT_CLIENT_TIMEOUT'
          : (error as Error & { failureDetail?: { provider?: string; stage?: string; code?: string } }).failureDetail?.stage === 'llm_generate'
            ? ((error as Error & { failureDetail?: { code?: string } }).failureDetail?.code === 'timeout' ? 'OPENROUTER_TIMEOUT' : 'OPENROUTER_FAILURE')
            : undefined;
        if (convToUpdate) {
          const message = errorCode === 'CHAT_CLIENT_TIMEOUT'
            ? 'Chat request timed out after 105s waiting for a response. Mem0 save was not completed.'
            : errorCode === 'OPENROUTER_TIMEOUT'
              ? 'Model response timed out (OpenRouter). Mem0 save was not attempted.'
              : errorCode === 'OPENROUTER_FAILURE'
                ? 'The model provider failed to generate a reply. Mem0 save was not attempted.'
                : error instanceof Error ? error.message : 'Please try again.';
          const updatedMessages = convToUpdate.messages.map((m) =>
            m.id === messageId
              ? {
                  ...m,
                  assistantMessage: `I couldn't get a response from the assistant. ${message}`,
                }
              : m
          );
          setState({
            ...currentState,
            conversations: {
              ...currentState.conversations,
              [conversationId]: {
                ...convToUpdate,
                messages: updatedMessages,
                updatedAt: Date.now(),
              },
            },
          });
        }
        return JSON.stringify({ saved: false, save: 'failed', error: errorCode });
      } finally {
        window.clearTimeout(requestTimeout);
        setIsPending(false);
      }
    },
    []
  );

  return {
    state: appState,
    activeConversation,
    isPending,

    // Sync & loading flags
    conversationsLoading,
    conversationsError,
    messagesLoading,
    messagesError,
    deletingId,
    deleteError,

    customSkills: appState.customSkills || {},

    // Actions
    loadConversations,
    fetchMessages,
    createConversation,
    deleteConversation,
    setActiveConversation,
    renameConversation,
    sendMessage,
    clearDeleteError,
    setTheme,
    saveCustomSkill,
    deleteCustomSkill,
  };
}

// ─── Theme effect hook ────────────────────────────────────────────
export function useThemeEffect(theme: ThemePreference) {
  useEffect(() => {
    const root = document.documentElement;

    function apply(isDark: boolean) {
      if (isDark) {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    }

    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      apply(mq.matches);
      const handler = (e: MediaQueryListEvent) => apply(e.matches);
      mq.addEventListener('change', handler);
      return () => mq.removeEventListener('change', handler);
    } else {
      apply(theme === 'dark');
    }
  }, [theme]);
}
