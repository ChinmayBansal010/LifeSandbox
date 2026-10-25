import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Chat from '../components/Chat';
import type { Conversation } from '../types';

const mockConversation: Conversation = {
  id: 'conv-1',
  title: 'Test Conversation',
  messages: [],
  createdAt: Date.now(),
  updatedAt: Date.now(),
};

describe('Chat Component Composer Controls (Issue #1)', () => {
  it('displays Setup required when Mem0 and Browser Use are not configured', () => {
    const handleSendMessage = vi.fn().mockResolvedValue('{}');
    render(
      <Chat
        conversation={mockConversation}
        onSendMessage={handleSendMessage}
        mem0Enabled={false}
        hostedMemoryAllowed={false}
        browserUseEnabled={false}
        sttEnabled={false}
        ttsEnabled={false}
        imageUnderstandingEnabled={false}
        isPending={false}
        theme="light"
      />
    );

    const switches = screen.getAllByRole('switch');
    expect(switches).toHaveLength(2);

    const mem0Switch = screen.getByRole('switch', { name: /Mem0 hosted memory/i });
    const browserSwitch = screen.getByRole('switch', { name: /Browser Use research/i });

    expect(mem0Switch).toBeDisabled();
    expect(browserSwitch).toBeDisabled();

    // Verify badges display Setup required
    const setupRequiredBadges = screen.getAllByText('Setup required');
    expect(setupRequiredBadges.length).toBeGreaterThanOrEqual(2);
  });

  it('displays Ready when configured and toggles On for this reply independently', () => {
    const handleSendMessage = vi.fn().mockResolvedValue('{}');
    render(
      <Chat
        conversation={mockConversation}
        onSendMessage={handleSendMessage}
        mem0Enabled={true}
        hostedMemoryAllowed={true}
        browserUseEnabled={true}
        sttEnabled={false}
        ttsEnabled={false}
        imageUnderstandingEnabled={false}
        isPending={false}
        theme="light"
      />
    );

    const mem0Switch = screen.getByRole('switch', { name: /Mem0 hosted memory/i });
    const browserSwitch = screen.getByRole('switch', { name: /Browser Use research/i });

    expect(mem0Switch).toBeEnabled();
    expect(browserSwitch).toBeEnabled();

    // Both start unchecked and ready
    expect(mem0Switch).not.toBeChecked();
    expect(browserSwitch).not.toBeChecked();
    expect(screen.getAllByText('Ready')).toHaveLength(2);

    // Toggle Mem0 switch
    fireEvent.click(mem0Switch);
    expect(mem0Switch).toBeChecked();
    expect(browserSwitch).not.toBeChecked(); // independent
    expect(screen.getByText('On for this reply')).toBeInTheDocument();
    expect(screen.getByText('1 enabled')).toBeInTheDocument();

    // Toggle Browser switch
    fireEvent.click(browserSwitch);
    expect(browserSwitch).toBeChecked();
    expect(screen.getAllByText('On for this reply')).toHaveLength(2);
    expect(screen.getByText('2 enabled')).toBeInTheDocument();
  });

  it('passes enabled integration flags to onSendMessage and resets them after sending', async () => {
    const handleSendMessage = vi.fn().mockResolvedValue(JSON.stringify({ saved: true }));
    render(
      <Chat
        conversation={mockConversation}
        onSendMessage={handleSendMessage}
        mem0Enabled={true}
        hostedMemoryAllowed={true}
        browserUseEnabled={true}
        sttEnabled={false}
        ttsEnabled={false}
        imageUnderstandingEnabled={false}
        isPending={false}
        theme="light"
      />
    );

    const mem0Switch = screen.getByRole('switch', { name: /Mem0 hosted memory/i });
    const browserSwitch = screen.getByRole('switch', { name: /Browser Use research/i });
    const input = screen.getByLabelText(/Message input/i);
    const sendButton = screen.getByLabelText(/Send message/i);

    // Turn both on
    fireEvent.click(mem0Switch);
    fireEvent.click(browserSwitch);
    expect(mem0Switch).toBeChecked();
    expect(browserSwitch).toBeChecked();

    // Type a prompt
    fireEvent.change(input, { target: { value: 'Research and remember this' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(handleSendMessage).toHaveBeenCalledWith(
        'Research and remember this',
        true, // remember
        true, // browse
        []    // attachments
      );
    });

    // Verify controls reset after send
    expect(mem0Switch).not.toBeChecked();
    expect(browserSwitch).not.toBeChecked();
  });
});
