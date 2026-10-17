import { startTransition, useCallback, useEffect, useRef, useState, type CSSProperties, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { Archive, Bell, BrainCircuit, CalendarDays, Check, ChevronDown, FolderKanban, ListTodo, Pencil, Play, Plus, RefreshCw, Trash2, X } from 'lucide-react';

type Item = Record<string, any>;
type Section = 'memories' | 'projects' | 'tasks' | 'reminders' | 'approvals';

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
    <label className="flex min-h-10 items-center justify-between gap-4 border-b border-border py-2 text-sm">
      <span>{label}</span>
      <span className="relative inline-flex h-5 w-9 shrink-0">
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
          className="absolute inset-0 rounded-full bg-bg-tertiary transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-surface after:shadow-sm after:transition-transform peer-checked:bg-accent peer-checked:after:translate-x-4 peer-focus-visible:ring-2 peer-focus-visible:ring-accent peer-disabled:opacity-50"
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
    <div className={`life-field ${className}`} ref={root}>
      <span className="life-field-label">{label}</span>
      {name && <input type="hidden" name={name} value={selected} />}
      <span className="relative block">
        <button
          type="button"
          className="life-control flex w-full items-center justify-between gap-2 text-left"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label={label}
          disabled={disabled}
          onClick={() => setOpen((currentOpen) => !currentOpen)}
        >
          <span className={current ? 'truncate text-fg' : 'text-fg-muted'}>{current?.label ?? 'Choose an option'}</span>
          <ChevronDown aria-hidden="true" size={15} className={`shrink-0 text-fg-muted transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
        {open && (
          <div className="life-combobox-menu" role="listbox" aria-label={label}>
            {options.map((option) => (
              <button
                type="button"
                role="option"
                aria-selected={option.value === selected}
                key={option.value}
                className={`life-combobox-option ${option.value === selected ? 'is-selected' : ''}`}
                onClick={() => choose(option.value)}
              >
                <span>{option.label}</span>
                {option.value === selected && <Check size={14} />}
              </button>
            ))}
          </div>
        )}
      </span>
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
    setValue(`${datePart || today.toISOString().slice(0, 10)}T${String(nextHour24).padStart(2, '0')}:${String(minute).padStart(2, '0')}`);
    setClockMode('minute');
  }

  function updateMinute(nextMinute: number) {
    setValue(`${datePart || today.toISOString().slice(0, 10)}T${String(hour24).padStart(2, '0')}:${String(nextMinute).padStart(2, '0')}`);
  }

  function updatePeriod(nextPeriod: 'AM' | 'PM') {
    const nextHour = nextPeriod === 'PM' ? (displayHour % 12) + 12 : displayHour % 12;
    setValue(`${datePart || today.toISOString().slice(0, 10)}T${String(nextHour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`);
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
    <div className="life-field relative" ref={root}>
      <span className="life-field-label">{label}</span>
      <input type="hidden" name={name} value={value} required={required} />
      <button type="button" className="life-control flex w-full items-center justify-between gap-2 text-left" onClick={() => setOpen((currentOpen) => !currentOpen)} aria-expanded={open} aria-label={label}>
        <span className={value ? 'text-fg' : 'text-fg-muted'}>{value ? `${datePart} · ${timePart}` : 'Choose date and time'}</span>
        <CalendarDays size={15} className="shrink-0 text-fg-muted" />
      </button>
      {open && (
        <div className="life-date-popover">
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="life-icon-button" aria-label="Previous month" onClick={() => setMonth(new Date(year, monthIndex - 1, 1))}>‹</button>
            <strong className="text-sm">{monthName}</strong>
            <button type="button" className="life-icon-button" aria-label="Next month" onClick={() => setMonth(new Date(year, monthIndex + 1, 1))}>›</button>
          </div>
          <div className="mt-3 grid grid-cols-7 gap-1 text-center text-[10px] font-semibold text-fg-muted">
            {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}
          </div>
          <div className="mt-1 grid grid-cols-7 gap-1">
            {dayCells.map((day, index) => day === null ? <span key={`blank-${index}`} /> : (
              <button type="button" key={day} className={`life-calendar-day ${datePart === `${year}-${String(monthIndex + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}` ? 'is-selected' : ''}`} onClick={() => updateDate(day)}>{day}</button>
            ))}
          </div>
          <div className="mt-3 border-t border-border pt-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="life-field-label">Time</span>
              <span className="life-clock-readout">{displayHour}:{String(minute).padStart(2, '0')} <span>{period}</span></span>
            </div>
            <div className="mb-3 flex items-center justify-between gap-2 rounded-lg bg-bg-secondary p-1">
              <div className="flex gap-1">
                {(['hour', 'minute'] as const).map((mode) => <button key={mode} type="button" className={`life-clock-tab ${clockMode === mode ? 'is-active' : ''}`} onClick={() => setClockMode(mode)}>{mode === 'hour' ? 'Hour' : 'Minute'}</button>)}
              </div>
              <div className="flex gap-1">
                {(['AM', 'PM'] as const).map((nextPeriod) => <button key={nextPeriod} type="button" className={`life-clock-period ${period === nextPeriod ? 'is-active' : ''}`} onClick={() => updatePeriod(nextPeriod)}>{nextPeriod}</button>)}
              </div>
            </div>
            <div ref={minuteClockRef} className={`life-clock ${clockMode === 'minute' ? 'life-clock-minute' : 'life-clock-hour'}`} role="slider" tabIndex={0} aria-label={`Choose ${clockMode}`} aria-valuemin={clockMode === 'hour' ? 1 : 0} aria-valuemax={clockMode === 'hour' ? 12 : 59} aria-valuenow={clockMode === 'hour' ? displayHour : minute} onPointerDown={clockMode === 'minute' ? handleDialPointerDown : undefined} onPointerMove={clockMode === 'minute' ? handleDialPointerMove : undefined}>
              <span className="life-clock-center" />
              <span className="life-clock-hand" style={{ '--clock-angle': `${clockMode === 'hour' ? (displayHour % 12) * 30 : minuteAngle}deg` } as CSSProperties} />
              {clockMode === 'hour'
                ? clockValues.map((clockValue) => <button key={clockValue} type="button" className={`life-clock-number ${clockValue === displayHour ? 'is-selected' : ''}`} style={{ '--clock-angle': `${(clockValue % 12) * 30}deg` } as CSSProperties} onClick={() => updateHour(clockValue)}>{clockValue}</button>)
                : Array.from({ length: 12 }, (_, index) => index * 5).map((minuteValue, index) => <span key={minuteValue} className={`life-clock-number ${minuteValue === minute ? 'is-selected' : ''}`} style={{ '--clock-angle': `${index * 30}deg` } as CSSProperties}>{String(minuteValue).padStart(2, '0')}</span>)}
            </div>
            <p className="mt-2 text-center text-[10px] text-fg-muted">Click or drag the dial to set the {clockMode}.</p>
          </div>
          <button type="button" className="mt-3 w-full rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-accent-fg hover:bg-accent-hover" onClick={() => setOpen(false)}>Apply</button>
        </div>
      )}
    </div>
  );
}

function SectionHeading({ icon: Icon, title, count }: { icon: typeof BrainCircuit; title: string; count?: number }) {
  return (
    <div className="life-section-heading">
      <span className="life-section-icon"><Icon size={16} /></span>
      <h2>{title}</h2>
      {count !== undefined && <span className="life-count">{count}</span>}
    </div>
  );
}

export default function LifePanel({ onClose }: { onClose: () => void }) {
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
      const [m, c, t, r, a, p, n, mp, j] = await Promise.all([
        request('memories'), request('memory-candidates'), request('tasks'),
        request('reminder-schedules'), request('approvals'), request('projects'),
        request('notifications'), request('memory-policy'), request('jobs'),
      ]);
      startTransition(() => {
        setMemories(m.items);
        setCandidates(c.items);
        setTasks(t.items);
        setReminders(r.items);
        setApprovals(a.items);
        setProjects(p.items);
        setNotifications(n.items);
        setPolicy(mp);
        setJobs(j.items);
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
          method: 'PATCH', body: JSON.stringify({ project_id: projectId }),
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
      method: projectId ? 'PATCH' : 'POST', body: JSON.stringify(payload),
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
      method: taskId ? 'PATCH' : 'POST', body: JSON.stringify(payload),
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
      : payload.recurrence === 'none' ? 'reminders' : 'reminders/recurring';
    const saved = await act(path, {
      method: reminderId ? 'PATCH' : 'POST', body: JSON.stringify(payload),
    });
    if (saved) setEditingReminder(null);
  }

  async function resolveCandidate(candidate: Item, decision: 'approve' | 'reject') {
    if (decision === 'approve' && !window.confirm(`Save this ${candidate.category} memory?\n\n${candidate.content}`)) return;
    await act(`memory-candidates/${candidate.id}/${decision}`, { method: 'POST' });
  }

  async function resolveApproval(approval: Item, decision: 'approve' | 'reject') {
    const executable = ['task.create', 'reminder.create'].includes(approval.action);
    if (decision === 'approve' && !executable) {
      setError('This action has no safe local executor and cannot be approved here.');
      return;
    }
    if (decision === 'approve' && !window.confirm(`Approve and execute this action?\n\n${approval.description}`)) return;
    setBusy(true);
    setError('');
    try {
      await request(`approvals/${approval.id}/${decision}`, { method: 'POST' });
      if (decision === 'approve') {
        await request(`approved-actions/${approval.id}/execute`, { method: 'POST' });
      }
      await refresh();
      showNotice(decision === 'approve' ? 'Approved action executed.' : 'Action rejected.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Approval could not be completed.');
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  const field = 'min-h-10 min-w-0 rounded-md border border-border-strong bg-surface px-3 py-2 text-sm text-fg placeholder:text-fg-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20';
  const primary = 'inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-hover disabled:opacity-50';
  const formPrimary = `${primary} self-end h-10 min-h-0`;
  const secondary = 'inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md border border-border-strong bg-surface px-3 py-2 text-sm text-fg transition-colors hover:bg-surface-hover disabled:opacity-50';
  const danger = 'inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md px-3 py-2 text-sm text-error transition-colors hover:bg-error/10 disabled:opacity-50';
  const nav: { id: Section; label: string }[] = [
    { id: 'memories', label: 'Memories' }, { id: 'projects', label: 'Projects' },
    { id: 'tasks', label: 'Tasks' }, { id: 'reminders', label: 'Reminders' },
    { id: 'approvals', label: 'Approvals' },
  ];

  return (
    <section className="flex h-full min-w-0 flex-1 flex-col overflow-y-auto bg-bg px-4 py-5 text-fg sm:px-6">
      <header className="mx-auto mb-4 flex w-full max-w-6xl items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Memory & follow-through</h1>
          <p className="mt-1 text-sm text-fg-muted">Manage saved facts, projects, tasks, reminders, and approvals.</p>
        </div>
        <button className={secondary} onClick={onClose}><X size={16} />Back to chat</button>
      </header>
      <nav className="life-tabs mx-auto mb-4 flex w-full max-w-6xl flex-wrap items-center gap-1" aria-label="Follow-through sections" role="tablist">
        {nav.map((item) => (
          <button key={item.id} role="tab" aria-selected={section === item.id}
            className={`border-b-2 px-3 py-2 text-sm ${section === item.id ? 'border-accent font-semibold text-fg' : 'border-transparent text-fg-muted hover:text-fg'}`}
            onClick={() => setSection(item.id)}>{item.label}</button>
        ))}
        <button className="mb-1 ml-auto inline-grid h-9 w-9 place-items-center rounded-lg border border-border bg-surface text-fg-muted shadow-xs transition-colors hover:border-border-strong hover:bg-surface-hover hover:text-fg disabled:opacity-50" onClick={() => void refresh()} disabled={busy} aria-label="Refresh data" title="Refresh data"><RefreshCw size={15} /></button>
      </nav>
      {error && <p role="alert" className="mx-auto mb-3 w-full max-w-6xl border-l-2 border-error px-3 py-1.5 text-sm text-error">{error}</p>}
      {notice && <p role="status" className="mx-auto mb-3 flex w-full max-w-6xl items-center gap-1.5 text-xs text-success"><Check size={14} />{notice}</p>}
      {loading ? <p role="status" className="py-8 text-sm text-fg-muted">Loading your data…</p> : (
        <div className="mx-auto min-w-0 w-full max-w-6xl flex-1 space-y-6">
          {section === 'memories' && <>
            <section className="life-card">
              <SectionHeading icon={BrainCircuit} title="Memory policy" />
              {policy && <div className="grid max-w-3xl gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
                <PolicySwitch label="Allow local memory recall" checked={policy.enabled} disabled={busy} onChange={(enabled) => void act('memory-policy', { method: 'PUT', body: JSON.stringify({ ...policy, enabled }) })} />
                <PolicySwitch label="Allow opted-in exchanges to use Mem0" checked={policy.hosted_memory_allowed} disabled={busy} onChange={(hosted_memory_allowed) => void act('memory-policy', { method: 'PUT', body: JSON.stringify({ ...policy, hosted_memory_allowed }) })} />
                <fieldset className="sm:col-span-2">
                  <legend className="mb-2 text-fg-muted">Categories explicitly allowed for automatic saving</legend>
                  <div className="flex flex-wrap gap-x-4 gap-y-2">
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
                        <span className={`inline-flex min-h-8 items-center gap-2 rounded-md border px-2.5 text-xs capitalize transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-accent ${policy.auto_categories.includes(category) ? 'border-accent bg-accent-muted text-accent' : 'border-border-strong bg-surface text-fg-secondary hover:bg-surface-hover'}`}>
                          <span className={`grid h-4 w-4 place-items-center rounded-sm border ${policy.auto_categories.includes(category) ? 'border-accent bg-accent text-accent-fg' : 'border-border-strong bg-bg'}`}>
                            {policy.auto_categories.includes(category) && <Check size={11} />}
                          </span>
                          {category}
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>
                <div className="flex flex-wrap items-end gap-2 sm:col-span-2">
                  <label className="grid gap-1 text-sm text-fg-muted" htmlFor="memory-retention-days">
                    Archive active memories after days (blank disables retention)
                    <input id="memory-retention-days" type="number" min="1" max="3650" className={field}
                      value={policy.retention_days ?? ''}
                      onChange={(event) => setPolicy({ ...policy, retention_days: event.target.value ? Number(event.target.value) : null })} />
                  </label>
                  <button className={secondary} disabled={busy} onClick={() => void act('memory-policy', { method: 'PUT', body: JSON.stringify(policy) })}>Save retention</button>
                </div>
                <p className="text-xs text-fg-muted sm:col-span-2">Sensitive categories are never auto-saved. Without an explicit category permission, “remember” requests wait here for your approval.</p>
              </div>}
            </section>
            <section className="life-card">
              <SectionHeading icon={Bell} title="Pending memory review" count={candidates.length} />
              {candidates.length ? <ul className="divide-y divide-border">{candidates.map((candidate) => <li key={candidate.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="min-w-0"><span className="mr-2 text-xs uppercase text-fg-muted">{candidate.category}</span><p>{candidate.content}</p><p className="mt-1 text-xs text-fg-muted">From {timestamp(candidate.created_at)} · confidence {Math.round(candidate.confidence * 100)}%{candidate.source_conversation_id ? ` · conversation ${candidate.source_conversation_id}` : ''}</p></div>
                <span className="flex gap-2"><button className={primary} disabled={busy} onClick={() => void resolveCandidate(candidate, 'approve')}><Check size={15} />Approve</button><button className={danger} disabled={busy} onClick={() => void resolveCandidate(candidate, 'reject')}><X size={15} />Reject</button></span>
              </li>)}</ul> : <p className="text-sm text-fg-muted">No memories awaiting review.</p>}
            </section>
            <section className="life-card">
              <SectionHeading icon={BrainCircuit} title="Saved memories" count={memories.length} />
              <form className="mb-4 grid gap-2 sm:grid-cols-[minmax(12rem,2fr)_1fr_1fr_auto]" onSubmit={(event) => void saveMemory(event)}>
                <input name="content" aria-label="Memory content" className={field} placeholder="A fact you explicitly want remembered" required maxLength={2000} />
                <ComboBox name="category" label="Category" defaultValue="preference" options={[{ value: 'preference', label: 'Preference' }, { value: 'profile', label: 'Profile' }, { value: 'project', label: 'Project' }, { value: 'episode', label: 'Episode' }]} />
                <ComboBox name="project_id" label="Related project" options={[{ value: '', label: 'No project link' }, ...projects.map((project) => ({ value: project.id, label: project.title }))]} />
                <button className={formPrimary} disabled={busy}><Plus size={15} />Save</button>
              </form>
              <div className="mb-3 max-w-48"><ComboBox label="Filter category" value={memoryCategoryFilter} onChange={setMemoryCategoryFilter} options={[{ value: 'all', label: 'All categories' }, ...Array.from(new Set(memories.map((memory) => memory.category))).map((category) => ({ value: category, label: category }))]} /></div>
              <ul className="divide-y divide-border">{memories.filter((memory) => memoryCategoryFilter === 'all' || memory.category === memoryCategoryFilter).map((memory) => <li key={memory.id} className="py-3">
                {editingMemory === memory.id ? <form className="grid gap-2 sm:grid-cols-[2fr_1fr_1fr_auto_auto]" onSubmit={(event) => void saveMemory(event, memory.id)}>
                  <input name="content" aria-label="Edit memory" className={field} defaultValue={memory.content} required maxLength={2000} />
                  <ComboBox name="category" label="Category" defaultValue={memory.category} options={['preference', 'profile', 'project', 'episode'].map((category) => ({ value: category, label: category }))} />
                  <ComboBox name="project_id" label="Related project" defaultValue={memory.project_id ?? ''} options={[{ value: '', label: 'No project link' }, ...projects.map((project) => ({ value: project.id, label: project.title }))]} />
                  <button className={formPrimary} disabled={busy}><Check size={15} />Save</button><button type="button" className={`${secondary} self-end h-10 min-h-0`} onClick={() => setEditingMemory(null)}>Cancel</button>
                </form> : <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0"><span className="mr-2 text-xs uppercase text-fg-muted">{memory.category} · {memory.status}</span><p>{memory.content}</p><p className="mt-1 text-xs text-fg-muted">{memory.source} · {timestamp(memory.updated_at)}{memory.project_id ? ` · ${projects.find((project) => project.id === memory.project_id)?.title ?? 'Linked project'}` : ''}</p></div>
                  <span className="flex gap-1"><button className={secondary} aria-label="Edit memory" title="Edit memory" onClick={() => setEditingMemory(memory.id)}><Pencil size={15} /></button><button className={secondary} aria-label="Archive memory" title="Archive memory" disabled={busy || memory.status !== 'active'} onClick={() => { if (window.confirm('Archive this memory? It will no longer be used in recall.')) void act(`memories/${memory.id}/archive`, { method: 'POST' }); }}><Archive size={15} /></button><button className={danger} aria-label="Delete memory" title="Delete memory permanently" disabled={busy} onClick={() => { if (window.confirm('Permanently delete this memory?')) void act(`memories/${memory.id}`, { method: 'DELETE' }); }}><Trash2 size={15} /></button></span>
                </div>}
              </li>)}</ul>
              {!memories.length && <p className="text-sm text-fg-muted">No saved memories.</p>}
            </section>
          </>}

          {section === 'projects' && <section className="life-card">
            <SectionHeading icon={FolderKanban} title="Projects" count={projects.length} />
            <form className="mb-4 grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveProject(event)}>
              <input name="title" aria-label="Project title" className={field} placeholder="Project title" required />
              <input name="description" aria-label="Project description" className={field} placeholder="Description" />
              <input name="next_action" aria-label="Next action" className={field} placeholder="Next action" />
              <input name="progress" aria-label="Project progress" className={field} placeholder="Progress" />
              <input name="blocker" aria-label="Project blocker" className={field} placeholder="Blocker" />
              <DateTimeField name="target_at" label="Target date" />
              <button className={formPrimary} disabled={busy}><Plus size={15} />Add project</button>
            </form>
            <ul className="divide-y divide-border">{projects.map((project) => <li key={project.id} className="py-3">
              {editingProject === project.id ? <form className="grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveProject(event, project.id)}>
                <input name="title" aria-label="Edit project title" className={field} defaultValue={project.title} required />
                <input name="description" aria-label="Edit project description" className={field} defaultValue={project.description} />
                <ComboBox name="status" label="Status" defaultValue={project.status} options={['active', 'paused', 'completed', 'cancelled'].map((status) => ({ value: status, label: status }))} />
                <ComboBox name="priority" label="Priority" defaultValue={project.priority} options={['low', 'normal', 'high'].map((priority) => ({ value: priority, label: priority }))} />
                <input name="progress" aria-label="Project progress" className={field} defaultValue={project.progress} placeholder="Progress" />
                <input name="blocker" aria-label="Project blocker" className={field} defaultValue={project.blocker} placeholder="Blocker" />
                <input name="next_action" aria-label="Next action" className={field} defaultValue={project.next_action} placeholder="Next action" />
                <DateTimeField name="target_at" label="Target date" defaultValue={localDateTime(project.target_at)} />
                <span className="flex gap-2 self-end"><button className={formPrimary} disabled={busy}><Check size={15} />Save</button><button type="button" className={`${secondary} h-10 min-h-0`} onClick={() => setEditingProject(null)}>Cancel</button></span>
              </form> : <div className="flex items-start justify-between gap-3">
                <div><h3 className="font-medium">{project.title}</h3><p className="text-sm text-fg-muted">{project.status} · {project.priority}{project.target_at ? ` · target ${timestamp(project.target_at)}` : ''}</p>{project.progress && <p className="mt-1 text-sm">Progress: {project.progress}</p>}{project.blocker && <p className="text-sm">Blocker: {project.blocker}</p>}{project.next_action && <p className="text-sm">Next: {project.next_action}</p>}<p className="mt-1 text-xs text-fg-muted">{tasks.filter((task) => task.project_id === project.id).length} linked tasks · {memories.filter((memory) => memory.project_id === project.id).length} linked memories</p></div>
                <button className={secondary} aria-label="Edit project" onClick={() => setEditingProject(project.id)}><Pencil size={15} />Edit</button>
              </div>}
            </li>)}</ul>
            {!projects.length && <p className="text-sm text-fg-muted">No projects yet.</p>}
          </section>}

          {section === 'tasks' && <section className="life-card">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3"><SectionHeading icon={ListTodo} title="Tasks" count={tasks.length} /><ComboBox label="Filter status" value={taskStatusFilter} onChange={setTaskStatusFilter} options={[{ value: 'all', label: 'All statuses' }, { value: 'pending', label: 'Pending' }, { value: 'in_progress', label: 'In progress' }, { value: 'completed', label: 'Completed' }, { value: 'cancelled', label: 'Cancelled' }]} /></div>
            <form className="mb-4 grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveTask(event)}>
              <input name="title" aria-label="Task title" className={field} placeholder="Task title" required />
              <input name="description" aria-label="Task description" className={field} placeholder="Description" />
              <ComboBox name="project_id" label="Project" options={[{ value: '', label: 'No project' }, ...projects.map((project) => ({ value: project.id, label: project.title }))]} />
              <ComboBox name="priority" label="Priority" defaultValue="normal" options={['normal', 'low', 'high'].map((priority) => ({ value: priority, label: priority }))} />
              <DateTimeField name="due_at" label="Due date" />
              <input name="timezone" aria-label="Task timezone" className={field} defaultValue={timezone} />
              <button className={formPrimary} disabled={busy}><Plus size={15} />Add task</button>
            </form>
            <ul className="divide-y divide-border">{tasks.filter((task) => taskStatusFilter === 'all' || task.status === taskStatusFilter).map((task) => <li key={task.id} className="py-3">
              {editingTask === task.id ? <form className="grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveTask(event, task.id)}>
                <input name="title" aria-label="Edit task title" className={field} defaultValue={task.title} required />
                <input name="description" aria-label="Edit task description" className={field} defaultValue={task.description} />
                <ComboBox name="project_id" label="Project" defaultValue={task.project_id ?? ''} options={[{ value: '', label: 'No project' }, ...projects.map((project) => ({ value: project.id, label: project.title }))]} />
                <ComboBox name="priority" label="Priority" defaultValue={task.priority} options={['low', 'normal', 'high'].map((priority) => ({ value: priority, label: priority }))} />
                <DateTimeField name="due_at" label="Due date" defaultValue={localDateTime(task.due_at)} />
                <input name="timezone" aria-label="Edit task timezone" className={field} defaultValue={task.timezone} />
                <span className="flex gap-2 self-end"><button className={formPrimary} disabled={busy}><Check size={15} />Save</button><button type="button" className={`${secondary} h-10 min-h-0`} onClick={() => setEditingTask(null)}>Cancel</button></span>
              </form> : <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h3 className="font-medium">{task.title}</h3><p className="text-sm text-fg-muted">{task.status} · {task.priority}{task.due_at ? ` · due ${timestamp(task.due_at)} (${task.timezone})` : ''}</p>{task.description && <p className="mt-1 text-sm">{task.description}</p>}{task.project_id && <p className="text-xs text-fg-muted">Project: {projects.find((project) => project.id === task.project_id)?.title ?? 'Linked project'}</p>}</div>
                <span className="flex gap-1">{task.status === 'pending' && <button className={secondary} aria-label="Start task" title="Start task" disabled={busy} onClick={() => void act(`tasks/${task.id}/start`, { method: 'POST' })}><Play size={15} /></button>}{task.status !== 'completed' && task.status !== 'cancelled' && <><button className={secondary} aria-label="Complete task" title="Complete task" disabled={busy} onClick={() => void act(`tasks/${task.id}/complete`, { method: 'POST' })}><Check size={15} /></button><button className={danger} aria-label="Cancel task" title="Cancel task" disabled={busy} onClick={() => { if (window.confirm(`Cancel “${task.title}”?`)) void act(`tasks/${task.id}/cancel`, { method: 'POST' }); }}><X size={15} /></button></>}<button className={secondary} aria-label="Edit task" title="Edit task" disabled={busy} onClick={() => setEditingTask(task.id)}><Pencil size={15} /></button><button className={danger} aria-label="Delete task" title="Delete task permanently" disabled={busy} onClick={() => { if (window.confirm(`Permanently delete “${task.title}”?`)) void act(`tasks/${task.id}`, { method: 'DELETE' }); }}><Trash2 size={15} /></button></span>
              </div>}
            </li>)}</ul>
            {!tasks.length && <p className="life-empty">No tasks yet. Add one above to start moving a project forward.</p>}
            {tasks.length > 0 && !tasks.some((task) => taskStatusFilter === 'all' || task.status === taskStatusFilter) && <p className="life-empty">No tasks match this status filter.</p>}
          </section>}

          {section === 'reminders' && <section className="life-card">
            <SectionHeading icon={CalendarDays} title="Reminders and delivery jobs" count={reminders.length} />
            <form className="mb-4 grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveReminder(event)}>
              <input name="text" aria-label="Reminder text" className={field} placeholder="Reminder" required />
              <DateTimeField name="scheduled_at" label="Reminder date and time" required />
              <input name="timezone" aria-label="Reminder timezone" className={field} defaultValue={timezone} required />
              <ComboBox name="task_id" label="Related task" options={[{ value: '', label: 'No related task' }, ...tasks.filter((task) => !['completed', 'cancelled'].includes(task.status)).map((task) => ({ value: task.id, label: task.title }))]} />
              <ComboBox name="recurrence" label="Repeat" defaultValue="none" options={[{ value: 'none', label: 'One time' }, { value: 'daily', label: 'Daily' }, { value: 'weekly', label: 'Weekly' }]} />
              <button className={formPrimary} disabled={busy}><Plus size={15} />Schedule</button>
            </form>
            <ul className="divide-y divide-border">{reminders.map((reminder) => {
              const reminderJobs = jobs.filter((job) => job.reminder_id === reminder.id);
              const latestJob = reminderJobs.sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)))[0];
              return <li key={reminder.id} className="py-3">
                {editingReminder === reminder.id ? <form className="grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveReminder(event, reminder.id)}>
                  <input name="text" aria-label="Edit reminder text" className={field} defaultValue={reminder.text} required />
                  <DateTimeField name="scheduled_at" label="Reminder date and time" defaultValue={localDateTime(reminder.scheduled_at)} required />
                  <input name="timezone" aria-label="Edit reminder timezone" className={field} defaultValue={reminder.timezone} required />
                  <ComboBox name="task_id" label="Related task" defaultValue={reminder.task_id ?? ''} options={[{ value: '', label: 'No related task' }, ...tasks.map((task) => ({ value: task.id, label: task.title }))]} />
                  <ComboBox name="recurrence" label="Repeat" defaultValue={reminder.recurrence} options={[{ value: 'none', label: 'One time' }, { value: 'daily', label: 'Daily' }, { value: 'weekly', label: 'Weekly' }]} />
                  <span className="flex gap-2 self-end"><button className={formPrimary} disabled={busy}><Check size={15} />Save</button><button type="button" className={`${secondary} h-10 min-h-0`} onClick={() => setEditingReminder(null)}>Cancel</button></span>
                </form> : <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><h3 className="font-medium">{reminder.text}</h3><p className="text-sm text-fg-muted">{reminder.status} · {timestamp(reminder.scheduled_at)} · {reminder.timezone} · {reminder.recurrence}</p><p className="text-xs text-fg-muted">Job: {latestJob?.status ?? 'not found'}{latestJob ? ` · ${latestJob.attempts} attempts` : ''} · in-app delivery</p></div>
                  <span className="flex gap-1">{reminder.status === 'pending' && <><button className={secondary} aria-label="Edit reminder" title="Edit reminder" onClick={() => setEditingReminder(reminder.id)}><Pencil size={15} /></button><button className={danger} aria-label="Cancel reminder" title="Cancel reminder" disabled={busy} onClick={() => { if (window.confirm(`Cancel “${reminder.text}”?`)) void act(`reminders/${reminder.id}`, { method: 'DELETE' }); }}><X size={15} /></button></>}</span>
                </div>}
              </li>;
            })}</ul>
            {!reminders.length && <p className="text-sm text-fg-muted">No reminders scheduled.</p>}
            <h3 className="mb-2 mt-6 font-medium">Delivered in-app notifications</h3>
            <ul className="divide-y divide-border">{notifications.map((notification) => <li key={notification.id} className="py-2 text-sm">{notification.text}<span className="ml-2 text-xs text-fg-muted">{timestamp(notification.created_at)}</span></li>)}</ul>
            {!notifications.length && <p className="text-sm text-fg-muted">No delivery events yet.</p>}
          </section>}

          {section === 'approvals' && <section>
            <h2 className="mb-3 font-semibold">Action approvals</h2>
            <p className="mb-3 text-sm text-fg-muted">Only validated local task and reminder actions can execute here. Email, purchases, and other external actions are not connected.</p>
            <ul className="divide-y divide-border">{approvals.map((approval) => {
              const executable = ['task.create', 'reminder.create'].includes(approval.action);
              return <li key={approval.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div><h3 className="font-medium">{approval.description}</h3><p className="text-sm text-fg-muted">{approval.action} · {approval.status} · {executable ? 'reversible local write' : 'no local executor'}</p><p className="text-xs text-fg-muted">Proposed {timestamp(approval.created_at)}</p></div>
                {approval.status === 'pending' && <span className="flex gap-2"><button className={primary} disabled={busy || !executable} title={executable ? 'Approve and execute' : 'No local executor'} onClick={() => void resolveApproval(approval, 'approve')}><Check size={15} />Approve</button><button className={danger} disabled={busy} onClick={() => void resolveApproval(approval, 'reject')}><X size={15} />Reject</button></span>}
                {approval.status === 'approved' && executable && <button className={secondary} disabled={busy} onClick={() => { if (window.confirm(`Execute “${approval.description}”?`)) void act(`approved-actions/${approval.id}/execute`, { method: 'POST' }); }}>Execute approved action</button>}
              </li>;
            })}</ul>
            {!approvals.length && <p className="text-sm text-fg-muted">No action proposals.</p>}
          </section>}
        </div>
      )}
    </section>
  );
}
