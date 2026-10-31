/* ─── ProfileMenu / ProfileButton: Trigger for Profile Page or Sign-in ─── */

import { LogIn, ChevronRight } from 'lucide-react';
import type { ThemePreference } from '../types';

type AccountData = {
  name: string | null;
  email: string | null;
  picture?: string | null;
  authenticated: boolean;
};

type ProfileMenuProps = {
  account?: AccountData | null;
  onOpenProfile?: () => void;
  onPromptSignIn?: () => void;
  compact?: boolean;
  isActive?: boolean;
  // Legacy optional props
  theme?: ThemePreference;
  onSetTheme?: (theme: ThemePreference) => void;
  onOpenLifePanel?: () => void;
};

export default function ProfileMenu({
  account,
  onOpenProfile,
  onPromptSignIn,
  compact = false,
  isActive = false,
}: ProfileMenuProps) {
  const planTier = (typeof localStorage !== 'undefined' && localStorage.getItem('life_sandbox_plan_tier') === 'pro')
    ? 'Pro Plan'
    : 'Free Tier';

  const handleClick = () => {
    if (account?.authenticated) {
      onOpenProfile?.();
    } else {
      onPromptSignIn?.();
    }
  };

  const displayName = account?.name || 'Guest User';

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`flex items-center gap-2 rounded-xl text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer ${
        compact ? 'p-1.5 justify-center' : 'w-full px-2.5 py-2 justify-between'
      } ${
        isActive
          ? 'bg-accent-muted text-accent font-semibold border border-accent/30 shadow-2xs'
          : 'text-fg-secondary hover:text-fg hover:bg-surface-hover border border-transparent'
      }`}
      aria-label={account?.authenticated ? 'Open profile settings' : 'Sign in to Life Sandbox'}
      title={account?.authenticated ? `${displayName} · ${planTier}` : 'Click to sign in'}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-7 h-7 rounded-full overflow-hidden bg-accent text-accent-fg flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs border border-accent/20">
          {account?.authenticated && account.picture ? (
            <img src={account.picture} alt="" className="w-full h-full object-cover" />
          ) : account?.authenticated ? (
            (displayName[0] ?? 'U').toUpperCase()
          ) : (
            <LogIn size={13} />
          )}
        </div>

        {!compact && (
          <div className="text-left min-w-0 flex-1 truncate">
            <span className="block text-xs font-semibold text-fg truncate leading-tight">
              {account?.authenticated ? displayName : 'Sign in'}
            </span>
            <span className="block text-[10px] text-fg-muted truncate leading-tight">
              {account?.authenticated ? `${planTier} · Neon` : 'Click to authenticate'}
            </span>
          </div>
        )}
      </div>

      {!compact && (
        <ChevronRight size={13} className="text-fg-muted shrink-0 transition-transform group-hover:translate-x-0.5" />
      )}
    </button>
  );
}
