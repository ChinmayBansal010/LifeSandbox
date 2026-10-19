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
});
