/* ─── Admin Panel: Developer Observability, Data Flow Architecture & Skill Matrix ─── */

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
  GitBranch,
  Layers,
  ArrowRight,
  Zap,
  Command,
  Table as TableIcon,
  Play,
  HelpCircle,
} from 'lucide-react';
import type { AdminStats, PromptTrace, ToolAccessItem, SkillItem } from '../types';
import { formatDuration, formatTimestamp } from '../graph-utils';

type AdminPanelProps = {
  onClose: () => void;
  initialSelectedTraceId?: string | null;
};

const DEFAULT_SKILLS: SkillItem[] = [
  {
    name: 'budgeting',
    description: 'Budget and spending trade-offs',
    keywords: ['budget', 'save', 'money', 'cost', 'salary'],
    instructions: 'Separate stated facts from estimates. Do not assume risk tolerance.',
    tools: ['simulation'],
    slash_command: '/budgeting',
  },
  {
    name: 'career',
    description: 'Career decisions',
    keywords: ['career', 'job', 'offer', 'internship'],
    instructions: 'Compare goals, growth, compensation and constraints.',
    tools: ['research'],
    slash_command: '/career',
  },
  {
    name: 'education',
    description: 'Learning and education planning',
    keywords: ['study', 'learn', 'exam', 'course'],
    instructions: 'Break goals into realistic milestones and account for available time.',
    tools: [],
    slash_command: '/education',
  },
  {
    name: 'purchasing',
    description: 'Purchase decisions',
    keywords: ['buy', 'purchase', 'laptop', 'phone'],
    instructions: 'Compare requirements, total cost and alternatives.',
    tools: ['research', 'simulation'],
    slash_command: '/purchasing',
  },
  {
    name: 'travel',
    description: 'Travel planning',
    keywords: ['travel', 'trip', 'move', 'relocate'],
    instructions: 'Clarify dates, budget and flexibility before current claims.',
    tools: ['research', 'simulation'],
    slash_command: '/travel',
  },
  {
    name: 'time_management',
    description: 'Time and commitment planning',
    keywords: ['schedule', 'time', 'prioritize', 'commitment'],
    instructions: 'Respect existing commitments and avoid overloading the schedule.',
    tools: [],
    slash_command: '/time-management',
  },
];

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
  const [activeTab, setActiveTab] = useState<'diagram' | 'traces'>('diagram');
  const [traces, setTraces] = useState<PromptTrace[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [skills, setSkills] = useState<SkillItem[]>(DEFAULT_SKILLS);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [toolFilter, setToolFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(initialSelectedTraceId || null);

  // Skill Simulator state
  const [simulatorInput, setSimulatorInput] = useState('/budgeting Help me save $500 monthly from my salary');
  const [selectedSkillDetails, setSelectedSkillDetails] = useState<SkillItem | null>(DEFAULT_SKILLS[0]);

  // Fetch traces and stats
  const fetchTraces = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set('search', search.trim());
      if (toolFilter !== 'all') params.set('tool_filter', toolFilter);
      if (statusFilter !== 'all') params.set('status', statusFilter);

      const [tracesRes, statsRes, skillsRes] = await Promise.all([
        fetch(`/api/v1/admin/traces?${params.toString()}`),
        fetch('/api/v1/admin/stats'),
        fetch('/api/v1/skills'),
      ]);

      if (tracesRes.ok) {
        const data = await tracesRes.json();
        setTraces(data.items || []);
      }
      if (statsRes.ok) {
        const sdata = await statsRes.json();
        setStats(sdata);
      }
      if (skillsRes.ok) {
        const skData = await skillsRes.json();
        if (skData.skills && Array.isArray(skData.skills) && skData.skills.length > 0) {
          setSkills(skData.skills);
        }
      }
    } catch (err) {
      console.warn('Failed to fetch admin traces:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [search, toolFilter, statusFilter]);

  useEffect(() => {
    fetchTraces();
  }, [fetchTraces]);

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

  // Selected trace for Data Flow highlighting
  const activeTrace = useMemo(() => {
    if (!expandedTraceId) return traces[0] || null;
    return traces.find((t) => t.id === expandedTraceId) || traces[0] || null;
  }, [expandedTraceId, traces]);

  // Simulator resolution logic replicating registry.py
  const simulatedDetection = useMemo(() => {
    const raw = simulatorInput.trim();
    const lowered = raw.toLowerCase();
    if (!lowered) return null;

    const tokens = lowered.split(/\s+/);
    const firstToken = tokens[0] || '';

    // 1. Slash command
    for (const s of skills) {
      const slashNormal = `/${s.name.toLowerCase()}`;
      const slashDash = `/${s.name.toLowerCase().replace('_', '-')}`;
      const slashAliases = [slashNormal, slashDash];
      if (s.name === 'budgeting') slashAliases.push('/budget');
      if (s.name === 'time_management') slashAliases.push('/time', '/schedule');

      for (const alias of slashAliases) {
        if (
          firstToken === alias ||
          firstToken.startsWith(`${alias}:`) ||
          firstToken.startsWith(`${alias}/`) ||
          new RegExp(`(?:^|\\s)${alias.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:\\s|$|:)`).test(lowered)
        ) {
          return { skill: s, trigger: 'slash_command', aliasUsed: alias };
        }
      }
    }

    // 2. Context keywords
    for (const s of skills) {
      for (const kw of s.keywords) {
        const regex = new RegExp(`\\b${kw}\\b`, 'i');
        if (regex.test(lowered)) {
          return { skill: s, trigger: 'context', keywordMatched: kw };
        }
      }
    }

    return null;
  }, [simulatorInput, skills]);

  return (
    <div className="flex flex-col h-full bg-bg overflow-hidden animate-fade-in">
      {/* ─── Header ─────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-3.5 border-b border-border bg-bg-secondary/60 shrink-0">
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
                Architecture & Tool Tracing
              </span>
            </div>
            <p className="text-xs text-fg-muted mt-0.5">
              Visual data flow pipeline, decision skills registry & prompt execution traces
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Tab selector */}
          <div className="flex items-center bg-surface border border-border rounded-lg p-0.5 mr-2">
            <button
              onClick={() => setActiveTab('diagram')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === 'diagram'
                  ? 'bg-accent text-accent-fg shadow-xs font-semibold'
                  : 'text-fg-muted hover:text-fg'
              }`}
            >
              <GitBranch size={13} />
              <span>Data Flow & Skills</span>
            </button>
            <button
              onClick={() => setActiveTab('traces')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === 'traces'
                  ? 'bg-accent text-accent-fg shadow-xs font-semibold'
                  : 'text-fg-muted hover:text-fg'
              }`}
            >
              <Terminal size={13} />
              <span>Execution Traces ({traces.length})</span>
            </button>
          </div>

          {/* Live indicator toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
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
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-surface hover:bg-surface-hover text-fg text-xs font-medium transition-colors disabled:opacity-50"
            title="Refresh now"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin text-accent' : ''} />
            <span>Refresh</span>
          </button>

          {/* Clear logs button */}
          <button
            onClick={handleClearLogs}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-surface hover:bg-error/10 hover:text-error hover:border-error/30 text-fg-muted text-xs font-medium transition-colors"
            title="Clear all logs"
          >
            <Trash2 size={13} />
            <span>Clear</span>
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
              Skills in Registry
            </span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-purple-600 dark:text-purple-400">
                {skills.length}
              </span>
              <span className="text-[11px] text-fg-muted">active</span>
            </div>
          </div>
        </section>

        {activeTab === 'diagram' ? (
          /* ─── DATA FLOW ARCHITECTURE & SKILL REGISTRY VIEW ─────── */
          <div className="space-y-6">
            {/* Active Trace Inspector Selector */}
            <div className="p-4 rounded-2xl bg-surface border border-border shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Layers size={16} className="text-accent" />
                <div>
                  <h2 className="text-xs font-bold text-fg">Active Trace Inspector</h2>
                  <p className="text-[11px] text-fg-muted">
                    {activeTrace
                      ? `Inspecting: "${activeTrace.prompt.slice(0, 70)}${activeTrace.prompt.length > 70 ? '…' : ''}"`
                      : 'No trace selected. Showing default architecture.'}
                  </p>
                </div>
              </div>

              {traces.length > 0 && (
                <div className="flex items-center gap-2 w-full md:w-auto">
                  <span className="text-[11px] text-fg-muted font-medium whitespace-nowrap">Select Prompt:</span>
                  <select
                    value={activeTrace?.id || ''}
                    onChange={(e) => setExpandedTraceId(e.target.value)}
                    className="bg-bg-secondary rounded-lg px-2.5 py-1.5 text-xs text-fg border border-border focus:border-accent focus:outline-none max-w-xs truncate"
                  >
                    {traces.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.skill ? `[${t.skill}] ` : ''}"{t.prompt.slice(0, 40)}" ({formatDuration(t.total_duration_ms)})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* ─── END-TO-END DATA FLOW DIAGRAM ───────────────────── */}
            <div className="p-6 rounded-2xl bg-surface border border-border shadow-xs overflow-hidden">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
                <div>
                  <div className="flex items-center gap-2">
                    <GitBranch size={16} className="text-accent" />
                    <h2 className="text-sm font-bold text-fg">
                      End-to-End Prompt Processing & Data Flow Pipeline
                    </h2>
                  </div>
                  <p className="text-xs text-fg-muted mt-0.5">
                    Step-by-step traversal from user text intake, skill selection (/&lt;skill&gt; vs context), to structured table/diagram response
                  </p>
                </div>
                {activeTrace?.skill && (
                  <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-accent-muted border border-accent/20 text-accent text-xs font-medium">
                    <Sparkles size={12} />
                    <span>Skill Activated: <strong>/{activeTrace.skill.replace('_', '-')}</strong></span>
                    {activeTrace.skill_trigger && (
                      <span className="text-[10px] text-fg-muted font-mono">({activeTrace.skill_trigger})</span>
                    )}
                  </div>
                )}
              </div>

              {/* Connected Visual Pipeline Flowchart */}
              <div className="grid grid-cols-1 lg:grid-cols-7 gap-3 relative py-2">
                {/* Step 1: User Text Input */}
                <div className="p-4 rounded-xl border border-border bg-bg-secondary/60 flex flex-col justify-between transition-all hover:border-accent/40">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-accent/10 text-accent uppercase tracking-wider">
                        Step 1
                      </span>
                      <Terminal size={14} className="text-accent" />
                    </div>
                    <h3 className="text-xs font-bold text-fg mb-1">User Text Input</h3>
                    <p className="text-[11px] text-fg-muted leading-relaxed">
                      Accepts natural query or slash command (e.g. <code className="text-accent font-mono">/career</code>).
                    </p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-border/60 text-[10px] text-fg-muted font-mono">
                    Flags: <span className="text-fg">remember</span>, <span className="text-fg">browse</span>
                  </div>
                </div>

                {/* Arrow */}
                <div className="hidden lg:flex items-center justify-center text-fg-muted">
                  <ArrowRight size={18} className="text-accent/60" />
                </div>

                {/* Step 2: Skill & Intent Classifier */}
                <div className={`p-4 rounded-xl border transition-all ${
                  activeTrace?.skill
                    ? 'border-purple-500/40 bg-purple-500/5 ring-1 ring-purple-500/20'
                    : 'border-border bg-bg-secondary/60'
                } flex flex-col justify-between`}>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-purple-500/10 text-purple-600 dark:text-purple-400 uppercase tracking-wider">
                        Step 2
                      </span>
                      <Sliders size={14} className="text-purple-500" />
                    </div>
                    <h3 className="text-xs font-bold text-fg mb-1">classify node</h3>
                    <p className="text-[11px] text-fg-muted leading-relaxed">
                      Evaluates <strong>registry.py</strong>:
                    </p>
                    <div className="mt-1.5 space-y-1">
                      <div className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface border border-border text-fg-secondary">
                        ⚡ Slash: <span className="text-accent">/&lt;skill&gt;</span>
                      </div>
                      <div className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface border border-border text-fg-secondary">
                        🎯 Context keywords
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 pt-2 border-t border-border/60 text-[10px] text-fg-muted font-mono">
                    Output: <span className="text-purple-600 dark:text-purple-400 font-semibold">{activeTrace?.skill || 'skill'}, {activeTrace?.intent || 'intent'}</span>
                  </div>
                </div>

                {/* Arrow */}
                <div className="hidden lg:flex items-center justify-center text-fg-muted">
                  <ArrowRight size={18} className="text-accent/60" />
                </div>

                {/* Step 3: Optional Integrations */}
                <div className="p-4 rounded-xl border border-border bg-bg-secondary/60 flex flex-col justify-between transition-all hover:border-accent/40">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-amber-500/10 text-amber-600 uppercase tracking-wider">
                        Step 3
                      </span>
                      <div className="flex items-center gap-1">
                        <Database size={12} className="text-amber-500" />
                        <Globe size={12} className="text-blue-500" />
                      </div>
                    </div>
                    <h3 className="text-xs font-bold text-fg mb-1">Optional Integrations</h3>
                    <div className="text-[11px] text-fg-muted space-y-1.5 mt-1">
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                        <span>Mem0 Memory Recall</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                        <span>Browser Use Research</span>
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 pt-2 border-t border-border/60 text-[10px] text-fg-muted font-mono">
                    Conditional on user consent
                  </div>
                </div>

                {/* Arrow */}
                <div className="hidden lg:flex items-center justify-center text-fg-muted">
                  <ArrowRight size={18} className="text-accent/60" />
                </div>

                {/* Step 4: Supervisor & LLM */}
                <div className="p-4 rounded-xl border border-emerald-500/40 bg-emerald-500/5 ring-1 ring-emerald-500/20 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                        Step 4
                      </span>
                      <Cpu size={14} className="text-emerald-500" />
                    </div>
                    <h3 className="text-xs font-bold text-fg mb-1">agent Supervisor</h3>
                    <p className="text-[11px] text-fg-muted leading-relaxed">
                      Injects skill instructions, history & <strong>prefers tables/diagrams</strong> for answers.
                    </p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-border/60 text-[10px] text-fg-muted font-mono flex items-center justify-between">
                    <span>Tool Loop</span>
                    <TableIcon size={12} className="text-accent" />
                  </div>
                </div>
              </div>

              {/* Response formatting footer */}
              <div className="mt-4 p-3 rounded-xl bg-bg-secondary/40 border border-border/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-success" />
                  <span className="font-semibold text-fg">Step 5: Client Response Delivery</span>
                  <span className="text-fg-muted">— Renders Markdown tables, Mermaid sequence/flowcharts, or structured text.</span>
                </div>
                <div className="flex items-center gap-2 text-[11px] font-mono text-fg-muted">
                  <span>Trace Recorded</span>
                  <span>•</span>
                  <span>Auto-saved to DB</span>
                </div>
              </div>
            </div>

            {/* ─── SKILL REGISTRY MATRIX (registry.py) ────────────── */}
            <div className="p-6 rounded-2xl bg-surface border border-border shadow-xs">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
                <div>
                  <div className="flex items-center gap-2">
                    <Sparkles size={16} className="text-accent" />
                    <h2 className="text-sm font-bold text-fg">
                      Skills Registered in <code className="text-xs font-mono text-accent">app/skills/registry.py</code>
                    </h2>
                  </div>
                  <p className="text-xs text-fg-muted mt-0.5">
                    Click any skill to inspect its injected system prompt instructions, trigger syntax, and associated tools
                  </p>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-mono bg-bg-secondary border border-border text-fg-muted">
                  {skills.length} Loaded
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {skills.map((skill) => {
                  const isSelected = selectedSkillDetails?.name === skill.name;
                  const isActiveInCurrentTrace = activeTrace?.skill === skill.name;

                  return (
                    <div
                      key={skill.name}
                      onClick={() => setSelectedSkillDetails(skill)}
                      className={`p-4 rounded-xl border cursor-pointer transition-all ${
                        isSelected
                          ? 'border-accent bg-accent/5 ring-1 ring-accent/30 shadow-xs'
                          : 'border-border bg-bg-secondary/40 hover:border-accent/40 hover:bg-surface'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Command size={13} className="text-accent" />
                          <span className="font-mono text-xs font-bold text-fg">
                            {skill.slash_command}
                          </span>
                        </div>
                        {isActiveInCurrentTrace && (
                          <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-success/10 text-success border border-success/20">
                            Active in Trace
                          </span>
                        )}
                      </div>

                      <h4 className="text-xs font-semibold text-fg mb-1">{skill.name}</h4>
                      <p className="text-[11px] text-fg-muted line-clamp-2 mb-3">
                        {skill.description}
                      </p>

                      <div className="space-y-1.5 pt-2 border-t border-border/60">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="text-fg-muted">Trigger Keywords:</span>
                          <span className="font-mono text-fg-secondary truncate max-w-35" title={skill.keywords.join(', ')}>
                            {skill.keywords.slice(0, 3).join(', ')}...
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="text-fg-muted">Tools:</span>
                          <span className="font-mono text-accent">
                            {skill.tools.length > 0 ? skill.tools.join(', ') : 'none'}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Selected Skill Detail Inspector Drawer */}
              {selectedSkillDetails && (
                <div className="mt-4 p-4 rounded-xl border border-accent/30 bg-accent/5 animate-fade-in text-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-fg flex items-center gap-1.5">
                      <Zap size={14} className="text-accent" />
                      Injected Skill Instructions for: <code className="text-accent font-mono">{selectedSkillDetails.slash_command}</code>
                    </span>
                    <button
                      onClick={() => {
                        setSimulatorInput(`${selectedSkillDetails.slash_command} Analyze my situation`);
                      }}
                      className="flex items-center gap-1 text-[11px] text-accent hover:underline font-medium"
                    >
                      <Play size={10} />
                      <span>Test in Simulator</span>
                    </button>
                  </div>
                  <div className="p-3 rounded-lg bg-surface border border-border font-mono text-[11px] text-fg leading-relaxed">
                    "{selectedSkillDetails.instructions}"
                  </div>
                </div>
              )}
            </div>

            {/* ─── INTERACTIVE SKILL DETECTION SIMULATOR ───────────── */}
            <div className="p-6 rounded-2xl bg-surface border border-border shadow-xs">
              <div className="flex items-center gap-2 mb-2">
                <Play size={16} className="text-accent" />
                <h2 className="text-sm font-bold text-fg">Live Skill & Slash Command Simulator</h2>
              </div>
              <p className="text-xs text-fg-muted mb-4">
                Test how Life Sandbox resolves skills in real-time based on slash syntax (<code className="text-accent">/&lt;skill&gt;</code>) vs context keywords from prompt text
              </p>

              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  value={simulatorInput}
                  onChange={(e) => setSimulatorInput(e.target.value)}
                  placeholder="Type a message or use /<skill> (e.g. /career, /budgeting, or 'I need to buy a laptop')..."
                  className="flex-1 bg-bg-secondary rounded-xl px-4 py-2 text-xs text-fg placeholder:text-fg-muted border border-border focus:border-accent focus:outline-none font-mono"
                />
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setSimulatorInput('/career Should I accept the senior developer offer?')}
                    className="px-2.5 py-1 rounded-lg border border-border bg-bg-secondary hover:bg-surface text-[11px] font-mono text-fg-secondary"
                  >
                    /career
                  </button>
                  <button
                    onClick={() => setSimulatorInput('Help me compare a laptop')}
                    className="px-2.5 py-1 rounded-lg border border-border bg-bg-secondary hover:bg-surface text-[11px] font-mono text-fg-secondary"
                  >
                    Context: laptop
                  </button>
                  <button
                    onClick={() => setSimulatorInput('/travel Trip to Japan in October')}
                    className="px-2.5 py-1 rounded-lg border border-border bg-bg-secondary hover:bg-surface text-[11px] font-mono text-fg-secondary"
                  >
                    /travel
                  </button>
                </div>
              </div>

              {/* Simulator Result Card */}
              <div className="mt-4 p-4 rounded-xl border border-border bg-bg-secondary/50">
                {simulatedDetection ? (
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-accent-muted flex items-center justify-center text-accent">
                        <CheckCircle2 size={16} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-fg">Skill Triggered:</span>
                          <span className="px-2 py-0.5 rounded-full bg-accent-muted text-accent font-mono font-semibold text-xs border border-accent/20">
                            /{simulatedDetection.skill.name.replace('_', '-')}
                          </span>
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                            simulatedDetection.trigger === 'slash_command'
                              ? 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20'
                              : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                          }`}>
                            {simulatedDetection.trigger === 'slash_command'
                              ? `⚡ Explicit Command (${simulatedDetection.aliasUsed})`
                              : `🎯 Keyword Match (${simulatedDetection.keywordMatched})`}
                          </span>
                        </div>
                        <p className="text-[11px] text-fg-muted mt-0.5">
                          {simulatedDetection.skill.description}
                        </p>
                      </div>
                    </div>

                    <div className="text-right sm:text-right font-mono text-[11px] text-fg-muted">
                      Decision Tools: <span className="text-accent">{simulatedDetection.skill.tools.join(', ') || 'None'}</span>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-xs text-fg-muted italic">
                    <HelpCircle size={14} />
                    <span>No specific skill triggered. Standard general conversation workflow will be used.</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* ─── EXECUTION TRACES LIST VIEW ───────────────────────── */
          <div className="space-y-4">
            {/* Search & Filters Bar */}
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

            {/* Traces List */}
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
                              {trace.skill && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                                  Skill: /{trace.skill.replace('_', '-')} ({trace.skill_trigger || 'context'})
                                </span>
                              )}
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
        )}
      </div>
    </div>
  );
}
