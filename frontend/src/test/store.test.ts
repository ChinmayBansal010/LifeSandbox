import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  parseBackendMessages,
  reconcileMessages,
  isUUID,
  loadConversations,
  fetchMessages,
  createConversation,
  deleteConversation,
  renameConversation,
  resetStoreForTesting,
} from '../store';
import type { ChatMessage } from '../types';

describe('store conversation synchronization and reconciliation', () => {
  beforeEach(() => {
    localStorage.clear();
    resetStoreForTesting();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('isUUID helper', () => {
    it('identifies valid and invalid UUIDs correctly', () => {
      expect(isUUID('12345678-1234-4234-8234-123456789abc')).toBe(true);
      expect(isUUID('local-conv-1')).toBe(false);
      expect(isUUID('')).toBe(false);
    });
  });

  describe('parseBackendMessages', () => {
    it('pairs alternating user and assistant messages into ChatMessage objects', () => {
      const serverItems = [
        { id: 'msg1', role: 'user', content: 'What is my budget?', created_at: '2026-10-22T08:00:00Z' },
        { id: 'msg2', role: 'assistant', content: 'Your budget is $2,000.', created_at: '2026-10-22T08:00:05Z' },
        { id: 'msg3', role: 'user', content: 'Can I spend $500?', created_at: '2026-10-22T08:01:00Z' },
        { id: 'msg4', role: 'assistant', content: 'Yes, you will have $1,500 left.', created_at: '2026-10-22T08:01:05Z' },
      ];

      const parsed = parseBackendMessages(serverItems);
      expect(parsed).toHaveLength(2);
      expect(parsed[0].userMessage).toBe('What is my budget?');
      expect(parsed[0].assistantMessage).toBe('Your budget is $2,000.');
      expect(parsed[1].userMessage).toBe('Can I spend $500?');
      expect(parsed[1].assistantMessage).toBe('Yes, you will have $1,500 left.');
    });

    it('handles standalone user message or trailing user message without assistant reply', () => {
      const serverItems = [
        { id: 'msg1', role: 'user', content: 'Pending prompt', created_at: '2026-10-22T08:00:00Z' },
      ];

      const parsed = parseBackendMessages(serverItems);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].userMessage).toBe('Pending prompt');
      expect(parsed[0].assistantMessage).toBe('');
    });

    it('handles standalone assistant message without preceding user message', () => {
      const serverItems = [
        { id: 'msg0', role: 'assistant', content: 'Welcome to LifeSandbox!', created_at: '2026-10-22T08:00:00Z' },
      ];

      const parsed = parseBackendMessages(serverItems);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].userMessage).toBe('');
      expect(parsed[0].assistantMessage).toBe('Welcome to LifeSandbox!');
    });
  });

  describe('reconcileMessages', () => {
    it('preserves rich in-memory metadata when matching backend messages', () => {
      const backendMessages: ChatMessage[] = [
        {
          id: 'msg1',
          userMessage: 'Help me evaluate savings',
          assistantMessage: 'Here is a projection table.',
          createdAt: 1700000000000,
        },
      ];

      const existingMessages: ChatMessage[] = [
        {
          id: 'msg1',
          userMessage: 'Help me evaluate savings',
          assistantMessage: 'Here is a projection table.',
          createdAt: 1700000000000,
          traceId: 'trace-1234',
          skill: 'budgeting',
          skillTrigger: 'slash_command',
          intent: 'conversation',
          mem0OptIn: true,
          mem0SaveStatus: 'saved',
          toolsAccessed: [
            {
              id: 'tool-1',
              tool_name: 'simulation',
              tool_type: 'deterministic',
              started_at: '2026-10-22T08:00:00Z',
              completed_at: '2026-10-22T08:00:01Z',
              duration_ms: 1000,
              status: 'success',
            },
          ],
        },
      ];

      const reconciled = reconcileMessages(backendMessages, existingMessages);
      expect(reconciled[0].traceId).toBe('trace-1234');
      expect(reconciled[0].skill).toBe('budgeting');
      expect(reconciled[0].toolsAccessed).toHaveLength(1);
      expect(reconciled[0].mem0SaveStatus).toBe('saved');
    });
  });

  describe('loadConversations API sync', () => {
    it('loads server conversations and merges without dropping local-only records', async () => {
      const localState = {
        version: 2,
        data: {
          conversations: {
            'local-draft-1': {
              id: 'local-draft-1',
              title: 'My Unsaved Local Draft',
              messages: [{ id: 'm1', userMessage: 'test', assistantMessage: 'test reply', createdAt: 1000 }],
              createdAt: 1000,
              updatedAt: 1000,
              isLocalOnly: true,
            },
          },
          activeConversationId: 'local-draft-1',
          theme: 'system',
        },
      };
      localStorage.setItem('life-sandbox-state', JSON.stringify(localState));
      resetStoreForTesting();

      // Mock /api/v1/conversations
      vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string) => {
        if (url === '/api/v1/conversations') {
          return {
            ok: true,
            json: async () => ({
              items: [
                {
                  id: 'c03260ef-64b3-460c-8064-0730d47343e5',
                  title: 'Server Conversation 1',
                  created_at: '2026-10-22T08:00:00Z',
                  updated_at: '2026-10-22T08:30:00Z',
                },
              ],
            }),
          };
        }
        if (url.includes('/messages')) {
          return {
            ok: true,
            json: async () => ({ items: [] }),
          };
        }
        return { ok: true, json: async () => ({}) };
      }));

      await loadConversations();

      const stored = JSON.parse(localStorage.getItem('life-sandbox-state') || '{}');
      const convs = stored.data.conversations;

      // Both the server conversation and the local-only draft exist!
      expect(convs['c03260ef-64b3-460c-8064-0730d47343e5']).toBeDefined();
      expect(convs['c03260ef-64b3-460c-8064-0730d47343e5'].title).toBe('Server Conversation 1');
      expect(convs['c03260ef-64b3-460c-8064-0730d47343e5'].isLocalOnly).toBe(false);

      expect(convs['local-draft-1']).toBeDefined();
      expect(convs['local-draft-1'].title).toBe('My Unsaved Local Draft');
      expect(convs['local-draft-1'].isLocalOnly).toBe(true);
    });

    it('handles server failure gracefully without wiping local conversations', async () => {
      const localState = {
        version: 2,
        data: {
          conversations: {
            'local-stay-1': {
              id: 'local-stay-1',
              title: 'Preserved Local Conversation',
              messages: [],
              createdAt: 1000,
              updatedAt: 1000,
              isLocalOnly: true,
            },
          },
          activeConversationId: 'local-stay-1',
          theme: 'system',
        },
      };
      localStorage.setItem('life-sandbox-state', JSON.stringify(localState));
      resetStoreForTesting();

      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network offline')));

      await expect(loadConversations()).resolves.toBeUndefined();

      // Ensure local state remains usable and untouched
      const stored = JSON.parse(localStorage.getItem('life-sandbox-state') || '{}');
      expect(stored.data.conversations['local-stay-1']).toBeDefined();
      expect(stored.data.conversations['local-stay-1'].title).toBe('Preserved Local Conversation');
    });
  });

  describe('fetchMessages', () => {
    it('loads messages from server and prevents cross-conversation pollution', async () => {
      vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string, opts?: any) => {
        if (opts?.method === 'POST' && url === '/api/v1/conversations') {
          return {
            ok: true,
            json: async () => ({ id: 'conv-A-uuid', title: 'Conversation A' }),
          };
        }
        if (url.includes('/api/v1/conversations/conv-A-uuid/messages')) {
          return {
            ok: true,
            json: async () => ({
              items: [
                { id: 'mA', role: 'user', content: 'Message for A', created_at: '2026-10-22T08:00:00Z' },
                { id: 'mAR', role: 'assistant', content: 'Reply for A', created_at: '2026-10-22T08:00:01Z' },
              ],
            }),
          };
        }
        if (url.includes('/api/v1/conversations/conv-B-uuid/messages')) {
          return {
            ok: true,
            json: async () => ({
              items: [
                { id: 'mB', role: 'user', content: 'Message for B', created_at: '2026-10-22T08:00:00Z' },
                { id: 'mBR', role: 'assistant', content: 'Reply for B', created_at: '2026-10-22T08:00:01Z' },
              ],
            }),
          };
        }
        return { ok: false, status: 404 };
      }));

      // Create conversation A
      const convA = await createConversation('Conversation A');

      // Change mock for second conversation
      vi.stubGlobal('fetch', vi.fn().mockImplementation(async (url: string, opts?: any) => {
        if (opts?.method === 'POST' && url === '/api/v1/conversations') {
          return {
            ok: true,
            json: async () => ({ id: 'conv-B-uuid', title: 'Conversation B' }),
          };
        }
        if (url.includes('/api/v1/conversations/conv-A-uuid/messages')) {
          return {
            ok: true,
            json: async () => ({
              items: [
                { id: 'mA', role: 'user', content: 'Message for A', created_at: '2026-10-22T08:00:00Z' },
                { id: 'mAR', role: 'assistant', content: 'Reply for A', created_at: '2026-10-22T08:00:01Z' },
              ],
            }),
          };
        }
        if (url.includes('/api/v1/conversations/conv-B-uuid/messages')) {
          return {
            ok: true,
            json: async () => ({
              items: [
                { id: 'mB', role: 'user', content: 'Message for B', created_at: '2026-10-22T08:00:00Z' },
                { id: 'mBR', role: 'assistant', content: 'Reply for B', created_at: '2026-10-22T08:00:01Z' },
              ],
            }),
          };
        }
        return { ok: false, status: 404 };
      }));

      const convB = await createConversation('Conversation B');

      // Fetch messages for A and B with force = true
      await fetchMessages(convA.id, true);
      await fetchMessages(convB.id, true);

      const stored = JSON.parse(localStorage.getItem('life-sandbox-state') || '{}');
      const convs = stored.data.conversations;

      // Ensure messages are strictly isolated
      expect(convs[convA.id].messages).toHaveLength(1);
      expect(convs[convA.id].messages[0]?.userMessage).toBe('Message for A');

      expect(convs[convB.id].messages).toHaveLength(1);
      expect(convs[convB.id].messages[0]?.userMessage).toBe('Message for B');
    });
  });

  describe('deleteConversation', () => {
    it('deletes on server first and updates local state only upon server confirmation', async () => {
      let serverDeleted = false;
      vi.stubGlobal('fetch', vi.fn().mockImplementation(async (_url: string, opts?: any) => {
        if (opts?.method === 'DELETE') {
          serverDeleted = true;
          return { ok: true, status: 204 };
        }
        return { ok: true, json: async () => ({ id: 'srv-del-1', title: 'To Delete' }) };
      }));

      const conv = await createConversation('To Delete');
      const success = await deleteConversation(conv.id);

      expect(success).toBe(true);
      expect(serverDeleted).toBe(true);

      const stored = JSON.parse(localStorage.getItem('life-sandbox-state') || '{}');
      expect(stored.data.conversations[conv.id]).toBeUndefined();
    });

    it('refuses to delete locally if server returns 500 error', async () => {
      vi.stubGlobal('fetch', vi.fn().mockImplementation(async (_url: string, opts?: any) => {
        if (opts?.method === 'DELETE') {
          return { ok: false, status: 500, json: async () => ({ detail: 'Database error' }) };
        }
        return { ok: true, json: async () => ({ id: 'srv-fail-1', title: 'Should Stay' }) };
      }));

      const conv = await createConversation('Should Stay');

      await expect(deleteConversation(conv.id)).rejects.toThrow();

      // Conversation must still be present in local state!
      const stored = JSON.parse(localStorage.getItem('life-sandbox-state') || '{}');
      expect(stored.data.conversations[conv.id]).toBeDefined();
    });
  });

  describe('renameConversation', () => {
    it('updates title and issues PATCH to server', async () => {
      let patchSent = false;
      let patchTitle = '';

      vi.stubGlobal('fetch', vi.fn().mockImplementation(async (_url: string, opts?: any) => {
        if (opts?.method === 'PATCH') {
          patchSent = true;
          patchTitle = JSON.parse(opts.body).title;
          return { ok: true, json: async () => ({ id: 'srv-rename-1', title: patchTitle }) };
        }
        return { ok: true, json: async () => ({ id: 'srv-rename-1', title: 'Original' }) };
      }));

      const conv = await createConversation('Original');
      await renameConversation(conv.id, 'Renamed Session Title');

      expect(patchSent).toBe(true);
      expect(patchTitle).toBe('Renamed Session Title');

      const stored = JSON.parse(localStorage.getItem('life-sandbox-state') || '{}');
      expect(stored.data.conversations[conv.id].title).toBe('Renamed Session Title');
    });
  });
});
