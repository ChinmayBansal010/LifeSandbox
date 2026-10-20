/* ─── PluginsPanel: Dynamic Registry-Backed Plugin & Capabilities Manager ── */

import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Blocks,
  RefreshCw,
  Search,
  X,
  CheckSquare,
  Calculator,
  Calendar,
  Mail,
  ExternalLink,
  ShieldAlert,
  Code,
  Sparkles,
  Clock,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  Activity,
  AlertCircle,
  Plug,
} from 'lucide-react';
import type { PluginCapability, PluginExecution, CapabilityStatus } from '../types';

type PluginsPanelProps = {
  onClose: () => void;
  onUseInChat?: (suggestedPrompt: string) => void;
};

type ViewTab = 'catalogue' | 'executions' | 'connections';

const CATEGORY_ICONS: Record<string, typeof Blocks> = {
  analysis: Calculator,
  planning: CheckSquare,
  calendar: Calendar,
  email: Mail,
  research: ExternalLink,
};

const STATUS_LABELS: Record<CapabilityStatus, { label: string; color: string; bg: string }> = {
  available: {
    label: 'Available',
    color: 'text-emerald-500 dark:text-emerald-400',
    bg: 'bg-emerald-500/10 border-emerald-500/25',
  },
  connected: {
    label: 'Connected',
    color: 'text-blue-500 dark:text-blue-400',
    bg: 'bg-blue-500/10 border-blue-500/25',
  },
  requires_setup: {
    label: 'Needs Server Setup',
    color: 'text-amber-500 dark:text-amber-400',
    bg: 'bg-amber-500/10 border-amber-500/25',
  },
  requires_connection: {
    label: 'Connect Account',
    color: 'text-orange-500 dark:text-orange-400',
    bg: 'bg-orange-500/10 border-orange-500/25',
  },
  permission_required: {
    label: 'Permission Needed',
    color: 'text-purple-500 dark:text-purple-400',
    bg: 'bg-purple-500/10 border-purple-500/25',
  },
  disabled: {
    label: 'Disabled',
    color: 'text-zinc-500 dark:text-zinc-400',
    bg: 'bg-zinc-500/10 border-zinc-500/25',
  },
  unavailable: {
    label: 'Unavailable',
    color: 'text-red-500 dark:text-red-400',
    bg: 'bg-red-500/10 border-red-500/25',
  },
  degraded: {
    label: 'Degraded',
    color: 'text-yellow-500 dark:text-yellow-400',
    bg: 'bg-yellow-500/10 border-yellow-500/25',
  },
};

const SUGGESTED_PROMPTS: Record<string, string> = {
  'analysis.compare_allocations':
    'Compare allocations: rent $1500, groceries $600, savings $900 out of a total $3000 budget.',
  'calendar.find_free_time':
    'Check my calendar to find free time this Friday afternoon.',
  'calendar.list_events':
    'List my upcoming calendar events and meetings for this week.',
  'followthrough.create_task':
    'Create a high-priority task for me: Prepare quarterly budget review by Friday.',
  'followthrough.list_tasks':
    'List all my current pending tasks and priorities.',
  'followthrough.create_reminder':
    'Set an in-app reminder to review project deadline tomorrow at 10:00 AM.',
  'followthrough.list_reminders':
    'What reminders do I currently have scheduled?',
  'gmail.search_messages':
    'Search my email inbox for messages regarding project deliverables.',
  'gmail.get_thread':
    'Find and show the email thread regarding project updates.',
  'gmail.create_draft':
    'Draft a polite email to team@company.com with subject "Status Sync" asking for feedback.',
  'gmail.send_draft':
    'Help me draft and send an email update to my team after I review the draft.',
  'research.search':
    'Search the web for the latest benchmarks and architecture patterns in agentic workflows.',
};

