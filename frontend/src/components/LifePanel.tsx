/* ─── LifePanel: Memory & Follow-Through Dashboard ─── */

import {
  startTransition,
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react';
import {
  Archive,
  Bell,
  BrainCircuit,
  CalendarDays,
  Check,
  ChevronDown,
  FolderKanban,
  Link as LinkIcon,
  ListTodo,
  NotebookTabs,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react';
import type { PluginCapability, PluginExecution } from '../types';

type Item = Record<string, any>;
type Section = 'memories' | 'projects' | 'tasks' | 'reminders' | 'approvals' | 'connections';

type LifePanelProps = {
  onClose: () => void;
  onPolicyChange?: () => void;
};

async function request<T = any>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(body?.detail?.message ?? 'Could not complete the request.');
  }
  return body as T;
}

function localDateTime(value: string | null | undefined) {
  if (!value) return '';
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function timestamp(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : 'Not set';
}

function PolicySwitch({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex min-h-10 items-center justify-between gap-4 border-b border-border py-2 text-xs text-fg">
      <span>{label}</span>
      <span className="relative inline-flex h-5 w-9 shrink-0 cursor-pointer">
        <input
          type="checkbox"
          role="switch"
          aria-label={label}
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
          className="peer sr-only"
        />
        <span
          aria-hidden="true"
          className="absolute inset-0 rounded-full bg-bg-secondary border border-border transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-3.5 after:w-3.5 after:rounded-full after:bg-fg-muted after:shadow-xs after:transition-transform peer-checked:bg-accent peer-checked:border-accent peer-checked:after:translate-x-4 peer-checked:after:bg-accent-fg peer-focus-visible:ring-2 peer-focus-visible:ring-accent peer-disabled:opacity-50"
        />
      </span>
    </label>
  );
}

type ComboOption = { value: string; label: string };

function ComboBox({
  name,
  label,
  options,
  defaultValue = '',
  value,
  onChange,
  disabled = false,
  className = '',
}: {
  name?: string;
  label: string;
  options: ComboOption[];
  defaultValue?: string;
  value?: string;
  onChange?: (value: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(value ?? defaultValue);
  const root = useRef<HTMLDivElement>(null);
  const current = options.find((option) => option.value === selected) ?? options[0];

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  function choose(next: string) {
    setSelected(next);
    onChange?.(next);
    setOpen(false);
  }

  return (
    <div className={`grid gap-1 min-w-0 ${className}`} ref={root}>
      <span className="text-[11px] font-semibold text-fg-muted truncate">{label}</span>
      {name && <input type="hidden" name={name} value={selected} />}
      <div className="relative">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 text-left rounded-xl border border-border bg-bg px-3 py-2 text-xs text-fg hover:border-accent/40 focus:border-accent focus:outline-none transition-colors"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label={label}
          disabled={disabled}
          onClick={() => setOpen((currentOpen) => !currentOpen)}
        >
          <span className={current ? 'truncate text-fg font-medium' : 'text-fg-muted'}>
            {current?.label ?? 'Choose an option'}
          </span>
          <ChevronDown
            aria-hidden="true"
            size={14}
            className={`shrink-0 text-fg-muted transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
          />
        </button>
        {open && (
          <div
            className="absolute z-30 top-[calc(100%+4px)] left-0 w-full min-w-[14rem] max-h-56 overflow-y-auto rounded-xl border border-border bg-surface p-1 shadow-lg text-xs animate-fade-in"
            role="listbox"
            aria-label={label}
          >
            {options.map((option) => (
              <button
                type="button"
                role="option"
                aria-selected={option.value === selected}
                key={option.value}
                className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-xs text-left transition-colors ${
                  option.value === selected
                    ? 'bg-accent-muted text-accent font-semibold'
                    : 'text-fg hover:bg-surface-hover'
                }`}
                onClick={() => choose(option.value)}
              >
                <span>{option.label}</span>
                {option.value === selected && <Check size={13} className="text-accent" />}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function DateTimeField({
  name,
  label,
  defaultValue = '',
  required = false,
}: {
  name: string;
  label: string;
  defaultValue?: string;
  required?: boolean;
}) {
  const initial = defaultValue || '';
  const [value, setValue] = useState(initial);
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => {
    const source = initial ? new Date(initial) : new Date();
    return new Date(source.getFullYear(), source.getMonth(), 1);
  });
  const [today] = useState(() => new Date());
  const root = useRef<HTMLDivElement>(null);
  const datePart = value.split('T')[0] || '';
  const timePart = value.split('T')[1] || '09:00';
  const year = month.getFullYear();
  const monthIndex = month.getMonth();
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
  const firstDay = new Date(year, monthIndex, 1).getDay();
  const monthName = month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  const dayCells = Array.from({ length: firstDay + daysInMonth }, (_, index) => {
    if (index < firstDay) return null;
    return index - firstDay + 1;
  });
  const [clockMode, setClockMode] = useState<'hour' | 'minute'>('hour');
  const hour24 = Number(timePart.slice(0, 2)) || 9;
  const minute = Number(timePart.slice(3, 5)) || 0;
  const period = hour24 >= 12 ? 'PM' : 'AM';
  const displayHour = hour24 % 12 || 12;
  const clockValues = Array.from({ length: 12 }, (_, index) => index + 1);
  const minuteClockRef = useRef<HTMLDivElement>(null);
  const minuteAngle = minute * 6;

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  function updateDate(day: number) {
    const nextDate = `${year}-${String(monthIndex + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    setValue(`${nextDate}T${timePart}`);
  }

  function updateHour(nextHour: number) {
    const nextHour24 = period === 'PM' ? (nextHour % 12) + 12 : nextHour % 12;
    setValue(
      `${datePart || today.toISOString().slice(0, 10)}T${String(nextHour24).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
    );
    setClockMode('minute');
  }

  function updateMinute(nextMinute: number) {
    setValue(
      `${datePart || today.toISOString().slice(0, 10)}T${String(hour24).padStart(2, '0')}:${String(nextMinute).padStart(2, '0')}`
    );
  }

  function updatePeriod(nextPeriod: 'AM' | 'PM') {
    const nextHour = nextPeriod === 'PM' ? (displayHour % 12) + 12 : displayHour % 12;
    setValue(
      `${datePart || today.toISOString().slice(0, 10)}T${String(nextHour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
    );
  }

  function selectFromDial(clientX: number, clientY: number) {
    if (!minuteClockRef.current) return;
    const bounds = minuteClockRef.current.getBoundingClientRect();
    const x = clientX - (bounds.left + bounds.width / 2);
    const y = clientY - (bounds.top + bounds.height / 2);
    const angle = (Math.atan2(x, -y) + Math.PI * 2) % (Math.PI * 2);
    if (clockMode === 'hour') {
      const nextHour = Math.round((angle / (Math.PI * 2)) * 12) % 12 || 12;
      updateHour(nextHour);
    } else {
      updateMinute(Math.round((angle / (Math.PI * 2)) * 60) % 60);
    }
  }

  function handleDialPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    selectFromDial(event.clientX, event.clientY);
  }

  function handleDialPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.buttons) selectFromDial(event.clientX, event.clientY);
  }

  return (
    <div className="grid gap-1 min-w-0 relative" ref={root}>
      <span className="text-[11px] font-semibold text-fg-muted truncate">{label}</span>
      <input type="hidden" name={name} value={value} required={required} />
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 text-left rounded-xl border border-border bg-bg px-3 py-2 text-xs text-fg hover:border-accent/40 focus:border-accent focus:outline-none transition-colors"
        onClick={() => setOpen((currentOpen) => !currentOpen)}
        aria-expanded={open}
        aria-label={label}
      >
        <span className={value ? 'text-fg font-medium' : 'text-fg-muted'}>
          {value ? `${datePart} · ${timePart}` : 'Choose date & time'}
        </span>
        <CalendarDays size={14} className="shrink-0 text-fg-muted" />
      </button>
      {open && (
        <div className="absolute z-30 top-[calc(100%+4px)] left-0 w-min-[18rem] max-w-[calc(100vw-2rem)] rounded-2xl border border-border bg-surface p-4 shadow-xl text-xs animate-fade-in">
          <div className="flex items-center justify-between gap-3 mb-2">
            <button
              type="button"
              className="w-7 h-7 rounded-lg border border-border flex items-center justify-center text-fg-muted hover:text-fg hover:bg-surface-hover"
              aria-label="Previous month"
              onClick={() => setMonth(new Date(year, monthIndex - 1, 1))}
            >
              ‹
            </button>
            <strong className="text-xs font-semibold text-fg">{monthName}</strong>
            <button
              type="button"
              className="w-7 h-7 rounded-lg border border-border flex items-center justify-center text-fg-muted hover:text-fg hover:bg-surface-hover"
              aria-label="Next month"
              onClick={() => setMonth(new Date(year, monthIndex + 1, 1))}
            >
              ›
            </button>
          </div>
          <div className="grid grid-cols-7 gap-1 text-center text-[10px] font-semibold text-fg-muted">
            {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, index) => (
              <span key={`${day}-${index}`}>{day}</span>
            ))}
          </div>
          <div className="mt-1 grid grid-cols-7 gap-1">
            {dayCells.map((day, index) =>
              day === null ? (
                <span key={`blank-${index}`} />
              ) : (
                <button
                  type="button"
                  key={day}
                  className={`w-7 h-7 rounded-lg text-xs font-medium transition-colors ${
                    datePart ===
                    `${year}-${String(monthIndex + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
                      ? 'bg-accent text-accent-fg font-bold shadow-2xs'
                      : 'text-fg hover:bg-surface-hover'
                  }`}
                  onClick={() => updateDate(day)}
                >
                  {day}
                </button>
              )
            )}
          </div>
          <div className="mt-3 border-t border-border pt-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-[11px] font-semibold text-fg-muted">Time</span>
              <span className="text-xs font-mono font-bold text-fg">
                {displayHour}:{String(minute).padStart(2, '0')} <span className="text-accent">{period}</span>
              </span>
            </div>
            <div className="mb-3 flex items-center justify-between gap-2 rounded-xl bg-bg-secondary p-1">
              <div className="flex gap-1">
                {(['hour', 'minute'] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={`px-2 py-1 rounded-lg text-[11px] font-medium transition-colors ${
                      clockMode === mode ? 'bg-accent text-accent-fg shadow-xs font-semibold' : 'text-fg-muted hover:text-fg'
                    }`}
                    onClick={() => setClockMode(mode)}
                  >
                    {mode === 'hour' ? 'Hour' : 'Minute'}
                  </button>
                ))}
              </div>
              <div className="flex gap-1">
                {(['AM', 'PM'] as const).map((nextPeriod) => (
                  <button
                    key={nextPeriod}
                    type="button"
                    className={`px-2 py-1 rounded-lg text-[11px] font-medium transition-colors ${
                      period === nextPeriod ? 'bg-accent text-accent-fg shadow-xs font-semibold' : 'text-fg-muted hover:text-fg'
                    }`}
                    onClick={() => updatePeriod(nextPeriod)}
                  >
                    {nextPeriod}
                  </button>
                ))}
              </div>
            </div>
            <div
              ref={minuteClockRef}
              className={`life-clock ${clockMode === 'minute' ? 'life-clock-minute' : 'life-clock-hour'}`}
              role="slider"
              tabIndex={0}
              aria-label={`Choose ${clockMode}`}
              aria-valuemin={clockMode === 'hour' ? 1 : 0}
              aria-valuemax={clockMode === 'hour' ? 12 : 59}
              aria-valuenow={clockMode === 'hour' ? displayHour : minute}
              onPointerDown={clockMode === 'minute' ? handleDialPointerDown : undefined}
              onPointerMove={clockMode === 'minute' ? handleDialPointerMove : undefined}
            >
              <span className="life-clock-center" />
              <span
                className="life-clock-hand"
                style={{ '--clock-angle': `${clockMode === 'hour' ? (displayHour % 12) * 30 : minuteAngle}deg` } as CSSProperties}
              />
              {clockMode === 'hour'
                ? clockValues.map((clockValue) => (
                    <button
                      key={clockValue}
                      type="button"
                      className={`life-clock-number ${clockValue === displayHour ? 'is-selected' : ''}`}
                      style={{ '--clock-angle': `${(clockValue % 12) * 30}deg` } as CSSProperties}
                      onClick={() => updateHour(clockValue)}
                    >
                      {clockValue}
                    </button>
                  ))
                : Array.from({ length: 12 }, (_, index) => index * 5).map((minuteValue, index) => (
                    <span
                      key={minuteValue}
                      className={`life-clock-number ${minuteValue === minute ? 'is-selected' : ''}`}
                      style={{ '--clock-angle': `${index * 30}deg` } as CSSProperties}
                    >
                      {String(minuteValue).padStart(2, '0')}
                    </span>
                  ))}
            </div>
            <p className="mt-2 text-center text-[10px] text-fg-muted">Click or drag the dial to set the {clockMode}.</p>
          </div>
          <button
            type="button"
            className="mt-3 w-full rounded-xl bg-accent px-3 py-2 text-xs font-semibold text-accent-fg hover:bg-accent-hover transition-colors shadow-2xs"
            onClick={() => setOpen(false)}
          >
            Apply
          </button>
        </div>
      )}
    </div>
  );
}

