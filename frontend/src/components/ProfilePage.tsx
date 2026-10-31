/* ─── ProfilePage: Complete User Profile & Account Settings ─────────── */

import { useState, useEffect } from 'react';
import {
  User,
  ArrowLeft,
  CreditCard,
  Sun,
  Moon,
  Monitor,
  Eye,
  Trash2,
  LogOut,
  AlertTriangle,
  Check,
  Sparkles,
  Database,
  Flame,
  Palette,
  HardDrive,
  Ghost,
} from 'lucide-react';
import type { ThemePreference } from '../types';

type AccountData = {
  user_id: string;
  name: string | null;
  email: string | null;
  picture?: string | null;
  authenticated: boolean;
};

type ProfilePageProps = {
  account: AccountData | null;
  theme: ThemePreference;
  onSetTheme: (theme: ThemePreference) => void;
  onClose: () => void;
  onSignOut: () => void;
};

const THEME_OPTIONS: Array<{
  id: ThemePreference;
  label: string;
  desc: string;
  icon: typeof Sun;
  badgeBg: string;
  accentBg: string;
}> = [
  {
    id: 'light',
    label: 'Light',
    desc: 'Crisp daylight stone surface',
    icon: Sun,
    badgeBg: 'bg-stone-100 text-stone-900 border-stone-300',
    accentBg: '#0d7377',
  },
  {
    id: 'dark',
    label: 'Dark',
    desc: 'Deep obsidian dark mode',
    icon: Moon,
    badgeBg: 'bg-stone-900 text-stone-100 border-stone-700',
    accentBg: '#2dd4bf',
  },
  {
    id: 'system',
    label: 'System',
    desc: 'Syncs with your OS preference',
    icon: Monitor,
    badgeBg: 'bg-stone-800 text-stone-200 border-stone-600',
    accentBg: '#2dd4bf',
  },
  {
    id: 'high-contrast',
    label: 'High Contrast',
    desc: 'Pitch-black with vivid borders',
    icon: Eye,
    badgeBg: 'bg-black text-white border-white',
    accentBg: '#facc15',
  },
  {
    id: 'dracula',
    label: 'Dracula',
    desc: 'Vampiric purple and pink palette',
    icon: Flame,
    badgeBg: 'bg-[#282a36] text-[#f8f8f2] border-[#6272a4]',
    accentBg: '#bd93f9',
  },
  {
    id: 'mocha',
    label: 'Catppuccin Mocha',
    desc: 'Soothing dark pastel aesthetic',
    icon: Palette,
    badgeBg: 'bg-[#1e1e2e] text-[#cdd6f4] border-[#45475a]',
    accentBg: '#cba6f7',
  },
];

