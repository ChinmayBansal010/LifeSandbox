/* ─── Application store hook: Sequential Chats & State Orchestration ─── */

import { useCallback, useEffect, useSyncExternalStore } from 'react';
import type { AppState, ChatMessage, Conversation, ThemePreference } from './types';
import { createId } from './graph-utils';
import { loadState, saveState } from './persistence';

// ─── Singleton store ──────────────────────────────────────────────
let state: AppState = loadState();
let isPending = false;
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

// ─── Actions ──────────────────────────────────────────────────────
function createConversation(title?: string): Conversation {
  const id = createId();
  const now = Date.now();
  const conversation: Conversation = {
    id,
    title: title || 'New chat',
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
  setState({
    ...state,
    conversations: { ...state.conversations, [id]: conversation },
    activeConversationId: id,
  });
  return conversation;
}

function deleteConversation(conversationId: string) {
  const conv = state.conversations[conversationId];
  if (!conv) return;

  const newConversations = { ...state.conversations };
  delete newConversations[conversationId];

  const convIds = Object.keys(newConversations);
  setState({
    ...state,
    conversations: newConversations,
    activeConversationId:
      state.activeConversationId === conversationId
        ? convIds[0] ?? null
        : state.activeConversationId,
  });
}

function setActiveConversation(conversationId: string) {
  if (!state.conversations[conversationId]) return;
  setState({ ...state, activeConversationId: conversationId });
}

function renameConversation(conversationId: string, title: string) {
  const conv = state.conversations[conversationId];
  if (!conv) return;
  setState({
    ...state,
    conversations: {
      ...state.conversations,
      [conversationId]: { ...conv, title, updatedAt: Date.now() },
    },
  });
}

function setTheme(theme: ThemePreference) {
  setState({ ...state, theme });
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
    ) => {
      if (isPending) return false;
      setIsPending(true);

      const messageId = createId();
      const now = Date.now();
      const currentConv = getState().conversations[conversationId];
      if (!currentConv) {
        setIsPending(false);
        return false;
      }

      const pendingMessage: ChatMessage = {
        id: messageId,
        userMessage,
        assistantMessage: '',
        createdAt: now,
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

        const response = await fetch('/api/v1/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            message: userMessage,
            conversation_id: currentConv.serverConversationId ?? null,
            history,
            remember,
            browse,
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
                }
              : m
          );
          setState({
            ...currentState,
            conversations: {
              ...currentState.conversations,
              [conversationId]: {
                ...convToUpdate,
                serverConversationId: payload.conversation_id,
                messages: updatedMessages,
                updatedAt: Date.now(),
              },
            },
          });
        }
        return payload.memory_saved === true;
      } catch (error) {
        const currentState = getState();
        const convToUpdate = currentState.conversations[conversationId];
        if (convToUpdate) {
          const message =
            error instanceof Error && error.name === 'AbortError'
              ? 'The request timed out after 105 seconds. Check the backend log and try again.'
              : error instanceof Error
                ? error.message
                : 'Please try again.';
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
        return false;
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

    // Actions
    createConversation,
    deleteConversation,
    setActiveConversation,
    renameConversation,
    sendMessage,
    setTheme,
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