function SectionHeading({
  icon: Icon,
  title,
  count,
  subtitle,
}: {
  icon: typeof BrainCircuit;
  title: string;
  count?: number;
  subtitle?: string;
}) {
  return (
    <div className="flex items-center gap-3 pb-4 mb-5 border-b border-border">
      <div className="w-8 h-8 rounded-lg bg-accent-muted flex items-center justify-center text-accent shrink-0">
        <Icon size={16} />
      </div>
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold text-fg">{title}</h2>
          {count !== undefined && (
            <span className="rounded-full bg-bg-secondary border border-border px-2 py-0.5 font-mono text-[11px] font-semibold text-fg-muted">
              {count}
            </span>
          )}
        </div>
        {subtitle && <p className="text-xs text-fg-muted mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

export default function LifePanel({ onClose, onPolicyChange }: LifePanelProps) {
  const [section, setSection] = useState<Section>('memories');
  const [memories, setMemories] = useState<Item[]>([]);
  const [candidates, setCandidates] = useState<Item[]>([]);
  const [tasks, setTasks] = useState<Item[]>([]);
  const [reminders, setReminders] = useState<Item[]>([]);
  const [jobs, setJobs] = useState<Item[]>([]);
  const [approvals, setApprovals] = useState<Item[]>([]);
  const [projects, setProjects] = useState<Item[]>([]);
  const [notifications, setNotifications] = useState<Item[]>([]);
  const [policy, setPolicy] = useState<Item | null>(null);
  const [connections, setConnections] = useState<Item[]>([]);
  const [connectionConfigured, setConnectionConfigured] = useState(false);
  const [connectionCapabilities, setConnectionCapabilities] = useState<string[]>([
    'calendar.read',
    'gmail.read',
    'drive.read',
  ]);
  const [pluginCapabilities, setPluginCapabilities] = useState<PluginCapability[]>([]);
  const [pluginExecutions, setPluginExecutions] = useState<PluginExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [memoryCategoryFilter, setMemoryCategoryFilter] = useState('all');
  const [taskStatusFilter, setTaskStatusFilter] = useState('all');
  const [editingMemory, setEditingMemory] = useState<string | null>(null);
  const [editingProject, setEditingProject] = useState<string | null>(null);
  const [editingTask, setEditingTask] = useState<string | null>(null);
  const [editingReminder, setEditingReminder] = useState<string | null>(null);
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const refresh = useCallback(async () => {
    try {
      const [m, c, t, r, a, p, n, mp, j, ic, pc, pe] = await Promise.all([
        request('memories'),
        request('memory-candidates'),
        request('tasks'),
        request('reminder-schedules'),
        request('approvals'),
        request('projects'),
        request('notifications'),
        request('memory-policy'),
        request('jobs'),
        request('integrations'),
        request<{ tools: PluginCapability[] }>('plugins'),
        request<{ executions: PluginExecution[] }>('plugins/executions?limit=12'),
      ]);
      startTransition(() => {
        setMemories(m.items || []);
        setCandidates(c.items || []);
        setTasks(t.items || []);
        setReminders(r.items || []);
        setApprovals(a.items || []);
        setProjects(p.items || []);
        setNotifications(n.items || []);
        setPolicy(mp);
        setJobs(j.items || []);
        setConnections(ic.connections ?? []);
        setConnectionConfigured(ic.configured === true);
        setPluginCapabilities(pc.tools ?? []);
        setPluginExecutions(pe.executions ?? []);
        setError('');
        setLoading(false);
      });
    } catch (cause) {
      startTransition(() => {
        setError(cause instanceof Error ? cause.message : 'Unable to load your data.');
        setLoading(false);
      });
    }
  }, []);

  const connectGoogle = async () => {
    setBusy(true);
    setError('');
    try {
      const result = await request<{ authorization_url: string }>('integrations/google/authorize', {
        method: 'POST',
        body: JSON.stringify({ capabilities: connectionCapabilities }),
      });
      window.location.assign(result.authorization_url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not start Google authorization.');
      setBusy(false);
    }
  };

  const disconnectGoogle = async (id: string) => {
    setBusy(true);
    setError('');
    try {
      await request(`integrations/${id}`, { method: 'DELETE' });
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not disconnect Google.');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => () => {
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current);
  }, []);

  function showNotice(message: string) {
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current);
    setNotice(message);
    noticeTimer.current = window.setTimeout(() => {
      setNotice('');
      noticeTimer.current = null;
    }, 2500);
  }

  async function act(path: string, init?: RequestInit) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await request(path, init);
      await refresh();
      if (path.includes('memory-policy')) {
        onPolicyChange?.();
      }
      showNotice('Changes saved.');
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Request failed.');
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function saveMemory(event: FormEvent<HTMLFormElement>, memoryId?: string) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const projectId = String(data.get('project_id') || '') || null;
    const payload = {
      content: String(data.get('content') || '').trim(),
      category: String(data.get('category') || 'preference'),
      consent: true,
      source_conversation_id: memoryId
        ? memories.find((memory) => memory.id === memoryId)?.source_conversation_id ?? null
        : null,
    };
    if (!payload.content) return;
    setBusy(true);
    setError('');
    try {
      const saved = await request<Item>(memoryId ? `memories/${memoryId}` : 'memories', {
        method: memoryId ? 'PATCH' : 'POST',
        body: JSON.stringify(payload),
      });
      if (projectId) {
        await request(`memories/${saved.id}/project`, {
          method: 'PATCH',
          body: JSON.stringify({ project_id: projectId }),
        });
      }
      await refresh();
      setEditingMemory(null);
      showNotice('Memory saved.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Memory could not be saved.');
    } finally {
      setBusy(false);
    }
  }

  async function saveProject(event: FormEvent<HTMLFormElement>, projectId?: string) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const target = String(data.get('target_at') || '');
    const payload = {
      title: String(data.get('title') || '').trim(),
      description: String(data.get('description') || ''),
      status: String(data.get('status') || 'active'),
      priority: String(data.get('priority') || 'normal'),
      progress: String(data.get('progress') || ''),
      blocker: String(data.get('blocker') || ''),
      next_action: String(data.get('next_action') || ''),
      target_at: target ? new Date(target).toISOString() : null,
    };
    if (!payload.title) return;
    const saved = await act(projectId ? `projects/${projectId}` : 'projects', {
      method: projectId ? 'PATCH' : 'POST',
      body: JSON.stringify(payload),
    });
    if (saved) setEditingProject(null);
  }

  async function saveTask(event: FormEvent<HTMLFormElement>, taskId?: string) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const due = String(data.get('due_at') || '');
    const payload = {
      title: String(data.get('title') || '').trim(),
      description: String(data.get('description') || ''),
      project_id: String(data.get('project_id') || '') || null,
      priority: String(data.get('priority') || 'normal'),
      due_at: due ? new Date(due).toISOString() : null,
      timezone: String(data.get('timezone') || timezone),
    };
    if (!payload.title) return;
    const saved = await act(taskId ? `tasks/${taskId}` : 'tasks', {
      method: taskId ? 'PATCH' : 'POST',
      body: JSON.stringify(payload),
    });
    if (saved) setEditingTask(null);
  }

  async function saveReminder(event: FormEvent<HTMLFormElement>, reminderId?: string) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const time = String(data.get('scheduled_at') || '');
    const payload = {
      text: String(data.get('text') || '').trim(),
      scheduled_at: time ? new Date(time).toISOString() : '',
      timezone: String(data.get('timezone') || timezone),
      task_id: String(data.get('task_id') || '') || null,
      recurrence: String(data.get('recurrence') || 'none'),
      channel: 'in_app',
    };
    if (!payload.text || !time) return;
    const path = reminderId
      ? `reminders/${reminderId}`
      : payload.recurrence === 'none'
      ? 'reminders'
      : 'reminders/recurring';
    const saved = await act(path, {
      method: reminderId ? 'PATCH' : 'POST',
      body: JSON.stringify(payload),
    });
    if (saved) setEditingReminder(null);
  }

  async function resolveCandidate(candidate: Item, decision: 'approve' | 'reject') {
    if (decision === 'approve' && !window.confirm(`Save this ${candidate.category} memory?\n\n${candidate.content}`)) return;
    await act(`memory-candidates/${candidate.id}/${decision}`, { method: 'POST' });
  }

  async function resolveApproval(approval: Item, decision: 'approve' | 'reject') {
    const executable = ['task.create', 'reminder.create'].includes(approval.action);
    const gmailSend = approval.action === 'gmail.send_draft';
    if (decision === 'approve' && !executable && !gmailSend) {
      setError('This action has no configured executor and cannot be approved here.');
      return;
    }
    const exactEmail =
      gmailSend && approval.arguments
        ? `\n\nTo: ${approval.arguments.recipients?.to}\nCc: ${approval.arguments.recipients?.cc}\nBcc: ${approval.arguments.recipients?.bcc}\nSubject: ${approval.arguments.subject}\n\n${approval.arguments.body}`
        : '';
    if (
      decision === 'approve' &&
      !window.confirm(`Approve ${gmailSend ? 'and send' : 'and execute'} this action?\n\n${approval.description}${exactEmail}`)
    )
      return;
    setBusy(true);
    setError('');
    try {
      await request(`approvals/${approval.id}/${decision}`, { method: 'POST' });
      if (decision === 'approve') {
        await request(`approved-actions/${approval.id}/execute`, { method: 'POST' });
      }
      await refresh();
      showNotice(
        decision === 'approve'
          ? gmailSend
            ? 'Email sent.'
            : 'Approved action executed.'
          : 'Action rejected.'
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Approval could not be completed.');
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  // Consistent Form Control Styles matching design system
  const field =
    'w-full rounded-xl border border-border bg-bg px-3.5 py-2 text-xs text-fg placeholder:text-fg-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/20 transition-all';
  const primary =
    'inline-flex items-center justify-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-accent-fg shadow-2xs transition-colors hover:bg-accent-hover disabled:opacity-50 active:scale-95';
  const formPrimary = `${primary} self-end h-[34px]`;
  const secondary =
    'inline-flex items-center justify-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-fg transition-colors hover:bg-surface-hover hover:border-accent/40 disabled:opacity-50';
  const danger =
    'inline-flex items-center justify-center gap-1.5 rounded-xl border border-error/20 bg-error/5 px-2.5 py-1.5 text-xs font-semibold text-error transition-colors hover:bg-error/15 disabled:opacity-50';

  const nav: { id: Section; label: string; count?: number }[] = [
    { id: 'memories', label: 'Memories', count: memories.length },
    { id: 'projects', label: 'Projects', count: projects.length },
    { id: 'tasks', label: 'Tasks', count: tasks.length },
    { id: 'reminders', label: 'Reminders', count: reminders.length },
    { id: 'approvals', label: 'Approvals', count: approvals.length },
    { id: 'connections', label: 'Connections', count: connections.length },
  ];

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-bg text-fg">
      {/* ─── Top Header ────────────────────────────────────────── */}
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-4 shrink-0 shadow-2xs">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-fg shadow-xs">
            <NotebookTabs size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-fg">Memory & Follow-Through</h1>
              <span className="rounded-full bg-accent-muted px-2 py-0.5 font-mono text-[11px] font-semibold text-accent">
                {memories.length + tasks.length + projects.length + reminders.length} Total Records
              </span>
            </div>
            <p className="text-xs text-fg-muted">
              Manage persistent long-term memories, project milestones, tasks, reminders, and action approvals.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={busy}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-bg px-3 py-1.5 text-xs font-medium text-fg-secondary hover:bg-surface-hover hover:text-fg transition-colors disabled:opacity-50"
            title="Refresh memory and task records"
          >
            <RefreshCw size={13} className={busy ? 'animate-spin text-accent' : ''} />
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

      {/* ─── Metrics Sub-bar & Navigation Tabs ─────────────────── */}
      <div className="border-b border-border bg-bg-secondary px-6 py-2.5 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          {/* Metrics summary */}
          <div className="flex flex-wrap items-center gap-5">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-accent" />
              <span className="font-semibold text-fg font-mono">{memories.length}</span>
              <span className="text-fg-muted">Memories</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-purple-500" />
              <span className="font-semibold text-fg font-mono">{projects.length}</span>
              <span className="text-fg-muted">Projects</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-semibold text-fg font-mono">
                {tasks.filter((t) => t.status === 'pending' || t.status === 'in_progress').length}
              </span>
              <span className="text-fg-muted">Active Tasks</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-blue-500" />
              <span className="font-semibold text-fg font-mono">{reminders.length}</span>
              <span className="text-fg-muted">Reminders</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-500" />
              <span className="font-semibold text-fg font-mono">
                {approvals.filter((a) => a.status === 'pending').length}
              </span>
              <span className="text-fg-muted">Pending Approvals</span>
            </div>
          </div>

          {/* Sub-Tabs Pill Group */}
          <div className="flex items-center gap-1 rounded-lg bg-surface p-1 border border-border overflow-x-auto">
            {nav.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSection(item.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  section === item.id
                    ? 'bg-accent text-accent-fg shadow-xs font-semibold'
                    : 'text-fg-muted hover:text-fg'
                }`}
              >
                <span>{item.label}</span>
                {item.count !== undefined && (
                  <span
                    className={`font-mono text-[10px] px-1.5 py-0.2 rounded-full ${
                      section === item.id ? 'bg-accent-fg/20 text-accent-fg' : 'bg-bg-secondary text-fg-muted'
                    }`}
                  >
                    {item.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ─── Main Content Container ────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {error && (
            <div
              role="alert"
              className="p-3.5 rounded-xl bg-error/10 border border-error/20 text-error text-xs flex items-center justify-between gap-2 animate-fade-in"
            >
              <span>{error}</span>
              <button onClick={() => setError('')} className="p-1 hover:text-error/80">
                <X size={13} />
              </button>
            </div>
          )}

          {notice && (
            <div
              role="status"
              className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-2 animate-fade-in font-medium"
            >
              <Check size={14} className="text-emerald-500" />
              <span>{notice}</span>
            </div>
          )}

          {loading ? (
            <div className="p-12 text-center text-fg-muted text-xs">
              <RefreshCw size={20} className="animate-spin text-accent mx-auto mb-2" />
              Loading your memories, tasks, and follow-through items…
            </div>
          ) : (
            <>
              {/* ═════════════════════════════════════════════════════ */}
              {/* SECTION: MEMORIES                                    */}
              {/* ═════════════════════════════════════════════════════ */}
              {section === 'memories' && (
                <div className="space-y-6 animate-fade-in">
                  {/* Memory Policy Card */}
                  <section className="rounded-2xl border border-border bg-surface p-6 shadow-2xs hover:border-accent/40 transition-all">
                    <SectionHeading
                      icon={BrainCircuit}
                      title="Memory Recall & Retention Policy"
                      subtitle="Control local memory recall, Mem0 cloud sync, allowed automatic categories, and retention limits."
                    />
                    {policy && (
                      <div className="grid max-w-4xl gap-x-8 gap-y-3 text-xs sm:grid-cols-2">
                        <PolicySwitch
                          label="Allow local memory recall"
                          checked={policy.enabled}
                          disabled={busy}
                          onChange={(enabled) =>
                            void act('memory-policy', { method: 'PUT', body: JSON.stringify({ ...policy, enabled }) })
                          }
                        />
                        <PolicySwitch
                          label="Allow opted-in exchanges to use Mem0"
                          checked={policy.hosted_memory_allowed}
                          disabled={busy}
                          onChange={(hosted_memory_allowed) =>
                            void act('memory-policy', {
                              method: 'PUT',
                              body: JSON.stringify({ ...policy, hosted_memory_allowed }),
                            })
                          }
                        />

                        <fieldset className="sm:col-span-2 pt-2 border-t border-border">
                          <legend className="mb-2 text-xs font-semibold text-fg-secondary">
                            Categories explicitly allowed for automatic saving
                          </legend>
                          <div className="flex flex-wrap gap-2">
                            {['profile', 'preference', 'project', 'episode'].map((category) => (
                              <label key={category} className="cursor-pointer">
                                <input
                                  className="peer sr-only"
                                  type="checkbox"
                                  aria-label={category}
                                  checked={policy.auto_categories.includes(category)}
                                  disabled={busy}
                                  onChange={(event) => {
                                    const auto_categories = event.target.checked
                                      ? [...policy.auto_categories, category]
                                      : policy.auto_categories.filter((item: string) => item !== category);
                                    void act('memory-policy', {
                                      method: 'PUT',
                                      body: JSON.stringify({ ...policy, auto_categories }),
                                    });
                                  }}
                                />
                                <span
                                  className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium capitalize transition-all peer-focus-visible:ring-2 peer-focus-visible:ring-accent ${
                                    policy.auto_categories.includes(category)
                                      ? 'border-accent bg-accent/10 text-accent font-semibold'
                                      : 'border-border bg-bg text-fg-secondary hover:bg-surface-hover'
                                  }`}
                                >
                                  <span
                                    className={`flex h-3.5 w-3.5 items-center justify-center rounded-sm border ${
                                      policy.auto_categories.includes(category)
                                        ? 'border-accent bg-accent text-accent-fg'
                                        : 'border-border bg-surface'
                                    }`}
                                  >
                                    {policy.auto_categories.includes(category) && <Check size={10} />}
                                  </span>
                                  {category}
                                </span>
                              </label>
                            ))}
                          </div>
                        </fieldset>

                        <div className="flex flex-wrap items-end gap-3 sm:col-span-2 pt-2">
                          <div className="grid gap-1">
                            <label className="text-[11px] font-semibold text-fg-muted" htmlFor="memory-retention-days">
                              Archive active memories after days (blank disables retention):
                            </label>
                            <input
                              id="memory-retention-days"
                              type="number"
                              min="1"
                              max="3650"
                              className="w-48 rounded-xl border border-border bg-bg px-3.5 py-1.5 text-xs text-fg focus:border-accent focus:outline-none"
                              value={policy.retention_days ?? ''}
                              onChange={(event) =>
                                setPolicy({
                                  ...policy,
                                  retention_days: event.target.value ? Number(event.target.value) : null,
                                })
                              }
                            />
                          </div>
                          <button
                            className={secondary}
                            disabled={busy}
                            onClick={() =>
                              void act('memory-policy', { method: 'PUT', body: JSON.stringify(policy) })
                            }
                          >
                            Save retention
                          </button>
                        </div>
                        <p className="text-[11px] text-fg-muted sm:col-span-2 leading-relaxed">
                          Sensitive categories are never auto-saved. Without an explicit category permission, “remember” requests wait below for your review.
                        </p>
                      </div>
                    )}
                  </section>

                  {/* Pending Memory Review Card */}
                  <section className="rounded-2xl border border-border bg-surface p-6 shadow-2xs hover:border-accent/40 transition-all">
                    <SectionHeading
                      icon={Bell}
                      title="Pending Memory Review"
                      count={candidates.length}
                      subtitle="Proposals captured from chat awaiting your approval before long-term storage."
                    />
                    {candidates.length ? (
                      <ul className="divide-y divide-border">
                        {candidates.map((candidate) => (
                          <li key={candidate.id} className="flex flex-wrap items-start justify-between gap-3 py-3.5">
                            <div className="min-w-0 flex-1">
                              <span className="mr-2 text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-accent-muted text-accent font-semibold">
                                {candidate.category}
                              </span>
                              <p className="text-xs text-fg font-medium mt-1">{candidate.content}</p>
                              <p className="mt-1 text-[11px] text-fg-muted font-mono">
                                Proposed {timestamp(candidate.created_at)} · confidence {Math.round(candidate.confidence * 100)}%
                                {candidate.source_conversation_id ? ` · chat ${candidate.source_conversation_id.slice(0, 8)}…` : ''}
                              </p>
                            </div>
                            <span className="flex items-center gap-2">
                              <button
                                className={primary}
                                disabled={busy}
                                onClick={() => void resolveCandidate(candidate, 'approve')}
                              >
                                <Check size={13} />
                                <span>Approve</span>
                              </button>
                              <button
                                className={danger}
                                disabled={busy}
                                onClick={() => void resolveCandidate(candidate, 'reject')}
                              >
                                <X size={13} />
                                <span>Reject</span>
                              </button>
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-fg-muted italic">No memories currently awaiting review.</p>
                    )}
                  </section>

                  {/* Saved Memories Card */}
                  <section className="rounded-2xl border border-border bg-surface p-6 shadow-2xs hover:border-accent/40 transition-all">
                    <SectionHeading
                      icon={BrainCircuit}
                      title="Saved Memories"
                      count={memories.length}
                      subtitle="Explicit facts and preferences recalled during reasoning and planning."
                    />

                    {/* Add Memory Form */}
                    <form
                      className="mb-5 grid gap-3 sm:grid-cols-[minmax(14rem,2fr)_1fr_1fr_auto] p-4 rounded-xl border border-border bg-bg-secondary/40"
                      onSubmit={(event) => void saveMemory(event)}
                    >
                      <div className="grid gap-1">
                        <label className="text-[11px] font-semibold text-fg-muted">New Memory Content</label>
                        <input
                          name="content"
                          aria-label="Memory content"
                          className={field}
                          placeholder="A fact you explicitly want remembered…"
                          required
                          maxLength={2000}
                        />
                      </div>
                      <ComboBox
                        name="category"
                        label="Category"
                        defaultValue="preference"
                        options={[
                          { value: 'preference', label: 'Preference' },
                          { value: 'profile', label: 'Profile' },
                          { value: 'project', label: 'Project' },
                          { value: 'episode', label: 'Episode' },
                        ]}
                      />
                      <ComboBox
                        name="project_id"
                        label="Related project"
                        options={[
                          { value: '', label: 'No project link' },
                          ...projects.map((project) => ({ value: project.id, label: project.title })),
                        ]}
                      />
                      <button className={formPrimary} disabled={busy}>
                        <Plus size={14} />
                        <span>Save</span>
                      </button>
                    </form>

                    {/* Filter */}
                    <div className="mb-4 max-w-xs">
                      <ComboBox
                        label="Filter by Category"
                        value={memoryCategoryFilter}
                        onChange={setMemoryCategoryFilter}
                        options={[
                          { value: 'all', label: 'All categories' },
                          ...Array.from(new Set(memories.map((memory) => memory.category))).map((category) => ({
                            value: category,
                            label: category,
                          })),
                        ]}
                      />
                    </div>

                    {/* Memories List */}
                    <ul className="divide-y divide-border">
                      {memories
                        .filter((memory) => memoryCategoryFilter === 'all' || memory.category === memoryCategoryFilter)
                        .map((memory) => (
                          <li key={memory.id} className="py-3">
                            {editingMemory === memory.id ? (
                              <form
                                className="grid gap-2.5 sm:grid-cols-[2fr_1fr_1fr_auto_auto] p-3 rounded-xl border border-accent/40 bg-accent/5"
                                onSubmit={(event) => void saveMemory(event, memory.id)}
                              >
                                <input
                                  name="content"
                                  aria-label="Edit memory"
                                  className={field}
                                  defaultValue={memory.content}
                                  required
                                  maxLength={2000}
                                />
                                <ComboBox
                                  name="category"
                                  label="Category"
                                  defaultValue={memory.category}
                                  options={['preference', 'profile', 'project', 'episode'].map((category) => ({
                                    value: category,
                                    label: category,
                                  }))}
                                />
                                <ComboBox
                                  name="project_id"
                                  label="Related project"
                                  defaultValue={memory.project_id ?? ''}
                                  options={[
                                    { value: '', label: 'No project link' },
                                    ...projects.map((project) => ({ value: project.id, label: project.title })),
                                  ]}
                                />
                                <button className={formPrimary} disabled={busy}>
                                  <Check size={13} />
                                  <span>Save</span>
                                </button>
                                <button
                                  type="button"
                                  className={`${secondary} self-end h-[34px]`}
                                  onClick={() => setEditingMemory(null)}
                                >
                                  Cancel
                                </button>
                              </form>
                            ) : (
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-accent-muted text-accent font-semibold">
                                      {memory.category}
                                    </span>
                                    <span className="text-[10px] text-fg-muted font-mono uppercase">
                                      {memory.status}
                                    </span>
                                  </div>
                                  <p className="text-xs text-fg font-medium leading-relaxed">{memory.content}</p>
                                  <p className="mt-1 text-[11px] text-fg-muted font-mono">
                                    Source: {memory.source} · Updated: {timestamp(memory.updated_at)}
                                    {memory.project_id
                                      ? ` · ${projects.find((project) => project.id === memory.project_id)?.title ?? 'Linked project'}`
                                      : ''}
                                  </p>
                                </div>
                                <span className="flex items-center gap-1">
                                  <button
                                    className={secondary}
                                    aria-label="Edit memory"
                                    title="Edit memory"
                                    onClick={() => setEditingMemory(memory.id)}
                                  >
                                    <Pencil size={13} />
                                  </button>
                                  <button
                                    className={secondary}
                                    aria-label="Archive memory"
                                    title="Archive memory"
                                    disabled={busy || memory.status !== 'active'}
                                    onClick={() => {
                                      if (window.confirm('Archive this memory? It will no longer be used in recall.')) {
                                        void act(`memories/${memory.id}/archive`, { method: 'POST' });
                                      }
                                    }}
                                  >
                                    <Archive size={13} />
                                  </button>
                                  <button
                                    className={danger}
                                    aria-label="Delete memory"
                                    title="Delete memory permanently"
                                    disabled={busy}
                                    onClick={() => {
                                      if (window.confirm('Permanently delete this memory?')) {
                                        void act(`memories/${memory.id}`, { method: 'DELETE' });
                                      }
                                    }}
                                  >
                                    <Trash2 size={13} />
                                  </button>
                                </span>
                              </div>
                            )}
                          </li>
                        ))}
                    </ul>
                    {!memories.length && <p className="text-xs text-fg-muted italic">No saved memories yet.</p>}
                  </section>
                </div>
              )}

              {/* ═════════════════════════════════════════════════════ */}
              {/* SECTION: PROJECTS                                    */}
              {/* ═════════════════════════════════════════════════════ */}
              {section === 'projects' && (
                <section className="rounded-2xl border border-border bg-surface p-6 shadow-2xs hover:border-accent/40 transition-all animate-fade-in">
                  <SectionHeading
                    icon={FolderKanban}
                    title="Projects & Strategic Goals"
                    count={projects.length}
                    subtitle="Organize related tasks, blockers, deadlines, and memories under milestone initiatives."
                  />

                  {/* Add Project Form */}
                  <form
                    className="mb-5 grid gap-3 md:grid-cols-3 p-4 rounded-xl border border-border bg-bg-secondary/40"
                    onSubmit={(event) => void saveProject(event)}
                  >
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Project Title</label>
                      <input name="title" aria-label="Project title" className={field} placeholder="Project title…" required />
                    </div>
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Description</label>
                      <input name="description" aria-label="Project description" className={field} placeholder="Description…" />
                    </div>
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Next Action</label>
                      <input name="next_action" aria-label="Next action" className={field} placeholder="Next immediate step…" />
                    </div>
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Progress Note</label>
                      <input name="progress" aria-label="Project progress" className={field} placeholder="Current progress note…" />
                    </div>
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Active Blocker</label>
                      <input name="blocker" aria-label="Project blocker" className={field} placeholder="Blocker if any…" />
                    </div>
                    <DateTimeField name="target_at" label="Target Completion Date" />
                    <button className={formPrimary} disabled={busy}>
                      <Plus size={14} />
                      <span>Add Project</span>
                    </button>
                  </form>

                  {/* Projects List */}
                  <ul className="divide-y divide-border">
                    {projects.map((project) => (
                      <li key={project.id} className="py-3.5">
                        {editingProject === project.id ? (
                          <form
                            className="grid gap-3 md:grid-cols-3 p-4 rounded-xl border border-accent/40 bg-accent/5"
                            onSubmit={(event) => void saveProject(event, project.id)}
                          >
                            <input name="title" aria-label="Edit project title" className={field} defaultValue={project.title} required />
                            <input name="description" aria-label="Edit project description" className={field} defaultValue={project.description} />
                            <ComboBox
                              name="status"
                              label="Status"
                              defaultValue={project.status}
                              options={['active', 'paused', 'completed', 'cancelled'].map((status) => ({
                                value: status,
                                label: status,
                              }))}
                            />
                            <ComboBox
                              name="priority"
                              label="Priority"
                              defaultValue={project.priority}
                              options={['low', 'normal', 'high'].map((priority) => ({
                                value: priority,
                                label: priority,
                              }))}
                            />
                            <input name="progress" aria-label="Project progress" className={field} defaultValue={project.progress} placeholder="Progress" />
                            <input name="blocker" aria-label="Project blocker" className={field} defaultValue={project.blocker} placeholder="Blocker" />
                            <input name="next_action" aria-label="Next action" className={field} defaultValue={project.next_action} placeholder="Next action" />
                            <DateTimeField name="target_at" label="Target date" defaultValue={localDateTime(project.target_at)} />
                            <span className="flex gap-2 self-end">
                              <button className={formPrimary} disabled={busy}>
                                <Check size={13} />
                                <span>Save</span>
                              </button>
                              <button
                                type="button"
                                className={`${secondary} h-[34px]`}
                                onClick={() => setEditingProject(null)}
                              >
                                Cancel
                              </button>
                            </span>
                          </form>
                        ) : (
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <h3 className="text-sm font-bold text-fg">{project.title}</h3>
                                <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full ${
                                  project.status === 'active'
                                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                                    : 'bg-bg-secondary text-fg-muted border border-border'
                                }`}>
                                  {project.status}
                                </span>
                                <span className="text-[10px] font-mono uppercase text-fg-muted">
                                  {project.priority} priority
                                </span>
                              </div>
                              {project.description && <p className="text-xs text-fg-secondary mt-0.5">{project.description}</p>}
                              {project.target_at && (
                                <p className="text-[11px] text-fg-muted font-mono mt-1">
                                  Target date: {timestamp(project.target_at)}
                                </p>
                              )}
                              <div className="flex flex-wrap items-center gap-4 mt-2 text-xs">
                                {project.progress && <span className="text-fg">Progress: <strong className="text-accent">{project.progress}</strong></span>}
                                {project.blocker && <span className="text-error">Blocker: {project.blocker}</span>}
                                {project.next_action && <span className="text-fg-secondary">Next: {project.next_action}</span>}
                              </div>
                              <p className="mt-2 text-[10px] text-fg-muted font-mono">
                                {tasks.filter((task) => task.project_id === project.id).length} linked tasks ·{' '}
                                {memories.filter((memory) => memory.project_id === project.id).length} linked memories
                              </p>
                            </div>
                            <button
                              className={secondary}
                              aria-label="Edit project"
                              onClick={() => setEditingProject(project.id)}
                            >
                              <Pencil size={13} />
                              <span>Edit</span>
                            </button>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                  {!projects.length && <p className="text-xs text-fg-muted italic">No projects created yet.</p>}
                </section>
              )}

              {/* ═════════════════════════════════════════════════════ */}
              {/* SECTION: TASKS                                       */}
              {/* ═════════════════════════════════════════════════════ */}
              {section === 'tasks' && (
                <section className="rounded-2xl border border-border bg-surface p-6 shadow-2xs hover:border-accent/40 transition-all animate-fade-in">
                  <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                    <SectionHeading
                      icon={ListTodo}
                      title="Tasks & Action Items"
                      count={tasks.length}
                      subtitle="Discrete action steps with priorities, due dates, and project associations."
                    />
                    <div className="w-48">
                      <ComboBox
                        label="Filter Status"
                        value={taskStatusFilter}
                        onChange={setTaskStatusFilter}
                        options={[
                          { value: 'all', label: 'All statuses' },
                          { value: 'pending', label: 'Pending' },
                          { value: 'in_progress', label: 'In progress' },
                          { value: 'completed', label: 'Completed' },
                          { value: 'cancelled', label: 'Cancelled' },
                        ]}
                      />
                    </div>
                  </div>

                  {/* Add Task Form */}
                  <form
                    className="mb-5 grid gap-3 md:grid-cols-3 p-4 rounded-xl border border-border bg-bg-secondary/40"
                    onSubmit={(event) => void saveTask(event)}
                  >
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Task Title</label>
                      <input name="title" aria-label="Task title" className={field} placeholder="Task title…" required />
                    </div>
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Description</label>
                      <input name="description" aria-label="Task description" className={field} placeholder="Description…" />
                    </div>
                    <ComboBox
                      name="project_id"
                      label="Linked Project"
                      options={[
                        { value: '', label: 'No project' },
                        ...projects.map((project) => ({ value: project.id, label: project.title })),
                      ]}
                    />
                    <ComboBox
                      name="priority"
                      label="Priority"
                      defaultValue="normal"
                      options={['normal', 'low', 'high'].map((priority) => ({
                        value: priority,
                        label: priority,
                      }))}
                    />
                    <DateTimeField name="due_at" label="Due Date & Time" />
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Timezone</label>
                      <input name="timezone" aria-label="Task timezone" className={field} defaultValue={timezone} />
                    </div>
                    <button className={formPrimary} disabled={busy}>
                      <Plus size={14} />
                      <span>Add Task</span>
                    </button>
                  </form>

                  {/* Tasks List */}
                  <ul className="divide-y divide-border">
                    {tasks
                      .filter((task) => taskStatusFilter === 'all' || task.status === taskStatusFilter)
                      .map((task) => (
                        <li key={task.id} className="py-3.5">
                          {editingTask === task.id ? (
                            <form
                              className="grid gap-3 md:grid-cols-3 p-4 rounded-xl border border-accent/40 bg-accent/5"
                              onSubmit={(event) => void saveTask(event, task.id)}
                            >
                              <input name="title" aria-label="Edit task title" className={field} defaultValue={task.title} required />
                              <input name="description" aria-label="Edit task description" className={field} defaultValue={task.description} />
                              <ComboBox
                                name="project_id"
                                label="Project"
                                defaultValue={task.project_id ?? ''}
                                options={[
                                  { value: '', label: 'No project' },
                                  ...projects.map((project) => ({ value: project.id, label: project.title })),
                                ]}
                              />
                              <ComboBox
                                name="priority"
                                label="Priority"
                                defaultValue={task.priority}
                                options={['low', 'normal', 'high'].map((priority) => ({
                                  value: priority,
                                  label: priority,
                                }))}
                              />
                              <DateTimeField name="due_at" label="Due date" defaultValue={localDateTime(task.due_at)} />
                              <input name="timezone" aria-label="Edit task timezone" className={field} defaultValue={task.timezone} />
                              <span className="flex gap-2 self-end">
                                <button className={formPrimary} disabled={busy}>
                                  <Check size={13} />
                                  <span>Save</span>
                                </button>
                                <button
                                  type="button"
                                  className={`${secondary} h-[34px]`}
                                  onClick={() => setEditingTask(null)}
                                >
                                  Cancel
                                </button>
                              </span>
                            </form>
                          ) : (
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <h3 className="text-xs font-bold text-fg">{task.title}</h3>
                                  <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full ${
                                    task.status === 'completed'
                                      ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                                      : task.status === 'in_progress'
                                      ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
                                      : 'bg-bg-secondary text-fg-muted border border-border'
                                  }`}>
                                    {task.status}
                                  </span>
                                  <span className="text-[10px] font-mono text-fg-muted uppercase">
                                    {task.priority}
                                  </span>
                                </div>
                                {task.description && <p className="text-xs text-fg-secondary mt-0.5">{task.description}</p>}
                                <div className="flex items-center gap-3 mt-1.5 text-[11px] text-fg-muted font-mono">
                                  {task.due_at && <span>Due: {timestamp(task.due_at)} ({task.timezone})</span>}
                                  {task.project_id && (
                                    <span>
                                      Project: {projects.find((project) => project.id === task.project_id)?.title ?? 'Linked project'}
                                    </span>
                                  )}
                                </div>
                              </div>
                              <span className="flex items-center gap-1">
                                {task.status === 'pending' && (
                                  <button
                                    className={secondary}
                                    aria-label="Start task"
                                    title="Start task"
                                    disabled={busy}
                                    onClick={() => void act(`tasks/${task.id}/start`, { method: 'POST' })}
                                  >
                                    <Play size={13} />
                                    <span>Start</span>
                                  </button>
                                )}
                                {task.status !== 'completed' && task.status !== 'cancelled' && (
                                  <>
                                    <button
                                      className={secondary}
                                      aria-label="Complete task"
                                      title="Complete task"
                                      disabled={busy}
                                      onClick={() => void act(`tasks/${task.id}/complete`, { method: 'POST' })}
                                    >
                                      <Check size={13} />
                                      <span>Done</span>
                                    </button>
                                    <button
                                      className={danger}
                                      aria-label="Cancel task"
                                      title="Cancel task"
                                      disabled={busy}
                                      onClick={() => {
                                        if (window.confirm(`Cancel “${task.title}”?`)) {
                                          void act(`tasks/${task.id}/cancel`, { method: 'POST' });
                                        }
                                      }}
                                    >
                                      <X size={13} />
                                    </button>
                                  </>
                                )}
                                <button
                                  className={secondary}
                                  aria-label="Edit task"
                                  title="Edit task"
                                  disabled={busy}
                                  onClick={() => setEditingTask(task.id)}
                                >
                                  <Pencil size={13} />
                                </button>
                                <button
                                  className={danger}
                                  aria-label="Delete task"
                                  title="Delete task permanently"
                                  disabled={busy}
                                  onClick={() => {
                                    if (window.confirm(`Permanently delete “${task.title}”?`)) {
                                      void act(`tasks/${task.id}`, { method: 'DELETE' });
                                    }
                                  }}
                                >
                                  <Trash2 size={13} />
                                </button>
                              </span>
                            </div>
                          )}
                        </li>
                      ))}
                  </ul>
                  {!tasks.length && (
                    <p className="text-xs text-fg-muted italic">No tasks created yet. Add one above to move a project forward.</p>
                  )}
                  {tasks.length > 0 && !tasks.some((task) => taskStatusFilter === 'all' || task.status === taskStatusFilter) && (
                    <p className="text-xs text-fg-muted italic">No tasks match this status filter.</p>
                  )}
                </section>
              )}

              {/* ═════════════════════════════════════════════════════ */}
              {/* SECTION: REMINDERS                                   */}
              {/* ═════════════════════════════════════════════════════ */}
              {section === 'reminders' && (
                <section className="rounded-2xl border border-border bg-surface p-6 shadow-2xs hover:border-accent/40 transition-all animate-fade-in">
                  <SectionHeading
                    icon={CalendarDays}
                    title="Reminders & Delivery Jobs"
                    count={reminders.length}
                    subtitle="Scheduled alerts, recurring notifications, and dispatch delivery status."
                  />

                  {/* Add Reminder Form */}
                  <form
                    className="mb-5 grid gap-3 md:grid-cols-3 p-4 rounded-xl border border-border bg-bg-secondary/40"
                    onSubmit={(event) => void saveReminder(event)}
                  >
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Reminder Text</label>
                      <input name="text" aria-label="Reminder text" className={field} placeholder="Reminder note…" required />
                    </div>
                    <DateTimeField name="scheduled_at" label="Reminder Date & Time" required />
                    <div className="grid gap-1">
                      <label className="text-[11px] font-semibold text-fg-muted">Timezone</label>
                      <input name="timezone" aria-label="Reminder timezone" className={field} defaultValue={timezone} required />
                    </div>
                    <ComboBox
                      name="task_id"
                      label="Related Task"
                      options={[
                        { value: '', label: 'No related task' },
                        ...tasks
                          .filter((task) => !['completed', 'cancelled'].includes(task.status))
                          .map((task) => ({ value: task.id, label: task.title })),
                      ]}
                    />
                    <ComboBox
                      name="recurrence"
                      label="Recurrence"
                      defaultValue="none"
                      options={[
                        { value: 'none', label: 'One time' },
                        { value: 'daily', label: 'Daily' },
                        { value: 'weekly', label: 'Weekly' },
                      ]}
                    />
                    <button className={formPrimary} disabled={busy}>
                      <Plus size={14} />
                      <span>Schedule</span>
                    </button>
                  </form>

                  {/* Reminders List */}
                  <ul className="divide-y divide-border">
                    {reminders.map((reminder) => {
                      const reminderJobs = jobs.filter((job) => job.reminder_id === reminder.id);
                      const latestJob = reminderJobs.sort((left, right) =>
                        String(right.created_at).localeCompare(String(left.created_at))
                      )[0];

                      return (
                        <li key={reminder.id} className="py-3.5">
                          {editingReminder === reminder.id ? (
                            <form
                              className="grid gap-3 md:grid-cols-3 p-4 rounded-xl border border-accent/40 bg-accent/5"
                              onSubmit={(event) => void saveReminder(event, reminder.id)}
                            >
                              <input name="text" aria-label="Edit reminder text" className={field} defaultValue={reminder.text} required />
                              <DateTimeField name="scheduled_at" label="Reminder date and time" defaultValue={localDateTime(reminder.scheduled_at)} required />
                              <input name="timezone" aria-label="Edit reminder timezone" className={field} defaultValue={reminder.timezone} required />
                              <ComboBox
                                name="task_id"
                                label="Related task"
                                defaultValue={reminder.task_id ?? ''}
                                options={[
                                  { value: '', label: 'No related task' },
                                  ...tasks.map((task) => ({ value: task.id, label: task.title })),
                                ]}
                              />
                              <ComboBox
                                name="recurrence"
                                label="Repeat"
                                defaultValue={reminder.recurrence}
                                options={[
                                  { value: 'none', label: 'One time' },
                                  { value: 'daily', label: 'Daily' },
                                  { value: 'weekly', label: 'Weekly' },
                                ]}
                              />
                              <span className="flex gap-2 self-end">
                                <button className={formPrimary} disabled={busy}>
                                  <Check size={13} />
                                  <span>Save</span>
                                </button>
                                <button
                                  type="button"
                                  className={`${secondary} h-[34px]`}
                                  onClick={() => setEditingReminder(null)}
                                >
                                  Cancel
                                </button>
                              </span>
                            </form>
                          ) : (
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <h3 className="text-xs font-bold text-fg">{reminder.text}</h3>
                                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-accent-muted text-accent font-semibold">
                                    {reminder.status}
                                  </span>
                                  <span className="text-[10px] font-mono text-fg-muted uppercase">
                                    {reminder.recurrence}
                                  </span>
                                </div>
                                <div className="flex items-center gap-3 text-[11px] text-fg-muted font-mono mt-1">
                                  <span>Scheduled: {timestamp(reminder.scheduled_at)} ({reminder.timezone})</span>
                                  <span>•</span>
                                  <span>
                                    Job: {latestJob?.status ?? 'pending'}
                                    {latestJob ? ` · ${latestJob.attempts} attempts` : ''} · in-app
                                  </span>
                                </div>
                              </div>
                              <span className="flex items-center gap-1">
                                {reminder.status === 'pending' && (
                                  <>
                                    <button
                                      className={secondary}
                                      aria-label="Edit reminder"
                                      title="Edit reminder"
                                      onClick={() => setEditingReminder(reminder.id)}
                                    >
                                      <Pencil size={13} />
                                    </button>
                                    <button
                                      className={danger}
                                      aria-label="Cancel reminder"
                                      title="Cancel reminder"
                                      disabled={busy}
                                      onClick={() => {
                                        if (window.confirm(`Cancel “${reminder.text}”?`)) {
                                          void act(`reminders/${reminder.id}`, { method: 'DELETE' });
                                        }
                                      }}
                                    >
                                      <X size={13} />
                                    </button>
                                  </>
                                )}
                              </span>
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                  {!reminders.length && <p className="text-xs text-fg-muted italic">No reminders scheduled.</p>}

                  {/* Delivered In-App Notifications Sub-list */}
                  <div className="mt-6 pt-5 border-t border-border">
                    <h3 className="text-xs font-bold text-fg mb-3 flex items-center gap-2">
                      <Bell size={14} className="text-accent" />
                      <span>Delivered In-App Notifications</span>
                    </h3>
                    <ul className="divide-y divide-border">
                      {notifications.map((notification) => (
                        <li key={notification.id} className="py-2.5 text-xs flex items-center justify-between">
                          <span className="text-fg font-medium">{notification.text}</span>
                          <span className="text-[11px] font-mono text-fg-muted">{timestamp(notification.created_at)}</span>
                        </li>
                      ))}
                    </ul>
                    {!notifications.length && (
                      <p className="text-xs text-fg-muted italic">No delivery events recorded yet.</p>
                    )}
                  </div>
                </section>
              )}

              {/* ═════════════════════════════════════════════════════ */}
              {/* SECTION: APPROVALS                                   */}
              {/* ═════════════════════════════════════════════════════ */}
              {section === 'approvals' && (
                <section className="rounded-2xl border border-border bg-surface p-6 shadow-2xs hover:border-accent/40 transition-all animate-fade-in">
                  <SectionHeading
                    icon={Check}
                    title="External & Irreversible Action Approvals"
                    count={approvals.length}
                    subtitle="Local write actions and external email sends require explicit confirmation before execution."
                  />

                  <p className="mb-4 text-xs text-fg-muted leading-relaxed">
                    Local task and reminder actions can be approved here. Gmail sending is available only after the user grants its separate scope and reviews the exact draft. Calendar event writes are not yet available.
                  </p>

                  <ul className="divide-y divide-border">
                    {approvals.map((approval) => {
                      const executable = ['task.create', 'reminder.create'].includes(approval.action);
                      return (
                        <li key={approval.id} className="flex flex-wrap items-start justify-between gap-3 py-4">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <h3 className="text-xs font-bold text-fg">{approval.description}</h3>
                              <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full ${
                                approval.status === 'approved'
                                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                                  : approval.status === 'pending'
                                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                                  : 'bg-bg-secondary text-fg-muted border border-border'
                              }`}>
                                {approval.status}
                              </span>
                              <span className="text-[10px] font-mono text-fg-muted">
                                {executable ? 'reversible local write' : approval.action === 'gmail.send_draft' ? 'external email send' : 'no local executor'}
                              </span>
                            </div>
                            <p className="text-[11px] text-fg-muted font-mono mt-0.5">
                              Action: <code className="text-accent">{approval.action}</code> · Proposed: {timestamp(approval.created_at)}
                            </p>

                            {/* Gmail exact payload inspector */}
                            {approval.action === 'gmail.send_draft' && approval.arguments && (
                              <div className="mt-3 rounded-xl border border-border bg-bg-secondary/50 p-3 text-xs space-y-1">
                                <p><strong>To:</strong> {approval.arguments.recipients?.to}</p>
                                {approval.arguments.recipients?.cc && <p><strong>Cc:</strong> {approval.arguments.recipients.cc}</p>}
                                {approval.arguments.recipients?.bcc && <p><strong>Bcc:</strong> {approval.arguments.recipients.bcc}</p>}
                                <p><strong>Subject:</strong> {approval.arguments.subject}</p>
                                <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[11px] p-2.5 rounded-lg bg-surface border border-border text-fg-secondary">
                                  {approval.arguments.body}
                                </pre>
                              </div>
                            )}
                          </div>

                          {approval.status === 'pending' && (
                            <span className="flex items-center gap-2">
                              <button
                                className={primary}
                                disabled={busy || (!executable && approval.action !== 'gmail.send_draft')}
                                title={executable || approval.action === 'gmail.send_draft' ? 'Approve exact action' : 'No executor configured'}
                                onClick={() => void resolveApproval(approval, 'approve')}
                              >
                                <Check size={13} />
                                <span>Approve</span>
                              </button>
                              <button
                                className={danger}
                                disabled={busy}
                                onClick={() => void resolveApproval(approval, 'reject')}
                              >
                                <X size={13} />
                                <span>Reject</span>
                              </button>
                            </span>
                          )}

                          {approval.status === 'approved' && (executable || approval.action === 'gmail.send_draft') && (
                            <button
                              className={secondary}
                              disabled={busy}
                              onClick={() => {
                                if (window.confirm(`Execute “${approval.description}”?`)) {
                                  void act(`approved-actions/${approval.id}/execute`, { method: 'POST' });
                                }
                              }}
                            >
                              Execute approved action
                            </button>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                  {!approvals.length && <p className="text-xs text-fg-muted italic">No pending action proposals.</p>}
                </section>
              )}

              {/* ═════════════════════════════════════════════════════ */}
              {/* SECTION: CONNECTIONS                                 */}
              {/* ═════════════════════════════════════════════════════ */}
              {section === 'connections' && (
                <section className="rounded-2xl border border-border bg-surface p-6 shadow-2xs hover:border-accent/40 transition-all animate-fade-in space-y-6">
                  <div>
                    <SectionHeading
                      icon={LinkIcon}
                      title="Integrations & Plugin Tool Registry"
                      count={pluginCapabilities.length}
                      subtitle="Discovered tool capabilities from the backend registry. A connected status confirms saved permissions."
                    />

                    <div className="grid gap-3 sm:grid-cols-2 mb-6">
                      {pluginCapabilities.map((capability) => {
                        const statusLabel: Record<PluginCapability['status'], string> = {
                          available: 'Available',
                          connected: 'Connected',
                          requires_setup: 'Needs setup',
                          requires_connection: 'Connect account',
                          permission_required: 'Permission needed',
                          disabled: 'Disabled',
                          unavailable: 'Unavailable',
                          degraded: 'Degraded',
                        };
                        return (
                          <div key={capability.id} className="min-w-0 rounded-xl border border-border bg-bg-secondary/40 p-4 hover:border-accent/30 transition-all">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <h3 className="text-xs font-bold text-fg">{capability.display_name}</h3>
                              <span className="rounded-full border border-border bg-bg px-2 py-0.5 text-[10px] font-mono" role="status">
                                {statusLabel[capability.status] || capability.status}
                              </span>
                            </div>
                            <p className="mt-1 text-xs text-fg-secondary leading-relaxed">{capability.description}</p>
                            <p className="mt-2 text-[10px] capitalize text-fg-muted font-mono">
                              {capability.category} · {capability.provider} · {capability.read_only ? 'read only' : 'write'}
                              {capability.approval_required ? ' · approval required' : ''}
                            </p>
                            <p className="mt-1.5 text-[10px] text-fg-muted font-mono truncate">
                              Operations: {capability.operations.join(', ')}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Recent Tool Activity */}
                  <div className="pt-5 border-t border-border">
                    <h3 className="text-xs font-bold text-fg mb-1">Recent Tool Activity</h3>
                    <p className="text-[11px] text-fg-muted mb-3">
                      Private inputs and responses are excluded from this activity audit log.
                    </p>
                    {pluginExecutions.length ? (
                      <ul className="divide-y divide-border">
                        {pluginExecutions.map((execution, index) => (
                          <li
                            key={execution.id ?? `${execution.tool_id}-${index}`}
                            className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-xs"
                          >
                            <span className="font-semibold text-fg">
                              {execution.display_name}{' '}
                              <span className="text-[11px] font-normal text-fg-muted font-mono">· {execution.provider}</span>
                            </span>
                            <span className="text-[11px] font-mono text-fg-muted">
                              {execution.status} · {execution.duration_ms ?? '—'} ms · {timestamp(execution.started_at)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-xs text-fg-muted italic">No recorded tool activity yet.</p>
                    )}
                  </div>

                  {/* Google Account Connections */}
                  <div className="pt-5 border-t border-border">
                    <SectionHeading
                      icon={LinkIcon}
                      title="Google Account Connections"
                      count={connections.length}
                      subtitle="Choose only the capabilities you want Life Sandbox to access. Credentials stay encrypted on backend."
                    />

                    {!connectionConfigured && (
                      <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-xs mb-4">
                        Google OAuth credentials are not configured on this server environment.
                      </div>
                    )}

                    <div className="mb-4 grid gap-2 sm:grid-cols-2">
                      {[
                        ['calendar.read', 'Read Calendar events'],
                        ['gmail.read', 'Search and read Gmail'],
                        ['gmail.draft', 'Create Gmail drafts'],
                        ['gmail.send', 'Allow sending only after explicit approval (also needs drafts)'],
                        ['drive.read', 'Search and read Google Drive files & Docs'],
                      ].map(([value, label]) => (
                        <label key={value} className="flex items-center gap-2.5 text-xs text-fg cursor-pointer">
                          <input
                            type="checkbox"
                            checked={connectionCapabilities.includes(value)}
                            onChange={(event) =>
                              setConnectionCapabilities((current) => {
                                if (event.target.checked) {
                                  return [...new Set([...current, value, ...(value === 'gmail.send' ? ['gmail.draft'] : [])])];
                                }
                                return current.filter((item) => item !== value && !(value === 'gmail.draft' && item === 'gmail.send'));
                              })
                            }
                            className="rounded border-border text-accent focus:ring-accent"
                          />
                          <span>{label}</span>
                        </label>
                      ))}
                    </div>

                    <button
                      className={primary}
                      disabled={!connectionConfigured || busy || !connectionCapabilities.length}
                      onClick={() => void connectGoogle()}
                    >
                      Connect Google Account
                    </button>

                    <ul className="mt-4 divide-y divide-border">
                      {connections.map((connection) => (
                        <li key={connection.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                          <div>
                            <h3 className="text-xs font-bold text-fg">Google · {connection.account_email ?? 'Connected account'}</h3>
                            <p className="text-[11px] text-fg-muted font-mono mt-0.5">
                              Capabilities: {connection.capabilities.join(', ')} · Status: {connection.status}
                            </p>
                          </div>
                          <button
                            className={danger}
                            disabled={busy}
                            onClick={() => void disconnectGoogle(connection.id)}
                          >
                            Disconnect
                          </button>
                        </li>
                      ))}
                    </ul>
                    {!connections.length && <p className="mt-3 text-xs text-fg-muted italic">No connected Google accounts.</p>}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
