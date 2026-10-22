import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import Chat from '../components/Chat';
import type { Conversation } from '../types';

const mockConversation: Conversation = {
  id: 'conv-test-1',
  title: 'Attachment Test Conversation',
  messages: [],
  createdAt: Date.now(),
  updatedAt: Date.now(),
};

function renderChat(props: Partial<React.ComponentProps<typeof Chat>> = {}) {
  const onSendMessage = props.onSendMessage || vi.fn().mockResolvedValue('{}');
  const result = render(
    <Chat
      conversation={mockConversation}
      onSendMessage={onSendMessage}
      mem0Enabled={false}
      hostedMemoryAllowed={false}
      browserUseEnabled={false}
      sttEnabled={false}
      ttsEnabled={false}
      imageUnderstandingEnabled={false}
      isPending={false}
      theme="light"
      {...props}
    />
  );
  return { ...result, onSendMessage };
}

describe('Chat Attachment Readiness and Ingestion UX (DEV-02)', () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    originalFetch = globalThis.fetch;
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('1. Upload completion preserves processing status while extraction is in progress', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-101',
              filename: 'contract.pdf',
              status: 'processing',
              mime_type: 'application/pdf',
              size_bytes: 4096,
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            id: 'file-101',
            filename: 'contract.pdf',
            status: 'processing',
          }),
      });
    });

    renderChat();
    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file = new File(['dummy content'], 'contract.pdf', { type: 'application/pdf' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    expect(await screen.findByText('contract.pdf')).toBeInTheDocument();
    expect(screen.getByText('Processing…')).toBeInTheDocument();
    expect(screen.queryByText('Ready')).not.toBeInTheDocument();
  });

  it('2. Processing indicator remains visible until backend reports readiness', async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-102',
              filename: 'report.docx',
              status: 'processing',
              mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-102')) {
        callCount++;
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-102',
              filename: 'report.docx',
              status: callCount < 2 ? 'processing' : 'ready',
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderChat();
    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file = new File(['doc content'], 'report.docx', { type: 'text/plain' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    expect(await screen.findByText('Processing…')).toBeInTheDocument();

    // Advance 1 interval (still processing)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByText('Processing…')).toBeInTheDocument();

    // Advance 2nd interval (transition to ready)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(await screen.findByText('Ready')).toBeInTheDocument();
  });

  it('3. Polling stops when file reaches terminal ready state', async () => {
    let getPollCount = 0;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-103',
              filename: 'notes.txt',
              status: 'processing',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-103')) {
        getPollCount++;
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-103',
              filename: 'notes.txt',
              status: 'ready',
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderChat();
    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file = new File(['text'], 'notes.txt', { type: 'text/plain' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    // Advance timer to trigger first poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(await screen.findByText('Ready')).toBeInTheDocument();
    const pollCountAfterReady = getPollCount;
    expect(pollCountAfterReady).toBe(1);

    // Advance time further; polling should have stopped!
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(getPollCount).toBe(pollCountAfterReady);
  });

  it('4. Polling stops when ingestion fails', async () => {
    let getPollCount = 0;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-104',
              filename: 'bad.pdf',
              status: 'processing',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-104')) {
        getPollCount++;
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-104',
              filename: 'bad.pdf',
              status: 'error',
              error_message: 'Encrypted PDFs are not supported',
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderChat();
    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file = new File(['bad'], 'bad.pdf', { type: 'application/pdf' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(await screen.findByText('Failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry bad\.pdf/i })).toBeInTheDocument();
    const pollCountAfterFail = getPollCount;

    // Advance time further; polling should have stopped!
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(getPollCount).toBe(pollCountAfterFail);
  });

  it('5. Chat submission blocked while required attachments are not ready', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-105',
              filename: 'doc.txt',
              status: 'processing',
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            id: 'file-105',
            filename: 'doc.txt',
            status: 'processing',
          }),
      });
    });

    const onSendMessage = vi.fn().mockResolvedValue('{}');
    renderChat({ onSendMessage });

    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file = new File(['content'], 'doc.txt', { type: 'text/plain' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    const textarea = screen.getByLabelText(/message input/i) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Summarize this file' } });

    const sendButton = screen.getByLabelText(/send message/i);
    expect(sendButton).toBeDisabled();

    // Trying Enter key when unready
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSendMessage).not.toHaveBeenCalled();
    expect(textarea.value).toBe('Summarize this file');
  });

  it('6. Chat submission enabled after all required attachments become ready', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-106',
              filename: 'ready_doc.txt',
              status: 'processing',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-106')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-106',
              filename: 'ready_doc.txt',
              status: 'ready',
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const onSendMessage = vi.fn().mockResolvedValue('{}');
    renderChat({ onSendMessage });

    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file = new File(['content'], 'ready_doc.txt', { type: 'text/plain' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    const textarea = screen.getByLabelText(/message input/i) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Analyze ready_doc' } });

    // Transition to ready via timer
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(await screen.findByText('Ready')).toBeInTheDocument();
    const sendButton = screen.getByLabelText(/send message/i);
    expect(sendButton).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(sendButton);
    });

    expect(onSendMessage).toHaveBeenCalledTimes(1);
    expect(onSendMessage).toHaveBeenCalledWith(
      'Analyze ready_doc',
      false,
      false,
      expect.arrayContaining([
        expect.objectContaining({ id: 'file-106', status: 'ready' }),
      ])
    );
  });

  it('7. Preservation of message draft when submission is blocked or fails', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-107',
              filename: 'flaky.txt',
              status: 'ready',
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const onSendMessage = vi.fn().mockRejectedValue(new Error('One or more attached files are unavailable or not ready'));
    renderChat({ onSendMessage });

    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file = new File(['content'], 'flaky.txt', { type: 'text/plain' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    expect(await screen.findByText('Ready')).toBeInTheDocument();

    const textarea = screen.getByLabelText(/message input/i) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Critical prompt draft' } });

    const sendButton = screen.getByLabelText(/send message/i);
    await act(async () => {
      fireEvent.click(sendButton);
    });

    // Because onSendMessage failed, draft must be restored!
    expect(textarea.value).toBe('Critical prompt draft');
    expect(screen.getByText(/draft has been restored/i)).toBeInTheDocument();
  });

  it('8. A failed status request with recovery through retry', async () => {
    let pollCount = 0;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-108',
              filename: 'retryable.txt',
              status: 'processing',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-108/retry')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-108',
              filename: 'retryable.txt',
              status: 'ready',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-108')) {
        pollCount++;
        if (pollCount === 1) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                id: 'file-108',
                filename: 'retryable.txt',
                status: 'error',
                error_message: 'Temporary processing failure',
              }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-108',
              filename: 'retryable.txt',
              status: 'ready',
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderChat();
    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file = new File(['content'], 'retryable.txt', { type: 'text/plain' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(await screen.findByText('Failed')).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: /retry retryable\.txt/i });
    await act(async () => {
      fireEvent.click(retryButton);
    });

    expect(await screen.findByText('Ready')).toBeInTheDocument();
  });

  it('9. Cleanup of polling when component unmounts or attachment is removed', async () => {
    let pollCount = 0;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-109',
              filename: 'removable.txt',
              status: 'processing',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-109')) {
        pollCount++;
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-109',
              filename: 'removable.txt',
              status: 'processing',
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const { unmount } = renderChat();
    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file = new File(['content'], 'removable.txt', { type: 'text/plain' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    // Advance 1 poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(pollCount).toBe(1);

    // Remove the attachment
    const removeBtn = screen.getByRole('button', { name: /remove removable\.txt from this message/i });
    await act(async () => {
      fireEvent.click(removeBtn);
    });

    expect(screen.queryByText('removable.txt')).not.toBeInTheDocument();

    // Advance timers; no further polls should occur
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(pollCount).toBe(1);

    // Also unmounting shouldn't throw or leave lingering active intervals
    unmount();
  });

  it('10. Multiple attachments process independently without status mixing', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-A',
              filename: 'fileA.pdf',
              status: 'processing',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-A')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-A',
              filename: 'fileA.pdf',
              status: 'ready',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-B')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-B',
              filename: 'fileB.docx',
              status: 'processing',
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderChat();
    const fileInput = screen.getByLabelText(/upload files/i) as HTMLInputElement;
    const file1 = new File(['1'], 'fileA.pdf', { type: 'application/pdf' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file1] } });
    });

    // Now upload file B
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/files') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-B',
              filename: 'fileB.docx',
              status: 'processing',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-A')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-A',
              filename: 'fileA.pdf',
              status: 'ready',
            }),
        });
      }
      if (url.includes('/api/v1/files/file-B')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'file-B',
              filename: 'fileB.docx',
              status: 'processing',
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const file2 = new File(['2'], 'fileB.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file2] } });
    });

    // Advance 2s to poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(screen.getByText('fileA.pdf')).toBeInTheDocument();
    expect(screen.getByText('fileB.docx')).toBeInTheDocument();

    // fileA should be Ready, fileB should be Processing
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('Processing…')).toBeInTheDocument();

    // Submission should still be disabled because fileB is not ready
    const sendButton = screen.getByLabelText(/send message/i);
    expect(sendButton).toBeDisabled();
  });
});