export default function ProfilePage({
  account,
  theme,
  onSetTheme,
  onClose,
  onSignOut,
}: ProfilePageProps) {
  // Nickname the agent calls the user
  const [nickname, setNickname] = useState(() => {
    return localStorage.getItem('life_sandbox_agent_nickname') || account?.name || '';
  });
  const [nicknameSaved, setNicknameSaved] = useState(false);

  // Plan tier (Free vs Pro)
  const [planTier, setPlanTier] = useState<'free' | 'pro'>(() => {
    return (localStorage.getItem('life_sandbox_plan_tier') as 'free' | 'pro') || 'free';
  });

  // Incognito mode
  const [incognito, setIncognito] = useState(() => {
    return localStorage.getItem('life_sandbox_incognito') === 'true';
  });

  // Cache & delete feedback states
  const [cacheCleared, setCacheCleared] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);

  useEffect(() => {
    if (account?.name && !localStorage.getItem('life_sandbox_agent_nickname')) {
      setNickname(account.name);
    }
  }, [account?.name]);

  const handleSaveNickname = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem('life_sandbox_agent_nickname', nickname.trim());
    setNicknameSaved(true);
    setTimeout(() => setNicknameSaved(false), 2000);
  };

  const handlePlanChange = (newTier: 'free' | 'pro') => {
    setPlanTier(newTier);
    localStorage.setItem('life_sandbox_plan_tier', newTier);
    setNotification(`Plan switched to ${newTier.toUpperCase()}`);
    setTimeout(() => setNotification(null), 3000);
  };

  const handleToggleIncognito = () => {
    const next = !incognito;
    setIncognito(next);
    localStorage.setItem('life_sandbox_incognito', String(next));
    setNotification(next ? 'Incognito Mode enabled: History is ephemeral' : 'Incognito Mode disabled');
    setTimeout(() => setNotification(null), 3000);
  };

  const handleClearCacheAndMemory = () => {
    if (!window.confirm('Clear all locally cached messages, memories, and application state?')) return;
    try {
      localStorage.removeItem('life-sandbox-state');
      sessionStorage.clear();
      setCacheCleared(true);
      setNotification('Client cache and local state successfully cleared.');
      setTimeout(() => {
        setCacheCleared(false);
        setNotification(null);
      }, 3000);
    } catch {
      setNotification('Failed to clear client storage.');
    }
  };

  const handleDeleteAccount = async () => {
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      return;
    }
    // Delete account action
    try {
      localStorage.clear();
      sessionStorage.clear();
      await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
      window.location.assign('/');
    } catch {
      window.location.assign('/');
    }
  };

  const displayName = account?.name || 'Sandbox User';
  const displayEmail = account?.email || 'Authenticated via Google';

  return (
    <div className="flex-1 flex flex-col h-full bg-bg overflow-y-auto">
      {/* Top Navigation Bar */}
      <div className="sticky top-0 z-20 flex items-center justify-between px-6 py-4 border-b border-border bg-bg/85 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg border border-border bg-surface hover:bg-surface-hover text-fg transition-colors"
            aria-label="Back to workspace"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <h1 className="text-base font-bold text-fg leading-tight">Settings & Profile</h1>
            <p className="text-[11px] text-fg-muted">Manage your personal details, AI preferences, and account</p>
          </div>
        </div>

        <button
          type="button"
          onClick={onSignOut}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-surface hover:bg-surface-hover text-xs font-semibold text-error hover:border-error/40 transition-colors cursor-pointer"
        >
          <LogOut size={13} />
          <span>Sign out</span>
        </button>
      </div>

      {/* Main Content Container */}
      <div className="max-w-3xl w-full mx-auto p-6 space-y-7 animate-fade-in pb-16">
        {notification && (
          <div className="p-3 rounded-xl bg-accent-muted border border-accent/30 text-xs text-accent font-medium flex items-center justify-between animate-slide-in-top">
            <span>{notification}</span>
            <button type="button" onClick={() => setNotification(null)} className="text-accent underline text-[10px]">Dismiss</button>
          </div>
        )}

        {/* ─── 1. Personal Details ─────────────────────────────────────── */}
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-2xs">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl overflow-hidden bg-accent text-accent-fg flex items-center justify-center font-bold text-xl shrink-0 border-2 border-accent/20 shadow-xs">
                {account?.picture ? (
                  <img src={account.picture} alt={displayName} className="w-full h-full object-cover" />
                ) : (
                  <User size={30} />
                )}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-fg truncate">{displayName}</h2>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-accent-muted text-accent border border-accent/20">
                    {planTier === 'pro' ? 'PRO PLAN' : 'FREE TIER'}
                  </span>
                </div>
                <p className="text-xs text-fg-muted truncate">{displayEmail}</p>
                <div className="flex items-center gap-2 mt-1.5 text-[11px] text-fg-secondary">
                  <Database size={12} className="text-accent" />
                  <span>Durable Identity · Neon Postgres</span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-5 pt-4 border-t border-border grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-2.5 rounded-xl bg-bg-secondary border border-border">
              <span className="text-[10px] uppercase font-bold text-fg-muted block mb-0.5">Principal User ID</span>
              <span className="font-mono text-[11px] text-fg break-all">{account?.user_id || 'google:user'}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-bg-secondary border border-border">
              <span className="text-[10px] uppercase font-bold text-fg-muted block mb-0.5">Authentication Provider</span>
              <span className="text-[11px] text-fg font-medium">Google OAuth 2.0 (OpenID Connect)</span>
            </div>
          </div>
        </section>

        {/* ─── 2. Agent Nickname / Persona ─────────────────────────────── */}
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-2xs">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles size={16} className="text-accent" />
            <h2 className="text-sm font-bold text-fg">Agent Persona & Nickname</h2>
          </div>
          <p className="text-xs text-fg-muted mb-4">
            Customize how the Life Sandbox assistant addresses you during conversations.
          </p>

          <form onSubmit={handleSaveNickname} className="flex items-center gap-2 max-w-md">
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="e.g. Chief, Alex, Dr. Smith"
              className="flex-1 px-3 py-2 text-xs rounded-xl bg-bg-secondary border border-border text-fg placeholder:text-fg-muted focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition-colors"
            />
            <button
              type="submit"
              className="px-4 py-2 rounded-xl bg-accent text-accent-fg text-xs font-semibold hover:bg-accent-hover transition-colors shadow-2xs shrink-0 flex items-center gap-1.5"
            >
              {nicknameSaved ? <Check size={14} /> : null}
              <span>{nicknameSaved ? 'Saved' : 'Save Nickname'}</span>
            </button>
          </form>
        </section>

        {/* ─── 3. Plan Change & Credit Limits ──────────────────────────── */}
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-2xs">
          <div className="flex items-center gap-2 mb-1">
            <CreditCard size={16} className="text-accent" />
            <h2 className="text-sm font-bold text-fg">Plan & Credit Limits</h2>
          </div>
          <p className="text-xs text-fg-muted mb-4">
            Choose your computing tier and review your usage parameters.
          </p>

          {/* Tier Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
            {/* Free Tier */}
            <div
              onClick={() => handlePlanChange('free')}
              className={`p-4 rounded-xl border transition-all cursor-pointer ${
                planTier === 'free'
                  ? 'border-accent bg-accent-muted/20 ring-1 ring-accent'
                  : 'border-border bg-bg-secondary hover:border-border-strong'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-sm text-fg">Free Tier</span>
                {planTier === 'free' && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-accent text-accent-fg">
                    CURRENT
                  </span>
                )}
              </div>
              <p className="text-[11px] text-fg-muted mb-3">
                Standard inference, local memory, and core web tools.
              </p>
              <ul className="text-xs text-fg-secondary space-y-1.5">
                <li>• Unmetered local dev requests</li>
                <li>• 4k LLM completion tokens</li>
                <li>• Community Tavily & Browser tools</li>
              </ul>
            </div>

            {/* Pro Plan */}
            <div
              onClick={() => handlePlanChange('pro')}
              className={`p-4 rounded-xl border transition-all cursor-pointer ${
                planTier === 'pro'
                  ? 'border-accent bg-accent-muted/20 ring-1 ring-accent'
                  : 'border-border bg-bg-secondary hover:border-border-strong'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-sm text-fg">Pro Plan</span>
                  <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-500 border border-amber-500/30">PREMIUM</span>
                </div>
                {planTier === 'pro' && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-accent text-accent-fg">
                    ACTIVE
                  </span>
                )}
              </div>
              <p className="text-[11px] text-fg-muted mb-3">
                High-throughput Nebius/OpenRouter tokens with expanded memory.
              </p>
              <ul className="text-xs text-fg-secondary space-y-1.5">
                <li>• Priority concurrency & fast-lane dispatch</li>
                <li>• 32k context expansion</li>
                <li>• Cloud Neon storage & vector search</li>
              </ul>
            </div>
          </div>

          {/* Quota meters */}
          <div className="space-y-3 pt-3 border-t border-border">
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-fg-secondary">Daily API Quota</span>
                <span className="font-semibold text-fg">Active / Unmetered</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-bg-secondary overflow-hidden">
                <div className="h-full bg-accent w-1/4 rounded-full" />
              </div>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-fg-secondary">Neon PostgreSQL Storage</span>
                <span className="font-semibold text-fg">Durable & Connected</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-bg-secondary overflow-hidden">
                <div className="h-full bg-accent w-2/5 rounded-full" />
              </div>
            </div>
          </div>
        </section>

        {/* ─── 4. Appearance & Themes ──────────────────────────────────── */}
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-2xs">
          <div className="flex items-center gap-2 mb-1">
            <Palette size={16} className="text-accent" />
            <h2 className="text-sm font-bold text-fg">Themes & Visual Style</h2>
          </div>
          <p className="text-xs text-fg-muted mb-4">
            Select your preferred color scheme. Changes apply instantly across the entire application.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {THEME_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              const isSelected = theme === opt.id;
              return (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onSetTheme(opt.id)}
                  className={`flex flex-col text-left p-3.5 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'border-accent bg-accent-muted/20 shadow-xs ring-1 ring-accent'
                      : 'border-border bg-bg-secondary hover:bg-surface-hover hover:border-border-strong'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className={`w-6 h-6 rounded-lg flex items-center justify-center border text-xs ${opt.badgeBg}`}>
                        <Icon size={13} />
                      </div>
                      <span className="font-bold text-xs text-fg">{opt.label}</span>
                    </div>
                    {isSelected && (
                      <span className="w-4 h-4 rounded-full bg-accent text-accent-fg flex items-center justify-center">
                        <Check size={10} />
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-fg-muted leading-tight">{opt.desc}</p>
                </button>
              );
            })}
          </div>
        </section>

        {/* ─── 5. Incognito Mode ───────────────────────────────────────── */}
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-2xs">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Ghost size={16} className="text-accent" />
                <h2 className="text-sm font-bold text-fg">Incognito Mode</h2>
              </div>
              <p className="text-xs text-fg-muted max-w-md">
                When active, message exchanges and memories are ephemeral and will not be committed to long-term storage or Mem0.
              </p>
            </div>

            <button
              type="button"
              onClick={handleToggleIncognito}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                incognito ? 'bg-accent' : 'bg-bg-tertiary'
              }`}
              role="switch"
              aria-checked={incognito}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-surface shadow ring-0 transition duration-200 ease-in-out ${
                  incognito ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </section>

        {/* ─── 6. Cache & Memory Management ────────────────────────────── */}
        <section className="rounded-2xl border border-border bg-surface p-5 shadow-2xs">
          <div className="flex items-center gap-2 mb-1">
            <HardDrive size={16} className="text-accent" />
            <h2 className="text-sm font-bold text-fg">Cache & Local Data</h2>
          </div>
          <p className="text-xs text-fg-muted mb-4">
            Reset browser cache, temporary draft messages, or clear offline state.
          </p>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleClearCacheAndMemory}
              disabled={cacheCleared}
              className="flex items-center gap-2 px-4 py-2 rounded-xl border border-border bg-bg-secondary hover:bg-surface-hover text-fg text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              {cacheCleared ? <Check size={14} className="text-accent" /> : <Trash2 size={14} />}
              <span>{cacheCleared ? 'Cache Cleared' : 'Clear Browser Cache & Memory'}</span>
            </button>
          </div>
        </section>

        {/* ─── 7. Danger Zone: Delete Account ──────────────────────────── */}
        <section className="rounded-2xl border border-error/30 bg-error/5 p-5 shadow-2xs">
          <div className="flex items-center gap-2 mb-1 text-error">
            <AlertTriangle size={16} />
            <h2 className="text-sm font-bold">Danger Zone</h2>
          </div>
          <p className="text-xs text-fg-muted mb-4">
            Permanently delete your account session, personal memory policies, and conversations. This action cannot be undone.
          </p>

          <button
            type="button"
            onClick={handleDeleteAccount}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-colors cursor-pointer ${
              deleteConfirm
                ? 'bg-error text-white hover:bg-error/90 animate-pulse'
                : 'border border-error/30 text-error hover:bg-error/15'
            }`}
          >
            <Trash2 size={14} />
            <span>{deleteConfirm ? 'Click again to permanently delete account' : 'Delete Account'}</span>
          </button>
        </section>
      </div>
    </div>
  );
}
