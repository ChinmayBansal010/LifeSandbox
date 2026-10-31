/* ─── ProfileMenu: User Account, Preferences, Plan & Usage, and Memory ─── */

import { useState, useRef, useEffect } from 'react';
import {
  User,
  Sun,
  Moon,
  Monitor,
  BrainCircuit,
  CreditCard,
  ChevronRight,
} from 'lucide-react';
import type { ThemePreference } from '../types';

type ProfileMenuProps = {
  theme: ThemePreference;
  onSetTheme: (theme: ThemePreference) => void;
  onOpenLifePanel: () => void;
  compact?: boolean;
};

export default function ProfileMenu({
  theme,
  onSetTheme,
  onOpenLifePanel,
  compact = false,
}: ProfileMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [authNotice, setAuthNotice] = useState(() => {
    if (typeof window === 'undefined') return '';
    const result = new URLSearchParams(window.location.search).get('auth');
    return result === 'success' ? 'Google sign-in complete.' : result === 'denied' ? 'Google sign-in was cancelled.' : '';
  });
  const [account, setAccount] = useState<{ name: string | null; email: string | null; picture?: string | null; authenticated: boolean } | null>(null);
  const [googleConfigured, setGoogleConfigured] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const authResult = params.get('auth');
    if (authResult) {
      params.delete('auth');
      const query = params.toString();
      window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
    }
    void fetch('/api/v1/auth/me', { credentials: 'include' })
      .then(async (response) => response.ok ? response.json() : null)
      .then((value) => setAccount(value))
      .catch(() => setAccount(null));
    void fetch('/api/v1/auth/google/status')
      .then(async (response) => response.ok ? response.json() : null)
      .then((value) => setGoogleConfigured(value?.configured === true))
      .catch(() => setGoogleConfigured(false));
  }, []);

  // Close when clicking outside or pressing Escape
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const handleGoogleSignIn = () => window.location.assign('/api/v1/auth/google/start');

  const handleSignOut = async () => {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
      setAccount(null);
      setAuthNotice('Signed out.');
    } catch {
      setAuthNotice('Could not complete sign-out. Try again.');
    }
  };

  const displayName = account?.name || (account?.authenticated ? 'Google user' : 'Guest User');

  return (
    <div className="relative" ref={menuRef}>
      {/* Profile Trigger Button replacing the old theme toggle icon */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`flex items-center gap-2 rounded-lg text-xs font-medium text-fg-secondary hover:text-fg hover:bg-surface-hover transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
          compact ? 'p-1.5 justify-center' : 'w-full px-2 py-1.5 justify-between'
        } ${isOpen ? 'bg-surface-hover text-fg' : ''}`}
        aria-label="User profile and settings"
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-full overflow-hidden bg-accent text-accent-fg flex items-center justify-center font-semibold text-xs shrink-0 shadow-2xs">
            {account?.picture ? (
              <img src={account.picture} alt={displayName} className="w-full h-full object-cover" />
            ) : (
              (displayName[0] ?? 'L').toUpperCase()
            )}
          </div>
          {!compact && (
            <div className="text-left min-w-0 flex-1 truncate">
                <span className="block text-xs font-semibold text-fg truncate leading-tight">
                {displayName}
              </span>
              <span className="block text-[10px] text-fg-muted truncate leading-tight">
                {account?.authenticated ? 'Authenticated · Neon' : 'Free plan · Local dev'}
              </span>
            </div>
          )}
        </div>
        {!compact && <ChevronRight size={13} className="text-fg-muted shrink-0" />}
      </button>

      {/* Account Popover Menu */}
      {isOpen && (
        <div
          role="menu"
          aria-label="Account options"
          className="absolute z-50 bottom-full mb-2 left-0 w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-border bg-surface p-2 shadow-lg text-fg animate-fade-in text-xs"
        >
          {/* Account Section */}
          <div className="px-2.5 py-2 border-b border-border">
            <div className="flex items-center gap-2.5 mb-2">
              <div className="w-9 h-9 rounded-full overflow-hidden bg-accent/15 text-accent flex items-center justify-center font-bold text-sm shrink-0 border border-accent/25">
                {account?.picture ? (
                  <img src={account.picture} alt={displayName} className="w-full h-full object-cover" />
                ) : (
                  <User size={18} />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-sm text-fg truncate">{displayName}</div>
                <div className="text-[11px] text-fg-muted truncate">{account?.email ?? 'Local development session'}</div>
              </div>
            </div>

            <button
              type="button"
              disabled={!googleConfigured}
              onClick={handleGoogleSignIn}
              className="w-full flex items-center justify-center gap-2 py-1.5 px-3 rounded-lg border border-border bg-bg-secondary hover:bg-surface-hover text-fg font-medium transition-colors text-[11px] mt-1 shadow-2xs disabled:cursor-not-allowed disabled:opacity-50"
            >
              <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>{account?.authenticated ? 'Switch Google account' : 'Sign in with Google'}</span>
            </button>
            {!googleConfigured && <p className="mt-1 text-center text-[10px] text-fg-muted">Google sign-in needs server OAuth setup.</p>}
            {account?.authenticated && <button type="button" role="menuitem" onClick={() => void handleSignOut()} className="mt-1 w-full rounded-lg px-3 py-1.5 text-left text-[11px] text-fg-secondary hover:bg-surface-hover">Sign out</button>}
            {authNotice && (
              <p role="status" className="text-[10px] text-accent mt-1 text-center font-medium animate-fade-in">
                {authNotice}
              </p>
            )}
          </div>

          {/* Theme Preferences */}
          <div className="px-2.5 py-2 border-b border-border">
            <span className="block text-[10px] uppercase font-bold tracking-wider text-fg-muted mb-1.5">
              Theme
            </span>
            <div className="grid grid-cols-3 gap-1 bg-bg-secondary p-1 rounded-lg">
              <button
                type="button"
                onClick={() => onSetTheme('light')}
                className={`flex items-center justify-center gap-1.5 py-1 px-2 rounded-md transition-colors text-xs font-medium ${
                  theme === 'light'
                    ? 'bg-surface text-fg shadow-2xs font-semibold'
                    : 'text-fg-secondary hover:text-fg'
                }`}
              >
                <Sun size={13} />
                <span>Light</span>
              </button>
              <button
                type="button"
                onClick={() => onSetTheme('dark')}
                className={`flex items-center justify-center gap-1.5 py-1 px-2 rounded-md transition-colors text-xs font-medium ${
                  theme === 'dark'
                    ? 'bg-surface text-fg shadow-2xs font-semibold'
                    : 'text-fg-secondary hover:text-fg'
                }`}
              >
                <Moon size={13} />
                <span>Dark</span>
              </button>
              <button
                type="button"
                onClick={() => onSetTheme('system')}
                className={`flex items-center justify-center gap-1.5 py-1 px-2 rounded-md transition-colors text-xs font-medium ${
                  theme === 'system'
                    ? 'bg-surface text-fg shadow-2xs font-semibold'
                    : 'text-fg-secondary hover:text-fg'
                }`}
              >
                <Monitor size={13} />
                <span>System</span>
              </button>
            </div>
          </div>

          {/* Plan & Usage Section */}
          <div className="px-2.5 py-2 border-b border-border">
            <span className="block text-[10px] uppercase font-bold tracking-wider text-fg-muted mb-1">
              Plan & Usage
            </span>
            <div className="flex items-center justify-between py-1">
              <div className="flex items-center gap-1.5 text-fg">
                <CreditCard size={14} className="text-accent" />
                <span className="font-medium text-xs">Free Tier</span>
              </div>
              <span className="text-[10px] bg-accent-muted text-accent font-semibold px-2 py-0.5 rounded-full border border-accent/20">
                Active
              </span>
            </div>
            <div className="mt-1 text-[11px] text-fg-muted">
              <div className="flex justify-between py-0.5">
                <span>Daily requests</span>
                <span className="font-medium text-fg">Active / Unmetered</span>
              </div>
              <div className="flex justify-between py-0.5">
                <span>Storage</span>
                <span className="font-medium text-fg">{account?.authenticated ? 'Neon Postgres' : 'Local SQLite'}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                setAuthNotice('Upgrade plan is a placeholder — all local features are free');
                setTimeout(() => setAuthNotice(''), 3500);
              }}
              className="mt-1.5 w-full text-center text-[11px] text-accent hover:underline py-0.5 font-medium"
            >
              Manage subscription (Placeholder)
            </button>
          </div>

          {/* User Memory Section */}
          <div className="px-1 py-1">
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                onOpenLifePanel();
              }}
              className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-fg hover:bg-surface-hover hover:text-accent transition-colors font-medium text-xs"
            >
              <div className="flex items-center gap-2">
                <BrainCircuit size={15} className="text-accent" />
                <span>Manage Memory</span>
              </div>
              <ChevronRight size={13} className="text-fg-muted" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
