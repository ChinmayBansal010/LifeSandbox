/* ─── Sidebar: Chat Conversations Navigation & Admin Link ─────────── */

import { useState } from 'react';
import {
  Plus,
  MessageSquare,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
  Trash2,
  NotebookTabs,
  Blocks,
  Loader2,
  RefreshCw,
  AlertCircle,
  X,
} from 'lucide-react';
import type { Conversation, ThemePreference } from '../types';
import { truncate } from '../graph-utils';
import { navigate } from '../router';
import ProfileMenu from './ProfileMenu';

type SidebarProps = {
  conversations: Record<string, Conversation>;
  activeConversationId: string | null;
  theme: ThemePreference;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onCreateConversation: () => void;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onOpenLifePanel: () => void;
  onOpenPlugins: () => void;
  onOpenProfile?: () => void;
  onPromptSignIn?: () => void;
  isProfileActive?: boolean;
  onOpenAdminPanel?: () => void;
  isAdminActive?: boolean;
  isLifeActive?: boolean;
  isPluginsActive?: boolean;
  onSetTheme: (theme: ThemePreference) => void;
  account?: { name: string | null; email: string | null; picture?: string | null; authenticated: boolean } | null;
  isLoading?: boolean;
  error?: string | null;
  onRetryLoad?: () => void;
  deletingId?: string | null;
  deleteError?: string | null;
  onClearDeleteError?: () => void;
};

