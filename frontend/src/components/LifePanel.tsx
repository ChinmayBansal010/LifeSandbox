import { startTransition, useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Archive, Check, Pencil, Play, Plus, RefreshCw, Trash2, X } from 'lucide-react';

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
      <nav className="mx-auto mb-4 flex w-full max-w-6xl flex-wrap items-center gap-1 border-b border-border" aria-label="Follow-through sections">
        {nav.map((item) => (
          <button key={item.id} role="tab" aria-selected={section === item.id}
            className={`border-b-2 px-3 py-2 text-sm ${section === item.id ? 'border-accent font-semibold text-fg' : 'border-transparent text-fg-muted hover:text-fg'}`}
            onClick={() => setSection(item.id)}>{item.label}</button>
        ))}
        <button className="mb-1 ml-auto inline-grid h-9 w-9 place-items-center rounded-md text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg disabled:opacity-50" onClick={() => void refresh()} disabled={busy} aria-label="Refresh data" title="Refresh data"><RefreshCw size={15} /></button>
      </nav>
      {error && <p role="alert" className="mx-auto mb-3 w-full max-w-6xl border-l-2 border-error px-3 py-1.5 text-sm text-error">{error}</p>}
      {notice && <p role="status" className="mx-auto mb-3 flex w-full max-w-6xl items-center gap-1.5 text-xs text-success"><Check size={14} />{notice}</p>}
      {loading ? <p role="status" className="py-8 text-sm text-fg-muted">Loading your data…</p> : (
        <div className="mx-auto min-w-0 w-full max-w-6xl flex-1 space-y-6">
          {section === 'memories' && <>
            <section className="border-b border-border pb-5">
              <h2 className="mb-3 font-semibold">Memory policy</h2>
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
            <section className="border-b border-border pb-5">
              <h2 className="mb-3 font-semibold">Pending memory review <span className="font-normal text-fg-muted">{candidates.length}</span></h2>
              {candidates.length ? <ul className="divide-y divide-border">{candidates.map((candidate) => <li key={candidate.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="min-w-0"><span className="mr-2 text-xs uppercase text-fg-muted">{candidate.category}</span><p>{candidate.content}</p><p className="mt-1 text-xs text-fg-muted">From {timestamp(candidate.created_at)} · confidence {Math.round(candidate.confidence * 100)}%{candidate.source_conversation_id ? ` · conversation ${candidate.source_conversation_id}` : ''}</p></div>
                <span className="flex gap-2"><button className={primary} disabled={busy} onClick={() => void resolveCandidate(candidate, 'approve')}><Check size={15} />Approve</button><button className={danger} disabled={busy} onClick={() => void resolveCandidate(candidate, 'reject')}><X size={15} />Reject</button></span>
              </li>)}</ul> : <p className="text-sm text-fg-muted">No memories awaiting review.</p>}
            </section>
            <section className="border-b border-border pb-5">
              <h2 className="mb-3 font-semibold">Saved memories</h2>
              <form className="mb-4 grid gap-2 sm:grid-cols-[minmax(12rem,2fr)_1fr_1fr_auto]" onSubmit={(event) => void saveMemory(event)}>
                <input name="content" aria-label="Memory content" className={field} placeholder="A fact you explicitly want remembered" required maxLength={2000} />
                <select name="category" aria-label="Memory category" className={`${field} app-select`}><option value="preference">Preference</option><option value="profile">Profile</option><option value="project">Project</option><option value="episode">Episode</option></select>
                <select name="project_id" aria-label="Related project" className={`${field} app-select`}><option value="">No project link</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}</select>
                <button className={primary} disabled={busy}><Plus size={15} />Save</button>
              </form>
              <div className="mb-3 flex items-center gap-2"><label htmlFor="memory-category-filter" className="text-sm text-fg-muted">Category</label><select id="memory-category-filter" className={`${field} app-select`} value={memoryCategoryFilter} onChange={(event) => setMemoryCategoryFilter(event.target.value)}><option value="all">All</option>{Array.from(new Set(memories.map((memory) => memory.category))).map((category) => <option key={category}>{category}</option>)}</select></div>
              <ul className="divide-y divide-border">{memories.filter((memory) => memoryCategoryFilter === 'all' || memory.category === memoryCategoryFilter).map((memory) => <li key={memory.id} className="py-3">
                {editingMemory === memory.id ? <form className="grid gap-2 sm:grid-cols-[2fr_1fr_1fr_auto_auto]" onSubmit={(event) => void saveMemory(event, memory.id)}>
                  <input name="content" aria-label="Edit memory" className={field} defaultValue={memory.content} required maxLength={2000} />
                  <select name="category" aria-label="Edit memory category" className={`${field} app-select`} defaultValue={memory.category}>{['preference', 'profile', 'project', 'episode'].map((category) => <option key={category}>{category}</option>)}</select>
                  <select name="project_id" aria-label="Link memory to project" className={`${field} app-select`} defaultValue={memory.project_id ?? ''}><option value="">No project link</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}</select>
                  <button className={primary} disabled={busy}><Check size={15} />Save</button><button type="button" className={secondary} onClick={() => setEditingMemory(null)}>Cancel</button>
                </form> : <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0"><span className="mr-2 text-xs uppercase text-fg-muted">{memory.category} · {memory.status}</span><p>{memory.content}</p><p className="mt-1 text-xs text-fg-muted">{memory.source} · {timestamp(memory.updated_at)}{memory.project_id ? ` · ${projects.find((project) => project.id === memory.project_id)?.title ?? 'Linked project'}` : ''}</p></div>
                  <span className="flex gap-1"><button className={secondary} aria-label="Edit memory" title="Edit memory" onClick={() => setEditingMemory(memory.id)}><Pencil size={15} /></button><button className={secondary} aria-label="Archive memory" title="Archive memory" disabled={busy || memory.status !== 'active'} onClick={() => { if (window.confirm('Archive this memory? It will no longer be used in recall.')) void act(`memories/${memory.id}/archive`, { method: 'POST' }); }}><Archive size={15} /></button><button className={danger} aria-label="Delete memory" title="Delete memory permanently" disabled={busy} onClick={() => { if (window.confirm('Permanently delete this memory?')) void act(`memories/${memory.id}`, { method: 'DELETE' }); }}><Trash2 size={15} /></button></span>
                </div>}
              </li>)}</ul>
              {!memories.length && <p className="text-sm text-fg-muted">No saved memories.</p>}
            </section>
          </>}

          {section === 'projects' && <section>
            <h2 className="mb-3 font-semibold">Projects</h2>
            <form className="mb-4 grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveProject(event)}>
              <input name="title" aria-label="Project title" className={field} placeholder="Project title" required />
              <input name="description" aria-label="Project description" className={field} placeholder="Description" />
              <input name="next_action" aria-label="Next action" className={field} placeholder="Next action" />
              <input name="progress" aria-label="Project progress" className={field} placeholder="Progress" />
              <input name="blocker" aria-label="Project blocker" className={field} placeholder="Blocker" />
              <input name="target_at" aria-label="Project target date" className={`${field} app-date-time`} type="datetime-local" />
              <button className={primary} disabled={busy}><Plus size={15} />Add project</button>
            </form>
            <ul className="divide-y divide-border">{projects.map((project) => <li key={project.id} className="py-3">
              {editingProject === project.id ? <form className="grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveProject(event, project.id)}>
                <input name="title" aria-label="Edit project title" className={field} defaultValue={project.title} required />
                <input name="description" aria-label="Edit project description" className={field} defaultValue={project.description} />
                <select name="status" aria-label="Project status" className={`${field} app-select`} defaultValue={project.status}><option>active</option><option>paused</option><option>completed</option><option>cancelled</option></select>
                <select name="priority" aria-label="Project priority" className={`${field} app-select`} defaultValue={project.priority}><option>low</option><option>normal</option><option>high</option></select>
                <input name="progress" aria-label="Project progress" className={field} defaultValue={project.progress} placeholder="Progress" />
                <input name="blocker" aria-label="Project blocker" className={field} defaultValue={project.blocker} placeholder="Blocker" />
                <input name="next_action" aria-label="Next action" className={field} defaultValue={project.next_action} placeholder="Next action" />
                <input name="target_at" aria-label="Target date" className={`${field} app-date-time`} type="datetime-local" defaultValue={localDateTime(project.target_at)} />
                <span className="flex gap-2"><button className={primary} disabled={busy}><Check size={15} />Save</button><button type="button" className={secondary} onClick={() => setEditingProject(null)}>Cancel</button></span>
              </form> : <div className="flex items-start justify-between gap-3">
                <div><h3 className="font-medium">{project.title}</h3><p className="text-sm text-fg-muted">{project.status} · {project.priority}{project.target_at ? ` · target ${timestamp(project.target_at)}` : ''}</p>{project.progress && <p className="mt-1 text-sm">Progress: {project.progress}</p>}{project.blocker && <p className="text-sm">Blocker: {project.blocker}</p>}{project.next_action && <p className="text-sm">Next: {project.next_action}</p>}<p className="mt-1 text-xs text-fg-muted">{tasks.filter((task) => task.project_id === project.id).length} linked tasks · {memories.filter((memory) => memory.project_id === project.id).length} linked memories</p></div>
                <button className={secondary} aria-label="Edit project" onClick={() => setEditingProject(project.id)}><Pencil size={15} />Edit</button>
              </div>}
            </li>)}</ul>
            {!projects.length && <p className="text-sm text-fg-muted">No projects yet.</p>}
          </section>}

          {section === 'tasks' && <section>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">Tasks</h2><select aria-label="Filter tasks by status" className={`${field} app-select`} value={taskStatusFilter} onChange={(event) => setTaskStatusFilter(event.target.value)}><option value="all">All statuses</option><option>pending</option><option>in_progress</option><option>completed</option><option>cancelled</option></select></div>
            <form className="mb-4 grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveTask(event)}>
              <input name="title" aria-label="Task title" className={field} placeholder="Task title" required />
              <input name="description" aria-label="Task description" className={field} placeholder="Description" />
              <select name="project_id" aria-label="Task project" className={`${field} app-select`}><option value="">No project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}</select>
              <select name="priority" aria-label="Task priority" className={`${field} app-select`}><option>normal</option><option>low</option><option>high</option></select>
              <input name="due_at" aria-label="Task due date" className={`${field} app-date-time`} type="datetime-local" />
              <input name="timezone" aria-label="Task timezone" className={field} defaultValue={timezone} />
              <button className={primary} disabled={busy}><Plus size={15} />Add task</button>
            </form>
            <ul className="divide-y divide-border">{tasks.filter((task) => taskStatusFilter === 'all' || task.status === taskStatusFilter).map((task) => <li key={task.id} className="py-3">
              {editingTask === task.id ? <form className="grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveTask(event, task.id)}>
                <input name="title" aria-label="Edit task title" className={field} defaultValue={task.title} required />
                <input name="description" aria-label="Edit task description" className={field} defaultValue={task.description} />
                <select name="project_id" aria-label="Edit task project" className={`${field} app-select`} defaultValue={task.project_id ?? ''}><option value="">No project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}</select>
                <select name="priority" aria-label="Edit task priority" className={`${field} app-select`} defaultValue={task.priority}><option>low</option><option>normal</option><option>high</option></select>
                <input name="due_at" aria-label="Edit task due date" className={`${field} app-date-time`} type="datetime-local" defaultValue={localDateTime(task.due_at)} />
                <input name="timezone" aria-label="Edit task timezone" className={field} defaultValue={task.timezone} />
                <span className="flex gap-2"><button className={primary} disabled={busy}><Check size={15} />Save</button><button type="button" className={secondary} onClick={() => setEditingTask(null)}>Cancel</button></span>
              </form> : <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h3 className="font-medium">{task.title}</h3><p className="text-sm text-fg-muted">{task.status} · {task.priority}{task.due_at ? ` · due ${timestamp(task.due_at)} (${task.timezone})` : ''}</p>{task.description && <p className="mt-1 text-sm">{task.description}</p>}{task.project_id && <p className="text-xs text-fg-muted">Project: {projects.find((project) => project.id === task.project_id)?.title ?? 'Linked project'}</p>}</div>
                <span className="flex gap-1">{task.status === 'pending' && <button className={secondary} aria-label="Start task" title="Start task" disabled={busy} onClick={() => void act(`tasks/${task.id}/start`, { method: 'POST' })}><Play size={15} /></button>}{task.status !== 'completed' && task.status !== 'cancelled' && <><button className={secondary} aria-label="Complete task" title="Complete task" disabled={busy} onClick={() => void act(`tasks/${task.id}/complete`, { method: 'POST' })}><Check size={15} /></button><button className={danger} aria-label="Cancel task" title="Cancel task" disabled={busy} onClick={() => { if (window.confirm(`Cancel “${task.title}”?`)) void act(`tasks/${task.id}/cancel`, { method: 'POST' }); }}><X size={15} /></button></>}<button className={secondary} aria-label="Edit task" title="Edit task" onClick={() => setEditingTask(task.id)}><Pencil size={15} /></button></span>
              </div>}
            </li>)}</ul>
            {!tasks.length && <p className="text-sm text-fg-muted">No tasks yet.</p>}
          </section>}

          {section === 'reminders' && <section>
            <h2 className="mb-3 font-semibold">Reminders and delivery jobs</h2>
            <form className="mb-4 grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveReminder(event)}>
              <input name="text" aria-label="Reminder text" className={field} placeholder="Reminder" required />
              <input name="scheduled_at" aria-label="Reminder time" className={`${field} app-date-time`} type="datetime-local" required />
              <input name="timezone" aria-label="Reminder timezone" className={field} defaultValue={timezone} required />
              <select name="task_id" aria-label="Related task" className={`${field} app-select`}><option value="">No related task</option>{tasks.filter((task) => !['completed', 'cancelled'].includes(task.status)).map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select>
              <select name="recurrence" aria-label="Reminder recurrence" className={`${field} app-select`}><option value="none">One time</option><option value="daily">Daily</option><option value="weekly">Weekly</option></select>
              <button className={primary} disabled={busy}><Plus size={15} />Schedule</button>
            </form>
            <ul className="divide-y divide-border">{reminders.map((reminder) => {
              const reminderJobs = jobs.filter((job) => job.reminder_id === reminder.id);
              const latestJob = reminderJobs.sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)))[0];
              return <li key={reminder.id} className="py-3">
                {editingReminder === reminder.id ? <form className="grid gap-2 md:grid-cols-3" onSubmit={(event) => void saveReminder(event, reminder.id)}>
                  <input name="text" aria-label="Edit reminder text" className={field} defaultValue={reminder.text} required />
                  <input name="scheduled_at" aria-label="Edit reminder time" className={`${field} app-date-time`} type="datetime-local" defaultValue={localDateTime(reminder.scheduled_at)} required />
                  <input name="timezone" aria-label="Edit reminder timezone" className={field} defaultValue={reminder.timezone} required />
                  <select name="task_id" aria-label="Edit related task" className={`${field} app-select`} defaultValue={reminder.task_id ?? ''}><option value="">No related task</option>{tasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select>
                  <select name="recurrence" aria-label="Edit recurrence" className={`${field} app-select`} defaultValue={reminder.recurrence}><option value="none">One time</option><option value="daily">Daily</option><option value="weekly">Weekly</option></select>
                  <span className="flex gap-2"><button className={primary} disabled={busy}><Check size={15} />Save</button><button type="button" className={secondary} onClick={() => setEditingReminder(null)}>Cancel</button></span>
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
