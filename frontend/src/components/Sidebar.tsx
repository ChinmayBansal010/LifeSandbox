/* ─── Sidebar: Conversation navigation ─────────────────────────────── */

import { useState } from 'react';
import {
  Plus,
  MessageSquare,
  Search,
  Sun,
  Moon,
  Monitor,
  PanelLeftClose,
  PanelLeftOpen,
  Trash2,
} from 'lucide-react';
import type { Scenario, ThemePreference } from '../types';
import { truncate } from '../graph-utils';

type SidebarProps = {
  scenarios: Record<string, Scenario>;
  activeScenarioId: string | null;
  theme: ThemePreference;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onCreateScenario: () => void;
  onSelectScenario: (id: string) => void;
  onDeleteScenario: (id: string) => void;
  onSetTheme: (theme: ThemePreference) => void;
};

export default function Sidebar({
  scenarios,
  activeScenarioId,
  theme,
  collapsed,
  onToggleCollapse,
  onCreateScenario,
  onSelectScenario,
  onDeleteScenario,
  onSetTheme,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const scenarioList = Object.values(scenarios).sort(
    (a, b) => b.updatedAt - a.updatedAt
  );

  const filtered = searchQuery
    ? scenarioList.filter((s) =>
        s.title.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : scenarioList;

  const themeIcons: Record<ThemePreference, typeof Sun> = {
    light: Sun,
    dark: Moon,
    system: Monitor,
  };
  const nextTheme: Record<ThemePreference, ThemePreference> = {
    light: 'dark',
    dark: 'system',
    system: 'light',
  };
  const ThemeIcon = themeIcons[theme];

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
          onClick={onCreateScenario}
          className="mt-4 p-1.5 rounded-md hover:bg-accent-muted text-accent transition-colors"
          aria-label="New scenario"
        >
          <Plus size={18} />
        </button>
        <div className="mt-auto">
          <button
            onClick={() => onSetTheme(nextTheme[theme])}
            className="p-1.5 rounded-md hover:bg-surface-hover text-fg-muted hover:text-fg transition-colors"
            aria-label={`Switch to ${nextTheme[theme]} theme`}
          >
            <ThemeIcon size={16} />
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="flex flex-col border-r border-border bg-bg-secondary w-64 shrink-0 animate-slide-in-left">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-accent flex items-center justify-center">
            <MessageSquare size={14} className="text-accent-fg" />
          </div>
          <span className="text-sm font-semibold text-fg tracking-tight">
            Life Sandbox
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

      {/* New scenario */}
      <div className="px-3 py-2">
        <button
          onClick={onCreateScenario}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg border border-border-strong hover:bg-surface-hover text-fg-secondary hover:text-fg transition-colors"
        >
          <Plus size={15} />
          New scenario
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
            placeholder="Search…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md bg-surface border border-border text-fg placeholder:text-fg-muted focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition-colors"
          />
        </div>
      </div>

      {/* Scenario list */}
      <nav className="flex-1 overflow-y-auto px-2 py-1" aria-label="Scenarios">
        {filtered.length === 0 && (
          <p className="px-3 py-4 text-xs text-fg-muted text-center">
            {searchQuery ? 'No matching scenarios' : 'No scenarios yet'}
          </p>
        )}
        {filtered.map((scenario) => {
          const isActive = scenario.id === activeScenarioId;
          return (
            <div
              key={scenario.id}
              className="group relative"
            >
              <button
                onClick={() => onSelectScenario(scenario.id)}
                className={`w-full text-left flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-accent-muted text-accent font-medium'
                    : 'text-fg-secondary hover:bg-surface-hover hover:text-fg'
                }`}
                aria-current={isActive ? 'page' : undefined}
              >
                <MessageSquare size={14} className="shrink-0 opacity-60" />
                <span className="truncate">
                  {truncate(scenario.title, 30)}
                </span>
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteScenario(scenario.id);
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-error/10 text-fg-muted hover:text-error transition-all"
                aria-label={`Delete ${scenario.title}`}
              >
                <Trash2 size={13} />
              </button>
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-border flex items-center justify-between">
        <button
          onClick={() => onSetTheme(nextTheme[theme])}
          className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-fg-muted hover:text-fg hover:bg-surface-hover transition-colors"
          aria-label={`Switch to ${nextTheme[theme]} theme`}
        >
          <ThemeIcon size={14} />
          <span className="capitalize">{theme}</span>
        </button>
      </div>
    </aside>
  );
}
