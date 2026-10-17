/* ─── App: Root layout and state orchestration ─────────────────────── */

import { useState, useCallback, useEffect } from 'react';
import { useStore, useThemeEffect } from './store';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import AdminPanel from './components/AdminPanel';
import LifePanel from './components/LifePanel';
import { Menu, X, MessageSquare, Activity, Plus } from 'lucide-react';

export default function App() {
  const {
    state,
    activeConversation,
    isPending,
    createConversation,
    deleteConversation,
    setActiveConversation,
    renameConversation,
    sendMessage,
    setTheme,
  } = useStore();

  // Apply theme
  useThemeEffect(state.theme);

  // Layout & Navigation state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [lifeOpen, setLifeOpen] = useState(false);
  const [adminTraceId, setAdminTraceId] = useState<string | null>(null);

  const [mem0Enabled, setMem0Enabled] = useState(false);
  const [browserUseEnabled, setBrowserUseEnabled] = useState(false);

  useEffect(() => {
    fetch('/api/v1/capabilities')
      .then((response) => (response.ok ? response.json() : null))
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
    typeof window !== 'undefined'
      ? window.matchMedia('(max-width: 768px)').matches
      : false
  );
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const handleCreateConversation = useCallback(() => {
    createConversation();
    setAdminOpen(false);
    setLifeOpen(false);
    setMobileMenuOpen(false);
  }, [createConversation]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      setActiveConversation(id);
      setAdminOpen(false);
      setLifeOpen(false);
      setMobileMenuOpen(false);
    },
    [setActiveConversation]
  );

  const handleDeleteConversation = useCallback(
    (id: string) => {
      deleteConversation(id);
      setMobileMenuOpen(false);
    },
    [deleteConversation]
  );

  const handleSendMessage = useCallback(
    async (userMessage: string, remember: boolean, browse: boolean) => {
      if (!activeConversation) return '{}';
      return sendMessage(activeConversation.id, userMessage, remember, browse);
    },
    [activeConversation, sendMessage]
  );

  const handleOpenAdmin = useCallback((traceId?: string) => {
    setAdminTraceId(traceId || null);
    setAdminOpen(true);
    setMobileMenuOpen(false);
  }, []);

  const handleCloseAdmin = useCallback(() => {
    setAdminOpen(false);
    setAdminTraceId(null);
  }, []);

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
            onClick={() => handleOpenAdmin()}
            className={`p-1.5 rounded-md transition-colors ${
              adminOpen ? 'bg-accent text-accent-fg' : 'hover:bg-surface-hover text-fg-muted'
            }`}
            aria-label="Toggle admin panel"
          >
            <Activity size={18} />
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
              conversations={state.conversations}
              activeConversationId={state.activeConversationId}
              theme={state.theme}
              collapsed={false}
              onToggleCollapse={() => setMobileMenuOpen(false)}
              onCreateConversation={handleCreateConversation}
              onSelectConversation={handleSelectConversation}
              onDeleteConversation={handleDeleteConversation}
              onOpenAdminPanel={() => handleOpenAdmin()}
              onOpenLifePanel={() => { setLifeOpen(true); setAdminOpen(false); setMobileMenuOpen(false); }}
              isAdminActive={adminOpen}
              isLifeActive={lifeOpen}
              onSetTheme={setTheme}
            />
          </div>
        </>
      )}

      {/* ─── Desktop sidebar ──────────────────────────────── */}
      {!isMobile && (
        <Sidebar
          conversations={state.conversations}
          activeConversationId={state.activeConversationId}
          theme={state.theme}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onCreateConversation={handleCreateConversation}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          onOpenAdminPanel={() => handleOpenAdmin()}
          onOpenLifePanel={() => { setLifeOpen(true); setAdminOpen(false); }}
          isAdminActive={adminOpen}
          isLifeActive={lifeOpen}
          onSetTheme={setTheme}
        />
      )}

      {/* ─── Main workspace ───────────────────────────────── */}
      <main className={`flex-1 flex overflow-hidden ${isMobile ? 'pt-11' : ''}`}>
        {lifeOpen ? (
          <LifePanel onClose={() => setLifeOpen(false)} />
        ) : adminOpen ? (
          <div className="flex-1 flex flex-col min-w-0">
            <AdminPanel
              onClose={handleCloseAdmin}
              initialSelectedTraceId={adminTraceId}
            />
          </div>
        ) : activeConversation ? (
          <div className="flex-1 flex flex-col min-w-0">
            <Chat
              key={activeConversation.id}
              conversation={activeConversation}
              onSendMessage={handleSendMessage}
              onRenameConversation={renameConversation}
              onOpenAdminPanel={handleOpenAdmin}
              isPending={isPending}
              mem0Enabled={mem0Enabled}
              browserUseEnabled={browserUseEnabled}
            />
          </div>
        ) : (
          /* Welcome state */
          <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
            <div className="w-16 h-16 rounded-2xl bg-accent-muted flex items-center justify-center mb-6">
              <MessageSquare size={28} className="text-accent" />
            </div>
            <h1 className="text-2xl font-bold text-fg mb-3 tracking-tight">
              Life Sandbox
            </h1>
            <p className="text-sm text-fg-secondary max-w-md leading-relaxed mb-6">
              A decision support and research assistant. Ask complex questions, weigh multi-criteria scenarios, and monitor all tool execution traces in real time.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={handleCreateConversation}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent text-accent-fg text-sm font-medium hover:bg-accent-hover transition-colors shadow-xs"
              >
                <Plus size={16} />
                <span>Start a new chat</span>
              </button>
              <button
                onClick={() => handleOpenAdmin()}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border bg-surface hover:bg-surface-hover text-fg text-sm font-medium transition-colors"
              >
                <Activity size={16} className="text-accent" />
                <span>Open Admin Panel</span>
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
