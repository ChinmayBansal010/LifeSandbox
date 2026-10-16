/* ─── Admin Panel: Developer Tool Observability & Trace Monitor ───────── */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Clock,
  Search,
  RefreshCw,
  Trash2,
  ChevronDown,
  ChevronRight,
  Terminal,
  Cpu,
  Database,
  Globe,
  Sliders,
  Sparkles,
  Copy,
  Check,
  AlertTriangle,
} from 'lucide-react';
import type { AdminStats, PromptTrace, ToolAccessItem } from '../types';
import { formatDuration, formatTimestamp } from '../graph-utils';

type AdminPanelProps = {
  onClose: () => void;
  initialSelectedTraceId?: string | null;
};

function ToolIcon({ toolName }: { toolName: string }) {
  if (toolName.includes('classifier') || toolName.includes('intent')) {
    return <Sliders size={14} className="text-fg-secondary" />;
  }
  if (toolName.includes('mem0') || toolName.includes('memory')) {
    return <Database size={14} className="text-fg-secondary" />;
  }
  if (toolName.includes('browser') || toolName.includes('web') || toolName.includes('research')) {
    return <Globe size={14} className="text-fg-secondary" />;
  }
  if (toolName.includes('llm') || toolName.includes('completion')) {
    return <Cpu size={14} className="text-fg-secondary" />;
  }
  if (toolName.includes('allocat') || toolName.includes('decision') || toolName.includes('compare')) {
    return <Sparkles size={14} className="text-fg-secondary" />;
  }
  return <Terminal size={14} className="text-fg-secondary" />;
}

function getToolBadgeColor(toolType: string, toolName: string) {
  if (toolName.includes('classifier')) {
    return 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20';
  }
  if (toolName.includes('mem0')) {
    return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
  }
  if (toolName.includes('browser')) {
    return 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20';
  }
  if (toolName.includes('llm')) {
    return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20';
  }
  if (toolType === 'decision_tool' || toolName.includes('allocat')) {
    return 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20';
  }
  return 'bg-surface border-border text-fg-secondary';
}