export default function PluginsPanel({ onClose, onUseInChat }: PluginsPanelProps) {
  const [plugins, setPlugins] = useState<PluginCapability[]>([]);
  const [executions, setExecutions] = useState<PluginExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ViewTab>('catalogue');

  // Search & filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedProvider, setSelectedProvider] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [expandedSchemaTool, setExpandedSchemaTool] = useState<string | null>(null);

  // Google connections sub-state
  const [connections, setConnections] = useState<Array<{ id: string; account_email?: string; capabilities: string[]; status: string }>>([]);
  const [googleConfigured, setGoogleConfigured] = useState(false);
  const [connectionCapabilities, setConnectionCapabilities] = useState<string[]>([
    'calendar.read',
    'gmail.read',
  ]);
  const [connectionBusy, setConnectionBusy] = useState(false);

  const fetchPluginsData = useCallback(async () => {
    setError(null);
    try {
      const [pluginsRes, executionsRes, integrationsRes] = await Promise.all([
        fetch('/api/v1/plugins', { credentials: 'include' }),
        fetch('/api/v1/plugins/executions?limit=30', { credentials: 'include' }),
        fetch('/api/v1/integrations', { credentials: 'include' }),
      ]);

      if (!pluginsRes.ok) {
        let msg = `HTTP ${pluginsRes.status} ${pluginsRes.statusText || ''}`.trim();
        try {
          const errData = await pluginsRes.json();
          msg = errData?.detail?.message || (typeof errData?.detail === 'string' ? errData.detail : msg);
        } catch {
          if (pluginsRes.status === 502 || pluginsRes.status === 504) {
            msg = 'Backend server is not reachable on port 8000. Please ensure the FastAPI backend is running.';
          }
        }
        throw new Error(`Failed to load plugin catalogue (${msg})`);
      }

      const pluginsData = await pluginsRes.json();
      setPlugins(pluginsData.tools || []);

      if (executionsRes.ok) {
        const executionsData = await executionsRes.json();
        setExecutions(executionsData.executions || []);
      }

      if (integrationsRes.ok) {
        const integrationsData = await integrationsRes.json();
        setConnections(integrationsData.connections || []);
        setGoogleConfigured(integrationsData.configured === true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to connect to backend plugins');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchPluginsData();

    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'GOOGLE_CONNECTED') {
        fetchPluginsData();
      }
    };
    window.addEventListener('message', handleMessage);

    const params = new URLSearchParams(window.location.search);
    if (params.get('integration') === 'google_connected') {
      params.delete('integration');
      const query = params.toString();
      window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
      setActiveTab('connections');
    }

    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [fetchPluginsData]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchPluginsData();
  };

  // Derive unique categories and providers dynamically from backend data
  const categories = useMemo(() => {
    const set = new Set<string>();
    plugins.forEach((p) => {
      if (p.category) set.add(p.category);
    });
    return Array.from(set).sort();
  }, [plugins]);

  const providers = useMemo(() => {
    const set = new Set<string>();
    plugins.forEach((p) => {
      if (p.provider) set.add(p.provider);
    });
    return Array.from(set).sort();
  }, [plugins]);

  // Filtered plugins
  const filteredPlugins = useMemo(() => {
    return plugins.filter((plugin) => {
      // Category filter
      if (selectedCategory !== 'all' && plugin.category !== selectedCategory) return false;

      // Provider filter
      if (selectedProvider !== 'all' && plugin.provider !== selectedProvider) return false;

      // Status filter
      if (selectedStatus !== 'all' && plugin.status !== selectedStatus) return false;

      // Text search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = plugin.display_name.toLowerCase().includes(q);
        const matchesId = plugin.id.toLowerCase().includes(q);
        const matchesDesc = plugin.description.toLowerCase().includes(q);
        const matchesOps = plugin.operations.some((op) => op.toLowerCase().includes(q));
        if (!matchesName && !matchesId && !matchesDesc && !matchesOps) return false;
      }

      return true;
    });
  }, [plugins, selectedCategory, selectedProvider, selectedStatus, searchQuery]);

  // Metrics
  const metrics = useMemo(() => {
    const total = plugins.length;
    const availableOrConnected = plugins.filter(
      (p) => p.status === 'available' || p.status === 'connected'
    ).length;
    const requiresAction = plugins.filter(
      (p) => p.status === 'requires_setup' || p.status === 'requires_connection' || p.status === 'permission_required'
    ).length;
    const approvalRequired = plugins.filter((p) => p.approval_required).length;
    return { total, availableOrConnected, requiresAction, approvalRequired };
  }, [plugins]);

  const handleConnectGoogle = async () => {
    setConnectionBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/integrations/google/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ capabilities: connectionCapabilities }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.message || data?.detail || 'Could not initialize Google OAuth');
      }
      if (data.authorization_url) {
        const popup = window.open(
          data.authorization_url,
          'google_oauth',
          'width=600,height=700,status=no,toolbar=no,menubar=no'
        );
        if (!popup) {
          window.location.href = data.authorization_url;
          return;
        }
        const pollInterval = setInterval(async () => {
          if (popup.closed) {
            clearInterval(pollInterval);
            setConnectionBusy(false);
            await fetchPluginsData();
          } else {
            try {
              const checkRes = await fetch('/api/v1/integrations', { credentials: 'include' });
              if (checkRes.ok) {
                const checkData = await checkRes.json();
                if ((checkData.connections || []).length > connections.length) {
                  clearInterval(pollInterval);
                  popup.close();
                  setConnectionBusy(false);
                  await fetchPluginsData();
                }
              }
            } catch {
              // Ignore polling errors
            }
          }
        }, 1500);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not initialize Google OAuth');
      setConnectionBusy(false);
    }
  };

  const handleDisconnectGoogle = async (connectionId: string) => {
    if (!window.confirm('Disconnect this Google account? Saved scopes will be removed.')) return;
    setConnectionBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/integrations/${connectionId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail?.message || data?.detail || 'Could not disconnect account');
      }
      await fetchPluginsData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not disconnect account');
    } finally {
      setConnectionBusy(false);
    }
  };

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-bg text-fg">
      {/* ─── Top Header ────────────────────────────────────────── */}
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-4 shrink-0 shadow-2xs">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-fg shadow-xs">
            <Blocks size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-fg">Plugins & Tools</h1>
              <span className="rounded-full bg-accent-muted px-2 py-0.5 font-mono text-[11px] font-semibold text-accent">
                {plugins.length} Backend Plugins
              </span>
            </div>
            <p className="text-xs text-fg-muted">
              Dynamically discovered from the backend tool registry. Model-callable schemas and live provider integration.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-bg px-3 py-1.5 text-xs font-medium text-fg-secondary hover:bg-surface-hover hover:text-fg transition-colors disabled:opacity-50"
            title="Refresh backend plugins and connection statuses"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin text-accent' : ''} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-bg px-3 py-1.5 text-xs font-semibold text-fg hover:bg-surface-hover transition-colors"
          >
            <X size={15} />
            <span>Close</span>
          </button>
        </div>
      </header>

      {/* ─── Metrics Sub-bar ──────────────────────────────────── */}
      <div className="border-b border-border bg-bg-secondary px-6 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-5">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span className="font-semibold text-fg">{metrics.availableOrConnected}</span>
              <span className="text-fg-muted">Ready / Connected</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-500" />
              <span className="font-semibold text-fg">{metrics.requiresAction}</span>
              <span className="text-fg-muted">Requires Setup/Auth</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-accent" />
              <span className="font-semibold text-fg">{metrics.approvalRequired}</span>
              <span className="text-fg-muted">Approval-Gated</span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-1 rounded-lg bg-surface p-1 border border-border">
            <button
              type="button"
              onClick={() => setActiveTab('catalogue')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'catalogue'
                  ? 'bg-accent text-accent-fg font-semibold shadow-2xs'
                  : 'text-fg-secondary hover:text-fg'
              }`}
            >
              <Blocks size={13} />
              <span>Plugin Catalogue ({plugins.length})</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('executions')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'executions'
                  ? 'bg-accent text-accent-fg font-semibold shadow-2xs'
                  : 'text-fg-secondary hover:text-fg'
              }`}
            >
              <Activity size={13} />
              <span>Activity & Traces ({executions.length})</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('connections')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                activeTab === 'connections'
                  ? 'bg-accent text-accent-fg font-semibold shadow-2xs'
                  : 'text-fg-secondary hover:text-fg'
              }`}
            >
              <Plug size={13} />
              <span>OAuth Connections</span>
            </button>
          </div>
        </div>
      </div>

      {/* Error notification banner */}
      {error && (
        <div className="flex items-center justify-between gap-2 border-b border-error/30 bg-error/10 px-6 py-2.5 text-xs text-error">
          <div className="flex items-center gap-2">
            <AlertCircle size={15} className="shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="hover:underline font-semibold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ─── Main Content Area ─────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center text-center">
            <RefreshCw size={24} className="animate-spin text-accent mb-3" />
            <p className="text-sm font-medium text-fg">Loading plugins from backend registry…</p>
            <p className="text-xs text-fg-muted mt-1">Connecting to /api/v1/plugins</p>
          </div>
        ) : activeTab === 'catalogue' ? (
          <div className="space-y-6 max-w-7xl mx-auto">
            {/* Filter and Search Bar */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
              {/* Search input */}
              <div className="relative flex-1 max-w-md">
                <Search
                  size={14}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted"
                />
                <input
                  type="text"
                  placeholder="Search plugins by name, ID, or operation…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-xl border border-border bg-surface pl-9 pr-3 py-2 text-xs text-fg placeholder:text-fg-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/30 transition-colors shadow-2xs"
                />
              </div>

              {/* Filter selections */}
              <div className="flex flex-wrap items-center gap-2">
                {/* Category Filter */}
                <div className="flex items-center gap-1 rounded-lg border border-border bg-surface p-1 text-xs">
                  <span className="text-[10px] text-fg-muted uppercase font-semibold px-1.5">
                    Category:
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedCategory('all')}
                    className={`rounded-md px-2 py-0.5 text-xs transition-colors ${
                      selectedCategory === 'all'
                        ? 'bg-accent text-accent-fg font-semibold'
                        : 'text-fg-secondary hover:text-fg'
                    }`}
                  >
                    All
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setSelectedCategory(cat)}
                      className={`capitalize rounded-md px-2 py-0.5 text-xs transition-colors ${
                        selectedCategory === cat
                          ? 'bg-accent text-accent-fg font-semibold'
                          : 'text-fg-secondary hover:text-fg'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                {/* Status Filter */}
                <select
                  value={selectedStatus}
                  onChange={(e) => setSelectedStatus(e.target.value)}
                  className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-fg focus:border-accent focus:outline-none"
                  aria-label="Filter by status"
                >
                  <option value="all">All Statuses</option>
                  <option value="available">Available</option>
                  <option value="connected">Connected</option>
                  <option value="requires_setup">Needs Server Setup</option>
                  <option value="requires_connection">Requires Connection</option>
                  <option value="disabled">Disabled</option>
                </select>

                {/* Provider Filter */}
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-fg focus:border-accent focus:outline-none"
                  aria-label="Filter by provider"
                >
                  <option value="all">All Providers</option>
                  {providers.map((p) => (
                    <option key={p} value={p}>
                      {p.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Plugin Cards Grid */}
            {filteredPlugins.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border p-12 text-center">
                {error ? (
                  <>
                    <AlertCircle size={32} className="mx-auto text-error mb-3" />
                    <h3 className="text-sm font-semibold text-fg">Unable to load plugins from backend</h3>
                    <p className="text-xs text-error max-w-md mx-auto mt-1 leading-relaxed">
                      {error}
                    </p>
                    <div className="mt-4 flex items-center justify-center gap-2">
                      <button
                        type="button"
                        onClick={handleRefresh}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-accent text-accent-fg px-3.5 py-1.5 text-xs font-semibold hover:bg-accent-hover transition-colors shadow-2xs"
                      >
                        <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
                        <span>Retry Connection</span>
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <Blocks size={32} className="mx-auto text-fg-muted mb-3 opacity-40" />
                    <h3 className="text-sm font-semibold text-fg">No matching plugins found</h3>
                    <p className="text-xs text-fg-muted mt-1">
                      Try adjusting your search query or clearing the category and provider filters.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setSearchQuery('');
                        setSelectedCategory('all');
                        setSelectedProvider('all');
                        setSelectedStatus('all');
                      }}
                      className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-surface border border-border px-3 py-1.5 text-xs font-semibold text-fg hover:bg-surface-hover"
                    >
                      Reset all filters
                    </button>
                  </>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredPlugins.map((plugin) => {
                  const Icon = CATEGORY_ICONS[plugin.category] || Blocks;
                  const statusInfo = STATUS_LABELS[plugin.status] || STATUS_LABELS.available;
                  const isExpanded = expandedSchemaTool === plugin.id;
                  const promptSuggestion = SUGGESTED_PROMPTS[plugin.id] || `Use the ${plugin.display_name} tool.`;

                  return (
                    <div
                      key={plugin.id}
                      className="group flex flex-col justify-between rounded-2xl border border-border bg-surface p-4 shadow-2xs hover:border-accent/40 hover:shadow-xs transition-all"
                    >
                      <div>
                        {/* Top Badge Row */}
                        <div className="flex items-start justify-between gap-2 mb-2.5">
                          <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-muted text-accent">
                              <Icon size={16} />
                            </div>
                            <div>
                              <h3 className="text-sm font-semibold text-fg group-hover:text-accent transition-colors leading-tight">
                                {plugin.display_name}
                              </h3>
                              <span className="font-mono text-[10px] text-fg-muted">
                                {plugin.id}
                              </span>
                            </div>
                          </div>

                          <span
                            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusInfo.bg} ${statusInfo.color}`}
                          >
                            <span className="h-1.5 w-1.5 rounded-full bg-current" />
                            {statusInfo.label}
                          </span>
                        </div>

                        {/* Description */}
                        <p className="text-xs text-fg-secondary leading-relaxed mb-3">
                          {plugin.description}
                        </p>

                        {/* Meta Tags */}
                        <div className="flex flex-wrap items-center gap-1.5 mb-3 text-[10px]">
                          <span className="rounded-md bg-bg-secondary px-2 py-0.5 font-medium uppercase text-fg-muted">
                            {plugin.category}
                          </span>
                          <span className="rounded-md bg-bg-secondary px-2 py-0.5 font-medium uppercase text-fg-muted">
                            {plugin.provider}
                          </span>
                          <span className="rounded-md bg-bg-secondary px-2 py-0.5 text-fg-muted">
                            {plugin.read_only ? 'Read-only' : 'State Modifying'}
                          </span>
                          {plugin.approval_required && (
                            <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/10 text-amber-500 px-2 py-0.5 font-semibold">
                              <ShieldAlert size={10} />
                              Approval Required
                            </span>
                          )}
                        </div>

                        {/* Configuration guidance / connection note */}
                        {plugin.configuration_guidance && plugin.status !== 'available' && plugin.status !== 'connected' && (
                          <div className="mb-3 rounded-lg border border-border bg-bg-secondary/60 p-2 text-[11px] text-fg-muted">
                            <span className="font-semibold text-fg block mb-0.5">Setup Guidance:</span>
                            {plugin.configuration_guidance}
                          </div>
                        )}

                        {/* Operations */}
                        <div className="mb-3">
                          <span className="text-[10px] font-semibold text-fg-muted uppercase tracking-wider block mb-1">
                            Callable Operations:
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {plugin.operations.map((op) => (
                              <code
                                key={op}
                                className="rounded bg-bg-secondary border border-border px-1.5 py-0.5 text-[10px] text-accent font-mono"
                              >
                                {op}
                              </code>
                            ))}
                          </div>
                        </div>

                        {/* Permissions requirement */}
                        {plugin.permission_labels.length > 0 && (
                          <div className="mb-3 text-[11px] text-fg-muted">
                            <span className="font-semibold text-fg">Required Scope: </span>
                            {plugin.permission_labels.join(', ')}
                          </div>
                        )}

                        {/* Expandable JSON Schema Inspector */}
                        {isExpanded && plugin.input_schema && (
                          <div className="mt-3 rounded-xl border border-border bg-bg p-3 animate-fade-in text-xs">
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="font-mono text-[10px] text-fg-muted font-semibold">
                                INPUT PARAMETERS SCHEMA
                              </span>
                              <span className="text-[10px] text-fg-muted">JSON Schema</span>
                            </div>
                            <pre className="max-h-40 overflow-auto font-mono text-[10px] text-fg bg-surface p-2 rounded-lg border border-border leading-tight">
                              {JSON.stringify(plugin.input_schema, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>

                      {/* Card Action Footer */}
                      <div className="mt-3 pt-3 border-t border-border flex items-center justify-between gap-2">
                        <button
                          type="button"
                          onClick={() => setExpandedSchemaTool(isExpanded ? null : plugin.id)}
                          className="flex items-center gap-1 text-[11px] text-fg-muted hover:text-fg font-medium transition-colors"
                        >
                          <Code size={12} />
                          <span>{isExpanded ? 'Hide Schema' : 'Inspect Schema'}</span>
                          {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>

                        {onUseInChat && (
                          <button
                            type="button"
                            onClick={() => {
                              onUseInChat(promptSuggestion);
                              onClose();
                            }}
                            className="inline-flex items-center gap-1 rounded-lg bg-accent text-accent-fg px-2.5 py-1 text-xs font-semibold hover:bg-accent-hover transition-colors shadow-2xs"
                            title="Pre-fill a chat prompt using this plugin"
                          >
                            <Sparkles size={12} />
                            <span>Try in Chat</span>
                            <ArrowRight size={11} />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : activeTab === 'executions' ? (
          /* ─── Executions Log Tab ──────────────────────────────────── */
          <div className="max-w-5xl mx-auto space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-fg">Recent Tool Execution Traces</h2>
                <p className="text-xs text-fg-muted">
                  Recorded from real-time agent invocations via /api/v1/plugins/executions. Private payloads are sanitized.
                </p>
              </div>
              <button
                type="button"
                onClick={handleRefresh}
                className="flex items-center gap-1 rounded-lg border border-border bg-surface px-2.5 py-1 text-xs text-fg hover:bg-surface-hover"
              >
                <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
                <span>Refresh Activity</span>
              </button>
            </div>

            {executions.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border p-12 text-center">
                <Clock size={32} className="mx-auto text-fg-muted mb-3 opacity-40" />
                <h3 className="text-sm font-semibold text-fg">No recent plugin executions</h3>
                <p className="text-xs text-fg-muted mt-1">
                  Send a prompt in chat that triggers a decision or follow-through tool to see execution telemetry here.
                </p>
              </div>
            ) : (
              <div className="rounded-2xl border border-border bg-surface overflow-hidden shadow-2xs">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-border bg-bg-secondary text-[11px] font-semibold text-fg-muted uppercase">
                    <tr>
                      <th className="px-4 py-2.5">Tool / Plugin</th>
                      <th className="px-4 py-2.5">Provider</th>
                      <th className="px-4 py-2.5">Status</th>
                      <th className="px-4 py-2.5">Duration</th>
                      <th className="px-4 py-2.5">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {executions.map((ex, idx) => (
                      <tr key={ex.id ?? `${ex.tool_id}-${idx}`} className="hover:bg-surface-hover/50 transition-colors">
                        <td className="px-4 py-3">
                          <span className="font-semibold text-fg block">{ex.display_name}</span>
                          <code className="text-[10px] text-fg-muted font-mono">{ex.tool_id}</code>
                        </td>
                        <td className="px-4 py-3 capitalize text-fg-secondary">
                          <span className="rounded bg-bg-secondary px-1.5 py-0.5 text-[10px] font-mono border border-border">
                            {ex.provider}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              ex.status === 'success' || ex.status === 'completed'
                                ? 'bg-emerald-500/10 text-emerald-500'
                                : ex.status === 'running'
                                ? 'bg-blue-500/10 text-blue-500'
                                : 'bg-red-500/10 text-red-500'
                            }`}
                          >
                            <span className="h-1.5 w-1.5 rounded-full bg-current" />
                            {ex.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-[11px] text-fg-muted">
                          {ex.duration_ms ? `${ex.duration_ms} ms` : '—'}
                        </td>
                        <td className="px-4 py-3 text-[11px] text-fg-muted">
                          {ex.started_at ? new Date(ex.started_at).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          /* ─── OAuth Connections Tab ────────────────────────────────── */
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="rounded-2xl border border-border bg-surface p-6 shadow-2xs">
              <div className="flex items-center gap-2.5 mb-2">
                <Mail size={18} className="text-accent" />
                <h2 className="text-base font-bold text-fg">Google Account Integrations</h2>
              </div>
              <p className="text-xs text-fg-secondary leading-relaxed mb-4">
                Connect your Google account to grant permission for Google Calendar reads, free-busy scheduling, and Gmail search/drafting. Credentials are encrypted at rest with AES-256.
              </p>

              {!googleConfigured && (
                <div className="mb-4 rounded-xl border border-amber-500/25 bg-amber-500/10 p-3 text-xs text-amber-500">
                  <span className="font-semibold block mb-0.5">Server Notice:</span>
                  Google OAuth client credentials and encryption keys are not yet configured on this server instance.
                </div>
              )}

              <div className="mb-4">
                <span className="text-xs font-semibold text-fg block mb-2">
                  Select Desired Permissions:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {[
                    ['calendar.read', 'Read Calendar events & free time'],
                    ['gmail.read', 'Search and read Gmail threads'],
                    ['gmail.draft', 'Create Gmail drafts for you'],
                    ['gmail.send', 'Send emails (Strictly approval-gated)'],
                  ].map(([value, label]) => (
                    <label
                      key={value}
                      className="flex items-center gap-2 rounded-lg border border-border bg-bg p-2.5 hover:bg-surface-hover cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={connectionCapabilities.includes(value)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setConnectionCapabilities((curr) => [
                              ...new Set([
                                ...curr,
                                value,
                                ...(value === 'gmail.send' ? ['gmail.draft'] : []),
                              ]),
                            ]);
                          } else {
                            setConnectionCapabilities((curr) =>
                              curr.filter(
                                (item) =>
                                  item !== value &&
                                  !(value === 'gmail.draft' && item === 'gmail.send')
                              )
                            );
                          }
                        }}
                        className="rounded border-border text-accent focus:ring-accent"
                      />
                      <span className="text-fg">{label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <button
                type="button"
                onClick={handleConnectGoogle}
                disabled={!googleConfigured || connectionBusy || connectionCapabilities.length === 0}
                className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-accent-fg hover:bg-accent-hover disabled:opacity-50 transition-colors shadow-xs"
              >
                <Plug size={14} />
                <span>Connect Google Account</span>
              </button>
            </div>

            {/* Active Connections List */}
            <div className="rounded-2xl border border-border bg-surface p-6 shadow-2xs">
              <h3 className="text-sm font-bold text-fg mb-3">Active Connected Accounts</h3>
              {connections.length === 0 ? (
                <p className="text-xs text-fg-muted">No Google accounts currently connected.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {connections.map((conn) => (
                    <li key={conn.id} className="flex items-center justify-between py-3">
                      <div>
                        <span className="font-semibold text-sm text-fg block">
                          {conn.account_email || 'Google Account'}
                        </span>
                        <span className="text-xs text-fg-muted">
                          Scopes: {conn.capabilities.join(', ')} · Status: {conn.status}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDisconnectGoogle(conn.id)}
                        disabled={connectionBusy}
                        className="rounded-lg border border-error/30 text-error hover:bg-error/10 px-3 py-1.5 text-xs font-semibold transition-colors"
                      >
                        Disconnect
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
