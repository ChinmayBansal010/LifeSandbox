import { useCallback, useEffect, useState } from 'react';

type Item = Record<string, any>;

async function request(path: string, init?: RequestInit) {
  const response = await fetch(`/api/v1/${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.detail?.message ?? 'Could not complete the request.');
  }
  return response.status === 204 ? null : response.json();
}

export default function LifePanel({ onClose }: { onClose: () => void }) {
  const [memories, setMemories] = useState<Item[]>([]);
  const [tasks, setTasks] = useState<Item[]>([]);
  const [reminders, setReminders] = useState<Item[]>([]);
  const [approvals, setApprovals] = useState<Item[]>([]);
  const [projects, setProjects] = useState<Item[]>([]);
  const [notifications, setNotifications] = useState<Item[]>([]);
  const [policy, setPolicy] = useState<Item | null>(null);
  const [memoryText, setMemoryText] = useState('');
  const [taskText, setTaskText] = useState('');
  const [reminderText, setReminderText] = useState('');
  const [reminderTime, setReminderTime] = useState('');
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      const [m, t, r, a, p, n, mp] = await Promise.all([
        request('memories'), request('tasks'), request('reminders'), request('approvals'),
        request('projects'), request('notifications'), request('memory-policy'),
      ]);
      setMemories(m.items); setTasks(t.items); setReminders(r.items); setApprovals(a.items);
      setProjects(p.items); setNotifications(n.items); setPolicy(mp);
      setError('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load your data.'); }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  async function act(path: string, init?: RequestInit) {
    try { await request(path, init); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Request failed.'); }
  }

  const card = 'rounded-xl border border-border bg-surface p-4';
  const input = 'min-w-0 rounded-lg border border-border bg-bg px-3 py-2 text-sm text-fg';
  const button = 'rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-fg disabled:opacity-50';

  return <section className="flex h-full min-w-0 flex-1 flex-col overflow-y-auto bg-bg p-5 text-fg">
    <header className="mb-5 flex items-center justify-between">
      <div><h1 className="text-xl font-semibold">Memory & follow-through</h1><p className="text-sm text-fg-muted">Manage saved facts, commitments, reminders, and pending approvals.</p></div>
      <button className={input} onClick={onClose}>Back to chat</button>
    </header>
    {error && <p role="alert" className="mb-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <div className="grid gap-4 lg:grid-cols-2">
      <section className={card}>
        <h2 className="mb-3 font-semibold">Memory policy</h2>
        {policy && <div className="space-y-3 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={policy.enabled} onChange={(e) => void act('memory-policy', { method: 'PUT', body: JSON.stringify({ ...policy, enabled: e.target.checked }) })} /> Allow local memory recall</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={policy.hosted_memory_allowed} onChange={(e) => void act('memory-policy', { method: 'PUT', body: JSON.stringify({ ...policy, hosted_memory_allowed: e.target.checked }) })} /> Allow opted-in exchanges to use hosted Mem0</label>
          <p className="text-xs text-fg-muted">Sensitive categories are excluded from automatic memory saving. Saving a local memory still requires your explicit action.</p>
        </div>}
      </section>
      <section className={card}>
        <h2 className="mb-3 font-semibold">Memory</h2>
        <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (memoryText.trim()) void act('memories', { method: 'POST', body: JSON.stringify({ content: memoryText, category: 'preference', consent: true }) }).then(() => setMemoryText('')); }}>
          <input aria-label="Memory to save" className={`${input} flex-1`} value={memoryText} onChange={(e) => setMemoryText(e.target.value)} placeholder="A preference to remember" />
          <button className={button}>Save</button>
        </form>
        <ul className="space-y-2">{memories.map((m) => <li key={m.id} className="flex items-start justify-between gap-3 rounded-lg bg-bg p-3 text-sm"><span><span className="mr-2 rounded bg-accent-muted px-1.5 py-0.5 text-xs">{m.category}</span>{m.content}<span className="mt-1 block text-xs text-fg-muted">{m.source} · {new Date(m.created_at).toLocaleDateString()}</span></span><button className="text-red-700" onClick={() => void act(`memories/${m.id}`, { method: 'DELETE' })}>Delete</button></li>)}</ul>
        {!memories.length && <p className="text-sm text-fg-muted">No saved memories.</p>}
      </section>
      <section className={card}>
        <h2 className="mb-3 font-semibold">Projects</h2>
        <form className="mb-4 grid gap-2 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); const data = new FormData(e.currentTarget); const title = String(data.get('project')).trim(); if (title) void act('projects', { method: 'POST', body: JSON.stringify({ title, next_action: String(data.get('next_action') ?? '') }) }); e.currentTarget.reset(); }}>
          <input name="project" aria-label="Project name" className={input} placeholder="Project name" />
          <input name="next_action" aria-label="Project next action" className={input} placeholder="Next action" />
          <button className={button}>Add project</button>
        </form>
        <ul className="space-y-2">{projects.map((p) => <li key={p.id} className="rounded-lg bg-bg p-3 text-sm"><strong>{p.title}</strong><span className="ml-2 text-xs text-fg-muted">{p.status}</span>{p.next_action && <p className="mt-1 text-fg-muted">Next: {p.next_action}</p>}</li>)}</ul>
        {!projects.length && <p className="text-sm text-fg-muted">No projects yet.</p>}
      </section>
      <section className={card}>
        <h2 className="mb-3 font-semibold">Tasks</h2>
        <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (taskText.trim()) void act('tasks', { method: 'POST', body: JSON.stringify({ title: taskText }) }).then(() => setTaskText('')); }}>
          <input aria-label="Task title" className={`${input} flex-1`} value={taskText} onChange={(e) => setTaskText(e.target.value)} placeholder="Add a task" /><button className={button}>Add</button>
        </form>
        <ul className="space-y-2">{tasks.map((t) => <li key={t.id} className="flex items-center justify-between gap-3 rounded-lg bg-bg p-3 text-sm"><span>{t.title}<span className="ml-2 text-xs text-fg-muted">{t.status}{t.due_at ? ` · due ${new Date(t.due_at).toLocaleString()}` : ''}</span></span>{t.status !== 'completed' && <button className="text-accent" onClick={() => void act(`tasks/${t.id}/complete`, { method: 'POST' })}>Complete</button>}</li>)}</ul>
        {!tasks.length && <p className="text-sm text-fg-muted">No tasks yet.</p>}
      </section>
      <section className={card}>
        <h2 className="mb-3 font-semibold">Delivered notifications</h2>
        <ul className="space-y-2">{notifications.map((n) => <li key={n.id} className="rounded-lg bg-bg p-3 text-sm">{n.text}<span className="mt-1 block text-xs text-fg-muted">{new Date(n.created_at).toLocaleString()}</span></li>)}</ul>
        {!notifications.length && <p className="text-sm text-fg-muted">No delivered reminders.</p>}
      </section>
      <section className={card}>
        <h2 className="mb-3 font-semibold">Reminders</h2>
        <form className="mb-4 grid gap-2 sm:grid-cols-[1fr_auto_auto]" onSubmit={(e) => { e.preventDefault(); if (reminderText && reminderTime) void act('reminders', { method: 'POST', body: JSON.stringify({ text: reminderText, scheduled_at: new Date(reminderTime).toISOString(), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }) }).then(() => { setReminderText(''); setReminderTime(''); }); }}>
          <input aria-label="Reminder text" className={input} value={reminderText} onChange={(e) => setReminderText(e.target.value)} placeholder="Reminder" />
          <input aria-label="Reminder time" type="datetime-local" className={input} value={reminderTime} onChange={(e) => setReminderTime(e.target.value)} />
          <button className={button}>Schedule</button>
        </form>
        <ul className="space-y-2">{reminders.map((r) => <li key={r.id} className="flex justify-between rounded-lg bg-bg p-3 text-sm"><span>{r.text}<span className="ml-2 text-xs text-fg-muted">{r.status} · {new Date(r.scheduled_at).toLocaleString()}</span></span>{r.status === 'pending' && <button className="text-red-700" onClick={() => void act(`reminders/${r.id}`, { method: 'DELETE' })}>Cancel</button>}</li>)}</ul>
        {!reminders.length && <p className="text-sm text-fg-muted">No reminders scheduled.</p>}
      </section>
      <section className={card}>
        <h2 className="mb-3 font-semibold">Action approvals</h2>
        <ul className="space-y-2">{approvals.filter((a) => a.status === 'pending').map((a) => <li key={a.id} className="flex items-center justify-between gap-3 rounded-lg bg-bg p-3 text-sm"><span>{a.description}<span className="block text-xs text-fg-muted">{a.action}</span></span><span className="flex gap-2"><button className="text-accent" onClick={() => void act(`approvals/${a.id}/approve`, { method: 'POST' })}>Approve</button><button className="text-red-700" onClick={() => void act(`approvals/${a.id}/reject`, { method: 'POST' })}>Reject</button></span></li>)}</ul>
        {!approvals.some((a) => a.status === 'pending') && <p className="text-sm text-fg-muted">No actions are waiting for approval.</p>}
      </section>
    </div>
  </section>;
}