export default function Sidebar({
  conversations,
  activeConversationId,
  collapsed,
  onToggleCollapse,
  onCreateConversation,
  onSelectConversation,
  onDeleteConversation,
  onOpenLifePanel,
  onOpenPlugins,
  onOpenProfile,
  onPromptSignIn,
  isProfileActive = false,
  isLifeActive = false,
  isPluginsActive = false,
  account,
  isLoading = false,
  error = null,
  onRetryLoad,
  deletingId = null,
  deleteError = null,
  onClearDeleteError,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const conversationList = Object.values(conversations).sort(
    (a, b) => b.updatedAt - a.updatedAt
  );

  const filtered = searchQuery
    ? conversationList.filter((s) =>
        s.title.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : conversationList;

  if (collapsed) {
    return (
      <aside className="flex flex-col items-center py-4 px-2 border-r border-border bg-bg-secondary w-12 shrink-0">
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-md hover:bg-surface-hover text-fg-muted hover:text-fg transition-colors"
          aria-label="Expand sidebar"
        >
          <PanelLeftOpen size={18} />
        </button>
        <button
          onClick={onCreateConversation}
          className="mt-4 p-1.5 rounded-md hover:bg-accent-muted text-accent transition-colors"
          aria-label="New chat"
        >
          <Plus size={18} />
        </button>
        <button
          onClick={onOpenPlugins}
          className={`mt-3 p-1.5 rounded-md transition-colors ${
            isPluginsActive
              ? 'bg-accent text-accent-fg'
              : 'text-fg-muted hover:bg-surface-hover hover:text-fg'
          }`}
          aria-label="Plugins and tools"
          title="Plugins & Tools"
        >
          <Blocks size={18} />
        </button>
        <button
          onClick={onOpenLifePanel}
          className={`mt-3 p-1.5 rounded-md ${isLifeActive ? 'bg-accent text-accent-fg' : 'text-fg-muted hover:bg-surface-hover'}`}
          aria-label="Memory and tasks"
          title="Memory and tasks"
        ><NotebookTabs size={18} /></button>
        <div className="mt-auto">
          <ProfileMenu
            account={account}
            onOpenProfile={onOpenProfile}
            onPromptSignIn={onPromptSignIn}
            isActive={isProfileActive}
            compact
          />
        </div>
      </aside>
    );
  }

  return (
    <aside className="flex flex-col border-r border-border bg-bg-secondary w-64 shrink-0 animate-slide-in-left">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <img src="/lifesandbox-icon.svg" alt="" aria-hidden="true" className="w-7 h-7 rounded-lg shrink-0" />
          <span className="text-sm font-semibold text-fg tracking-tight">
            LifeSandbox
          </span>
        </div>
        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-md hover:bg-surface-hover text-fg-muted hover:text-fg transition-colors"
          aria-label="Collapse sidebar"
        >
          <PanelLeftClose size={16} />
        </button>
      </div>

      {/* New chat */}
      <div className="px-3 py-2">
        <button
          onClick={onCreateConversation}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg border border-border-strong hover:bg-surface-hover text-fg-secondary hover:text-fg transition-colors"
        >
          <Plus size={15} />
          New chat
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-muted"
          />
          <input
            type="text"
            placeholder="Search chats…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md bg-surface border border-border text-fg placeholder:text-fg-muted focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition-colors"
          />
        </div>
      </div>

      {/* Delete error notification banner */}
      {deleteError && (
        <div className="mx-3 mb-2 p-2 rounded-lg bg-error/15 border border-error/30 text-xs flex items-start justify-between gap-1.5 animate-fade-in">
          <div className="flex items-start gap-1.5 text-error">
            <AlertCircle size={14} className="shrink-0 mt-0.5" />
            <span className="leading-tight">{deleteError}</span>
          </div>
          {onClearDeleteError && (
            <button
              onClick={onClearDeleteError}
              className="p-0.5 rounded hover:bg-error/20 text-error shrink-0"
              aria-label="Dismiss error"
            >
              <X size={12} />
            </button>
          )}
        </div>
      )}

      {/* Chat list */}
      <nav className="flex-1 overflow-y-auto px-2 py-1" aria-label="Conversations">
        {isLoading && conversationList.length === 0 && (
          <div className="flex items-center justify-center py-6 gap-2 text-xs text-fg-muted" role="status">
            <Loader2 size={14} className="animate-spin text-accent" />
            <span>Loading chats…</span>
          </div>
        )}

        {error && (
          <div className="mx-2 my-2 p-2.5 rounded-lg bg-error/10 border border-error/20 text-xs">
            <p className="text-error font-medium">Failed to load chats</p>
            <p className="text-[11px] text-fg-muted mt-0.5 line-clamp-2">{error}</p>
            {onRetryLoad && (
              <button
                onClick={onRetryLoad}
                className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-semibold text-accent hover:underline"
              >
                <RefreshCw size={11} /> Retry
              </button>
            )}
          </div>
        )}

        {!isLoading && filtered.length === 0 && !error && (
          <p className="px-3 py-4 text-xs text-fg-muted text-center">
            {searchQuery ? 'No matching chats' : 'No chats yet'}
          </p>
        )}

        {filtered.map((conv) => {
          const isActive = conv.id === activeConversationId;
          const isDeleting = deletingId === conv.id;
          return (
            <div key={conv.id} className="group relative">
              <button
                onClick={() => onSelectConversation(conv.id)}
                className={`w-full text-left flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-accent-muted text-accent font-medium'
                    : 'text-fg-secondary hover:bg-surface-hover hover:text-fg'
                }`}
                aria-current={isActive ? 'page' : undefined}
              >
                <MessageSquare size={14} className="shrink-0 opacity-60" />
                <span className="truncate flex-1">
                  {truncate(conv.title, 22)}
                </span>
                {conv.isLocalOnly && (
                  <span
                    className="text-[9px] font-mono px-1 py-0.2 rounded bg-surface border border-border text-fg-muted shrink-0"
                    title="Saved in browser localStorage"
                  >
                    Local
                  </span>
                )}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isDeleting) onDeleteConversation(conv.id);
                }}
                disabled={isDeleting}
                className={`absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded transition-all ${
                  isDeleting
                    ? 'opacity-100 text-fg-muted'
                    : 'opacity-0 group-hover:opacity-100 hover:bg-error/10 text-fg-muted hover:text-error'
                }`}
                aria-label={`Delete ${conv.title}`}
              >
                {isDeleting ? <Loader2 size={13} className="animate-spin text-accent" /> : <Trash2 size={13} />}
              </button>
            </div>
          );
        })}
      </nav>

      {/* Navigation action buttons */}
      <div className="px-3 py-2 border-t border-border space-y-1.5">
        <button
          onClick={onOpenPlugins}
          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-semibold transition-all ${
            isPluginsActive
              ? 'bg-accent text-accent-fg shadow-xs'
              : 'bg-surface hover:bg-surface-hover border border-border text-fg'
          }`}
        >
          <div className="flex items-center gap-2">
            <Blocks size={14} className={isPluginsActive ? 'text-accent-fg' : 'text-accent'} />
            <span>Plugins & Tools</span>
          </div>
          <span
            className={`px-1.5 py-0.5 rounded text-[9px] font-mono ${
              isPluginsActive
                ? 'bg-white/20 text-white'
                : 'bg-accent-muted text-accent'
            }`}
          >
            CATALOGUE
          </span>
        </button>
        <button
          onClick={onOpenLifePanel}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold ${
            isLifeActive
              ? 'bg-accent text-accent-fg'
              : 'border border-border text-fg hover:bg-surface-hover'
          }`}
        >
          <NotebookTabs size={14} />
          <span>Memory & tasks</span>
        </button>
      </div>

      {/* Footer: User Profile Button */}
      <div className="px-3 py-2.5 border-t border-border">
        <ProfileMenu
          account={account}
          onOpenProfile={onOpenProfile}
          onPromptSignIn={onPromptSignIn}
          isActive={isProfileActive}
        />
        <div className="mt-2 flex items-center gap-3 px-1 text-[10px] font-medium text-fg-muted">
          <button type="button" onClick={() => navigate('/privacy')} className="hover:text-fg hover:underline">Privacy</button>
          <button type="button" onClick={() => navigate('/terms')} className="hover:text-fg hover:underline">Terms</button>
        </div>
      </div>
    </aside>
  );
}
