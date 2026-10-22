import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Sidebar from '../components/Sidebar';
import type { Conversation } from '../types';

const mockConversations: Record<string, Conversation> = {
  conv1: {
    id: 'conv1',
    title: 'Career Switch Scenario',
    messages: [],
    createdAt: Date.now() - 1000,
    updatedAt: Date.now() - 1000,
  },
  conv2: {
    id: 'conv2',
    title: 'Budget Allocation',
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  },
};

describe('Sidebar Component', () => {
  it('renders conversations and triggers selection', () => {
    const handleSelect = vi.fn();
    render(
      <Sidebar
        conversations={mockConversations}
        activeConversationId="conv1"
        theme="system"
        collapsed={false}
        onToggleCollapse={vi.fn()}
        onCreateConversation={vi.fn()}
        onSelectConversation={handleSelect}
        onDeleteConversation={vi.fn()}
        onOpenAdminPanel={vi.fn()}
        onOpenLifePanel={vi.fn()}
        onOpenPlugins={vi.fn()}
        onSetTheme={vi.fn()}
      />
    );

    expect(screen.getByText('Career Switch Scenario')).toBeInTheDocument();
    expect(screen.getByText('Budget Allocation')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Budget Allocation'));
    expect(handleSelect).toHaveBeenCalledWith('conv2');
  });

  it('triggers onOpenPlugins when "Plugins & Tools" button is clicked', () => {
    const handleOpenPlugins = vi.fn();
    render(
      <Sidebar
        conversations={mockConversations}
        activeConversationId={null}
        theme="system"
        collapsed={false}
        onToggleCollapse={vi.fn()}
        onCreateConversation={vi.fn()}
        onSelectConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
        onOpenAdminPanel={vi.fn()}
        onOpenLifePanel={vi.fn()}
        onOpenPlugins={handleOpenPlugins}
        onSetTheme={vi.fn()}
      />
    );

    const pluginsButton = screen.getByText('Plugins & Tools');
    fireEvent.click(pluginsButton);
    expect(handleOpenPlugins).toHaveBeenCalled();
  });

  it('renders loading indicator when isLoading is true and no conversations exist', () => {
    render(
      <Sidebar
        conversations={{}}
        activeConversationId={null}
        theme="system"
        collapsed={false}
        isLoading={true}
        onToggleCollapse={vi.fn()}
        onCreateConversation={vi.fn()}
        onSelectConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
        onOpenAdminPanel={vi.fn()}
        onOpenLifePanel={vi.fn()}
        onOpenPlugins={vi.fn()}
        onSetTheme={vi.fn()}
      />
    );

    expect(screen.getByText('Loading chats…')).toBeInTheDocument();
  });

  it('renders error state and invokes onRetryLoad when Retry button is clicked', () => {
    const handleRetry = vi.fn();
    render(
      <Sidebar
        conversations={{}}
        activeConversationId={null}
        theme="system"
        collapsed={false}
        error="Failed to load conversations (HTTP 500)"
        onRetryLoad={handleRetry}
        onToggleCollapse={vi.fn()}
        onCreateConversation={vi.fn()}
        onSelectConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
        onOpenAdminPanel={vi.fn()}
        onOpenLifePanel={vi.fn()}
        onOpenPlugins={vi.fn()}
        onSetTheme={vi.fn()}
      />
    );

    expect(screen.getByText('Failed to load chats')).toBeInTheDocument();
    expect(screen.getByText('Failed to load conversations (HTTP 500)')).toBeInTheDocument();

    const retryButton = screen.getByText('Retry');
    fireEvent.click(retryButton);
    expect(handleRetry).toHaveBeenCalled();
  });

  it('renders "Local" badge for browser-only conversations', () => {
    const localConversations: Record<string, Conversation> = {
      local1: {
        id: 'local1',
        title: 'Draft Scenario in Browser',
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        isLocalOnly: true,
      },
    };

    render(
      <Sidebar
        conversations={localConversations}
        activeConversationId="local1"
        theme="system"
        collapsed={false}
        onToggleCollapse={vi.fn()}
        onCreateConversation={vi.fn()}
        onSelectConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
        onOpenAdminPanel={vi.fn()}
        onOpenLifePanel={vi.fn()}
        onOpenPlugins={vi.fn()}
        onSetTheme={vi.fn()}
      />
    );

    expect(screen.getByText('Local')).toBeInTheDocument();
  });

  it('renders delete error banner and allows dismissing it', () => {
    const handleClear = vi.fn();
    render(
      <Sidebar
        conversations={mockConversations}
        activeConversationId="conv1"
        theme="system"
        collapsed={false}
        deleteError="Server rejected conversation deletion"
        onClearDeleteError={handleClear}
        onToggleCollapse={vi.fn()}
        onCreateConversation={vi.fn()}
        onSelectConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
        onOpenAdminPanel={vi.fn()}
        onOpenLifePanel={vi.fn()}
        onOpenPlugins={vi.fn()}
        onSetTheme={vi.fn()}
      />
    );

    expect(screen.getByText('Server rejected conversation deletion')).toBeInTheDocument();
    const dismissButton = screen.getByLabelText('Dismiss error');
    fireEvent.click(dismissButton);
    expect(handleClear).toHaveBeenCalled();
  });
});