function JsonBlock({ data, label }: { data: unknown; label: string }) {
  const [copied, setCopied] = useState(false);
  const formatted = useMemo(() => {
    if (data === undefined || data === null) return 'null';
    if (typeof data === 'string') {
      try {
        const parsed = JSON.parse(data);
        return JSON.stringify(parsed, null, 2);
      } catch {
        return data;
      }
    }
    return JSON.stringify(data, null, 2);
  }, [data]);

  const copy = () => {
    navigator.clipboard.writeText(formatted).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg border border-border bg-bg-secondary overflow-hidden text-xs my-1.5">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-surface/50 text-[11px] font-medium text-fg-muted">
        <span>{label}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1 hover:text-fg transition-colors"
          title="Copy payload"
        >
          {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="p-3 overflow-x-auto text-[11px] font-mono leading-relaxed text-fg-secondary max-h-56 select-text whitespace-pre-wrap">
        {formatted}
      </pre>
    </div>
  );
}

function ToolEventCard({ event, index }: { event: ToolAccessItem; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const badgeClasses = getToolBadgeColor(event.tool_type, event.tool_name);

  return (
    <div className="border border-border rounded-xl bg-surface transition-all overflow-hidden mb-2">
      <div
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-surface-hover transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-[10px] font-mono text-fg-muted w-5 shrink-0">
            #{index + 1}
          </span>
          <div className="w-7 h-7 rounded-lg bg-bg-secondary border border-border flex items-center justify-center shrink-0">
            <ToolIcon toolName={event.tool_name} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold text-fg">
                {event.tool_name}
              </span>
              <span className={`text-[9px] px-2 py-0.5 rounded-full border font-medium ${badgeClasses}`}>
                {event.tool_type}
              </span>
              <span className={`text-[9px] px-1.5 py-0.2 rounded font-medium ${
                event.status === 'success'
                  ? 'bg-success/10 text-success'
                  : event.status === 'error'
                  ? 'bg-error/10 text-error'
                  : 'bg-amber-500/10 text-amber-500'
              }`}>
                {event.status}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-0.5 text-[10px] text-fg-muted font-mono">
              <span>{formatTimestamp(event.started_at)}</span>
              <span>→</span>
              <span>{formatTimestamp(event.completed_at)}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right">
            <span className="text-xs font-mono font-medium text-fg">
              {formatDuration(event.duration_ms)}
            </span>
          </div>
          <button
            className="p-1 text-fg-muted hover:text-fg"
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-3 pt-1 border-t border-border/60 bg-bg-secondary/40">
          {event.error && (
            <div className="p-2.5 rounded-lg bg-error/10 border border-error/20 text-error text-xs mb-2 flex items-start gap-2">
              <AlertTriangle size={14} className="shrink-0 mt-0.5" />
              <div className="font-mono text-[11px] whitespace-pre-wrap">{event.error}</div>
            </div>
          )}
          <div className="grid gap-2 md:grid-cols-2">
            {event.input_data !== undefined && (
              <JsonBlock data={event.input_data} label="Tool Input / Arguments" />
            )}
            {event.output_data !== undefined && (
              <JsonBlock data={event.output_data} label="Tool Output / Result" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminPanel({ onClose, initialSelectedTraceId }: AdminPanelProps) {
  const [traces, setTraces] = useState<PromptTrace[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [toolFilter, setToolFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(initialSelectedTraceId || null);

  const fetchTraces = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set('search', search.trim());
      if (toolFilter !== 'all') params.set('tool_filter', toolFilter);
      if (statusFilter !== 'all') params.set('status', statusFilter);

      const [tracesRes, statsRes] = await Promise.all([
        fetch(`/api/v1/admin/traces?${params.toString()}`),
        fetch('/api/v1/admin/stats'),
      ]);

      if (tracesRes.ok) {
        const data = await tracesRes.json();
        setTraces(data.items || []);
      }
      if (statsRes.ok) {
        const sdata = await statsRes.json();
        setStats(sdata);
      }
    } catch (err) {
      console.warn('Failed to fetch admin traces:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [search, toolFilter, statusFilter]);

  useEffect(() => {
    let ignore = false;
    const load = async () => {
      try {
        const params = new URLSearchParams();
        if (search.trim()) params.set('search', search.trim());
        if (toolFilter !== 'all') params.set('tool_filter', toolFilter);
        if (statusFilter !== 'all') params.set('status', statusFilter);

        const [tracesRes, statsRes] = await Promise.all([
          fetch(`/api/v1/admin/traces?${params.toString()}`),
          fetch('/api/v1/admin/stats'),
        ]);

        if (ignore) return;
        if (tracesRes.ok) {
          const data = await tracesRes.json();
          setTraces(data.items || []);
        }
        if (statsRes.ok) {
          const sdata = await statsRes.json();
          setStats(sdata);
        }
      } catch (err) {
        console.warn('Failed to fetch admin traces:', err);
      } finally {
        if (!ignore) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    };
    load();
    return () => {
      ignore = true;
    };
  }, [search, toolFilter, statusFilter]);

  // Live auto-refresh polling every 3 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchTraces(true);
    }, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchTraces]);

  const handleClearLogs = async () => {
    if (!confirm('Are you sure you want to clear all prompt tool access traces?')) return;
    try {
      await fetch('/api/v1/admin/traces', { method: 'DELETE' });
      fetchTraces();
    } catch (err) {
      console.warn('Failed to clear traces:', err);
    }
  };

  const toolOptions = useMemo(() => {
    const tools = new Set<string>();
    traces.forEach((t) => {
      (t.tools_accessed || []).forEach((tool) => {
        if (tool.tool_name) tools.add(tool.tool_name);
      });
    });
    return Array.from(tools).sort();
  }, [traces]);

  return (
    <div className="flex flex-col h-full bg-bg overflow-hidden animate-fade-in">
      {/* ─── Header ─────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-bg-secondary/60 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg border border-border bg-surface hover:bg-surface-hover text-fg-muted hover:text-fg transition-colors"
            title="Back to chat"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-accent" />
              <h1 className="text-base font-bold text-fg">Developer Admin Panel</h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-accent-muted text-accent">
                Tool Tracing
              </span>
            </div>
            <p className="text-xs text-fg-muted mt-0.5">
              Live monitoring of tools accessed during user prompt processing with millisecond timestamps
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Live indicator toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
              autoRefresh
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30'
                : 'bg-surface border-border text-fg-muted hover:text-fg'
            }`}
            title={autoRefresh ? 'Live updates enabled' : 'Click to enable live auto-updates'}
          >
            <span className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-emerald-500 animate-pulse' : 'bg-fg-muted'}`} />
            <span>{autoRefresh ? 'LIVE (3s)' : 'PAUSED'}</span>
          </button>

          {/* Manual refresh button */}
          <button
            onClick={() => fetchTraces()}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-surface hover:bg-surface-hover text-fg text-xs font-medium transition-colors disabled:opacity-50"
            title="Refresh now"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin text-accent' : ''} />
            <span>Refresh</span>
          </button>

          {/* Clear logs button */}
          <button
            onClick={handleClearLogs}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-surface hover:bg-error/10 hover:text-error hover:border-error/30 text-fg-muted text-xs font-medium transition-colors"
            title="Clear all logs"
          >
            <Trash2 size={13} />
            <span>Clear Logs</span>
          </button>
        </div>
      </header>

      {/* ─── Main Content ───────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {/* ─── Metrics Stats Bar ───────────────────────────────── */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4" aria-label="System Metrics">
          <div className="p-4 rounded-2xl bg-surface border border-border shadow-xs">
            <span className="text-[11px] font-medium text-fg-muted uppercase tracking-wider block">
              Total Prompts Processed
            </span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-fg">
                {stats?.total_prompts ?? traces.length}
              </span>
              <span className="text-[11px] text-fg-muted">runs</span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-surface border border-border shadow-xs">
            <span className="text-[11px] font-medium text-fg-muted uppercase tracking-wider block">
              Tool Invocations
            </span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-accent">
                {stats?.total_tool_calls ?? 0}
              </span>
              <span className="text-[11px] text-fg-muted">events</span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-surface border border-border shadow-xs">
            <span className="text-[11px] font-medium text-fg-muted uppercase tracking-wider block">
              Avg Processing Latency
            </span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-fg">
                {stats?.avg_duration_ms ? `${stats.avg_duration_ms}ms` : '-'}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-surface border border-border shadow-xs">
            <span className="text-[11px] font-medium text-fg-muted uppercase tracking-wider block">
              Active Tools Tracked
            </span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-fg">
                {Object.keys(stats?.tool_breakdown || {}).length}
              </span>
              <span className="text-[11px] text-fg-muted">types</span>
            </div>
          </div>
        </section>

        {/* ─── Search & Filters Bar ────────────────────────────── */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-2xl bg-surface border border-border">
          <div className="flex-1 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by prompt text, tool name, or ID…"
              className="w-full bg-bg-secondary rounded-lg pl-9 pr-3 py-1.5 text-xs text-fg placeholder:text-fg-muted border border-transparent focus:border-accent focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <select
              value={toolFilter}
              onChange={(e) => setToolFilter(e.target.value)}
              className="bg-bg-secondary rounded-lg px-2.5 py-1.5 text-xs text-fg border border-border focus:border-accent focus:outline-none"
            >
              <option value="all">All Tools</option>
              {toolOptions.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-bg-secondary rounded-lg px-2.5 py-1.5 text-xs text-fg border border-border focus:border-accent focus:outline-none"
            >
              <option value="all">All Status</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="running">Running</option>
            </select>
          </div>
        </div>

        {/* ─── Traces List ─────────────────────────────────────── */}
        <section className="space-y-3" aria-label="Prompt Processing Runs">
          <div className="flex items-center justify-between text-xs text-fg-muted px-1">
            <span className="font-medium">
              Showing {traces.length} Prompt Trace{traces.length !== 1 ? 's' : ''}
            </span>
            <span>Click any prompt to inspect tool execution sequence & parameters</span>
          </div>

          {loading ? (
            <div className="p-12 text-center text-fg-muted text-xs">
              <RefreshCw size={20} className="animate-spin text-accent mx-auto mb-2" />
              Loading tool execution logs…
            </div>
          ) : traces.length === 0 ? (
            <div className="p-12 rounded-2xl border border-dashed border-border bg-surface/50 text-center">
              <Activity size={28} className="text-fg-muted mx-auto mb-3 opacity-40" />
              <h3 className="text-sm font-semibold text-fg mb-1">No prompt traces recorded yet</h3>
              <p className="text-xs text-fg-muted max-w-sm mx-auto">
                Send a user prompt in the chat. Every tool accessed during prompt processing will be recorded here with timestamps and execution details.
              </p>
            </div>
          ) : (
            traces.map((trace) => {
              const isExpanded = expandedTraceId === trace.id;
              const tools = trace.tools_accessed || [];

              return (
                <div
                  key={trace.id}
                  id={`trace-${trace.id}`}
                  className={`rounded-2xl border transition-all ${
                    isExpanded
                      ? 'border-accent/40 bg-surface shadow-sm ring-1 ring-accent/20'
                      : 'border-border bg-surface hover:border-accent/30'
                  }`}
                >
                  {/* Prompt summary header row */}
                  <div
                    onClick={() => setExpandedTraceId(isExpanded ? null : trace.id)}
                    className="p-4 cursor-pointer flex items-start justify-between gap-4"
                  >
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <div className="mt-0.5">
                        {trace.status === 'completed' ? (
                          <CheckCircle2 size={16} className="text-success" />
                        ) : trace.status === 'failed' ? (
                          <XCircle size={16} className="text-error" />
                        ) : (
                          <Clock size={16} className="text-amber-500 animate-spin" />
                        )}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <span className="text-xs font-semibold text-fg">
                            Prompt:
                          </span>
                          <span className="text-xs text-fg font-medium truncate max-w-xl">
                            "{trace.prompt}"
                          </span>
                        </div>

                        {/* Tools accessed pills */}
                        <div className="flex items-center gap-1.5 flex-wrap mt-2">
                          <span className="text-[10px] text-fg-muted font-medium">Tools used:</span>
                          {tools.length === 0 ? (
                            <span className="text-[10px] text-fg-muted italic">No tools called</span>
                          ) : (
                            tools.map((t, idx) => (
                              <span
                                key={t.id || idx}
                                className={`text-[10px] font-mono px-2 py-0.5 rounded-md border font-medium ${getToolBadgeColor(
                                  t.tool_type,
                                  t.tool_name
                                )}`}
                              >
                                {t.tool_name} ({formatDuration(t.duration_ms)})
                              </span>
                            ))
                          )}
                        </div>

                        <div className="flex items-center gap-3 mt-2 text-[10px] text-fg-muted font-mono">
                          <span>Started: {trace.started_at ? new Date(trace.started_at).toLocaleString() : '-'}</span>
                          {trace.completed_at && (
                            <span>• Completed: {formatTimestamp(trace.completed_at)}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <span className="text-xs font-mono font-bold text-fg block">
                          {formatDuration(trace.total_duration_ms)}
                        </span>
                        <span className="text-[10px] text-fg-muted">
                          {tools.length} tool{tools.length !== 1 ? 's' : ''}
                        </span>
                      </div>
                      <div className="p-1 rounded-md text-fg-muted hover:text-fg">
                        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      </div>
                    </div>
                  </div>

                  {/* Expanded Trace Waterfall & Details */}
                  {isExpanded && (
                    <div className="px-5 pb-5 pt-2 border-t border-border/60 bg-bg-secondary/30 rounded-b-2xl animate-fade-in">
                      <div className="flex items-center justify-between mb-3 text-xs">
                        <span className="font-semibold text-fg flex items-center gap-1.5">
                          <Terminal size={14} className="text-accent" />
                          Tool Execution Waterfall ({tools.length} calls)
                        </span>
                        <span className="text-[10px] font-mono text-fg-muted">
                          Trace ID: {trace.id}
                        </span>
                      </div>

                      {trace.error && (
                        <div className="p-3 rounded-xl bg-error/10 border border-error/20 text-error text-xs mb-3 flex items-start gap-2">
                          <AlertTriangle size={15} className="shrink-0 mt-0.5" />
                          <div className="font-mono text-[11px] whitespace-pre-wrap leading-relaxed">
                            {trace.error}
                          </div>
                        </div>
                      )}

                      {/* Tool events sequence */}
                      {tools.length === 0 ? (
                        <p className="text-xs text-fg-muted italic py-3 text-center">
                          No tool calls were invoked for this prompt.
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {tools.map((event, idx) => (
                            <ToolEventCard key={event.id || idx} event={event} index={idx} />
                          ))}
                        </div>
                      )}

                      {/* Response Preview */}
                      {trace.response_preview && (
                        <div className="mt-3">
                          <span className="text-[11px] font-semibold text-fg block mb-1">
                            Assistant Response:
                          </span>
                          <div className="p-3 rounded-xl bg-surface border border-border text-xs text-fg-secondary leading-relaxed whitespace-pre-wrap max-h-36 overflow-y-auto">
                            {trace.response_preview}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </section>
      </div>
    </div>
  );
}
