import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PluginsPanel from '../components/PluginsPanel';

const mockPlugins = {
  tools: [
    {
      id: 'analysis.compare_allocations',
      display_name: 'Compare Allocations',
      description: 'Compare financial allocation options.',
      category: 'finance',
      provider: 'built-in',
      version: '1.0.0',
      status: 'available',
      operations: ['analysis.compare_allocations'],
      permission_requirements: [],
      permission_labels: [],
      connection_required: null,
      configuration_guidance: 'Ready to use',
      read_only: true,
      risk: 'low',
      approval_required: false,
      returns_external_urls: false,
      input_schema: { type: 'object', properties: { options: { type: 'array' } } },
    },
    {
      id: 'calendar.list_events',
      display_name: 'List Calendar Events',
      description: 'Fetch user calendar events.',
      category: 'calendar',
      provider: 'google',
      version: '1.0.0',
      status: 'requires_connection',
      operations: ['calendar.list_events'],
      permission_requirements: ['https://www.googleapis.com/auth/calendar.readonly'],
      permission_labels: ['Read calendar events and availability'],
      connection_required: 'google',
      configuration_guidance: 'Connect Google account',
      read_only: true,
      risk: 'medium',
      approval_required: false,
      returns_external_urls: false,
    },
  ],
  refreshed_at: new Date().toISOString(),
};

describe('PluginsPanel Component', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/api/v1/plugins/executions')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ executions: [] }),
          });
        }
        if (url.includes('/api/v1/integrations')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ connections: [], configured: true }),
          });
        }
        if (url.includes('/api/v1/plugins')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockPlugins),
          });
        }
        return Promise.resolve({ ok: false, status: 404 });
      })
    );
  });

  it('renders plugin catalogue and displays fetched plugins', async () => {
    const handleClose = vi.fn();
    render(<PluginsPanel onClose={handleClose} />);

    await waitFor(() => {
      expect(screen.getByText('Compare Allocations')).toBeInTheDocument();
      expect(screen.getByText('List Calendar Events')).toBeInTheDocument();
    });

    expect(screen.getByText('2 Backend Plugins')).toBeInTheDocument();
  });

  it('filters plugins by search text', async () => {
    render(<PluginsPanel onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Compare Allocations')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search plugins/i);
    fireEvent.change(searchInput, { target: { value: 'calendar' } });

    await waitFor(() => {
      expect(screen.queryByText('Compare Allocations')).not.toBeInTheDocument();
      expect(screen.getByText('List Calendar Events')).toBeInTheDocument();
    });
  });

  it('invokes onUseInChat callback when "Try in Chat" is clicked', async () => {
    const handleUseInChat = vi.fn();
    render(<PluginsPanel onClose={vi.fn()} onUseInChat={handleUseInChat} />);

    await waitFor(() => {
      expect(screen.getByText('Compare Allocations')).toBeInTheDocument();
    });

    const tryButtons = screen.getAllByTitle(/pre-fill a chat prompt/i);
    expect(tryButtons.length).toBeGreaterThan(0);
    fireEvent.click(tryButtons[0]);

    expect(handleUseInChat).toHaveBeenCalled();
  });
});
