/* ─── App: Root layout and state orchestration ─────────────────────── */

import { useState, useCallback, useEffect } from 'react';
import { useStore, useThemeEffect } from './store';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import ScenarioGraph from './components/ScenarioGraph';
import { PanelRightClose, PanelRightOpen, Menu, X, GitBranch } from 'lucide-react';

export default function App() {
  const {
    state,
    activeScenario,
    isPending,
    createScenario,
    deleteScenario,
    setActiveScenario,
    renameScenario,
    setActiveNode,
    sendMessage,
    toggleRemember,
    setTheme,
  } = useStore();

  // Apply theme
  useThemeEffect(state.theme);

  // Layout state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [graphOpen, setGraphOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileGraphOpen, setMobileGraphOpen] = useState(false);
  const [mem0Enabled, setMem0Enabled] = useState(false);
  const [browserUseEnabled, setBrowserUseEnabled] = useState(false);

  useEffect(() => {
    fetch('/api/v1/capabilities')
      .then((response) => response.ok ? response.json() : null)
      .then((capabilities) => {
        setMem0Enabled(capabilities?.mem0_enabled === true);
        setBrowserUseEnabled(capabilities?.browser_use_enabled === true);
      })
      .catch(() => {
        setMem0Enabled(false);
        setBrowserUseEnabled(false);
      });
  }, []);

  // Responsive: detect mobile
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(max-width: 768px)').matches : false
  );
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const handleCreateScenario = useCallback(() => {
    createScenario();
    setMobileMenuOpen(false);
    setMobileGraphOpen(false);
  }, [createScenario]);

  const handleSelectScenario = useCallback(
    (id: string) => {
      setActiveScenario(id);
      setMobileMenuOpen(false);
      setMobileGraphOpen(false);
    },
    [setActiveScenario]
  );

  const handleDeleteScenario = useCallback(
    (id: string) => {
      deleteScenario(id);
      setMobileMenuOpen(false);
      setMobileGraphOpen(false);
    },
    [deleteScenario]
  );

  const handleSendMessage = useCallback(
    async (
      userMessage: string,
      parentId: string | null,
      remember: boolean,
      browse: boolean,
    ) => {
      if (!activeScenario) return false;
      return sendMessage(activeScenario.id, userMessage, parentId, remember, browse);
    },
    [activeScenario, sendMessage]
  );

  const handleSelectNode = useCallback(
    (nodeId: string) => {
      if (!activeScenario) return;
      setActiveNode(activeScenario.id, nodeId);
    },
    [activeScenario, setActiveNode]
  );

  return (
    <div className="h-dvh flex overflow-hidden bg-bg">
      {/* ─── Mobile header ────────────────────────────────── */}
      {isMobile && (
        <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 py-2.5 bg-bg border-b border-border">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-md hover:bg-surface-hover text-fg-muted"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="text-sm font-semibold text-fg">Life Sandbox</span>
          <button
            onClick={() => setMobileGraphOpen(!mobileGraphOpen)}
            className="p-1.5 rounded-md hover:bg-surface-hover text-fg-muted"
            aria-label="Toggle graph"
          >
            <GitBranch size={18} />
          </button>
        </header>
      )}

      {/* ─── Mobile sidebar overlay ───────────────────────── */}
      {isMobile && mobileMenuOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/30"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 z-50 w-72 pt-12 animate-slide-in-left">
            <Sidebar
              scenarios={state.scenarios}
              activeScenarioId={state.activeScenarioId}
              theme={state.theme}
              collapsed={false}
              onToggleCollapse={() => setMobileMenuOpen(false)}
              onCreateScenario={handleCreateScenario}
              onSelectScenario={handleSelectScenario}
              onDeleteScenario={handleDeleteScenario}
              onSetTheme={setTheme}
            />
          </div>
        </>
      )}

      {/* ─── Mobile graph overlay ─────────────────────────── */}
      {isMobile && mobileGraphOpen && activeScenario && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/30"
            onClick={() => setMobileGraphOpen(false)}
          />
          <div className="fixed inset-y-0 right-0 z-50 w-80 pt-12 bg-bg-secondary border-l border-border animate-slide-in-right">
            <ScenarioGraph
              scenario={activeScenario}
              nodes={state.nodes}
              onSelectNode={(nodeId) => {
                handleSelectNode(nodeId);
                setMobileGraphOpen(false);
              }}
            />
          </div>
        </>
      )}

      {/* ─── Desktop sidebar ──────────────────────────────── */}
      {!isMobile && (
        <Sidebar
          scenarios={state.scenarios}
          activeScenarioId={state.activeScenarioId}
          theme={state.theme}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onCreateScenario={handleCreateScenario}
          onSelectScenario={handleSelectScenario}
          onDeleteScenario={handleDeleteScenario}
          onSetTheme={setTheme}
        />
      )}

      {/* ─── Main workspace ───────────────────────────────── */}
      <main className={`flex-1 flex overflow-hidden ${isMobile ? 'pt-11' : ''}`}>
        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {activeScenario ? (
            <Chat
              scenario={activeScenario}
              nodes={state.nodes}
              onSendMessage={handleSendMessage}
              onToggleRemember={toggleRemember}
              onSelectNode={handleSelectNode}
              onRenameScenario={renameScenario}
              isPending={isPending}
              mem0Enabled={mem0Enabled}
              browserUseEnabled={browserUseEnabled}
            />
          ) : (
            /* Welcome state */
            <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
              <div className="w-16 h-16 rounded-2xl bg-accent-muted flex items-center justify-center mb-6">
                <GitBranch size={28} className="text-accent" />
              </div>
              <h1 className="text-2xl font-bold text-fg mb-3 tracking-tight">
                Life Sandbox
              </h1>
              <p className="text-sm text-fg-secondary max-w-md leading-relaxed mb-6">
                Explore questions, decisions, and alternate possibilities through branching conversations. Every exchange becomes a node you can revisit and take in a different direction.
              </p>
              <button
                onClick={handleCreateScenario}
                className="px-5 py-2.5 rounded-lg bg-accent text-accent-fg text-sm font-medium hover:bg-accent-hover transition-colors"
              >
                Start your first scenario
              </button>
            </div>
          )}
        </div>

        {/* ─── Desktop graph panel ─────────────────────────── */}
        {!isMobile && activeScenario && (
          <>
            {/* Toggle button */}
            <button
              onClick={() => setGraphOpen(!graphOpen)}
              className="self-start mt-3 p-1.5 rounded-md hover:bg-surface-hover text-fg-muted hover:text-fg transition-colors shrink-0"
              aria-label={graphOpen ? 'Hide timeline' : 'Show timeline'}
            >
              {graphOpen ? (
                <PanelRightClose size={16} />
              ) : (
                <PanelRightOpen size={16} />
              )}
            </button>

            {/* Graph panel */}
            {graphOpen && (
              <div className="w-72 xl:w-80 border-l border-border bg-bg-secondary shrink-0 animate-fade-in">
                <ScenarioGraph
                  scenario={activeScenario}
                  nodes={state.nodes}
                  onSelectNode={handleSelectNode}
                />
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
