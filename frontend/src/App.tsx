/* ─── App: Root layout and state orchestration ─────────────────────── */

import { useState, useCallback, useEffect } from 'react';
import { useStore, useThemeEffect } from './store';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import LifePanel from './components/LifePanel';
import PluginsPanel from './components/PluginsPanel';
import ProfilePage from './components/ProfilePage';
import AuthModal from './components/AuthModal';
import { Menu, X, MessageSquare, Plus, Blocks } from 'lucide-react';
import type { FileAttachment } from './types';
import { navigate } from './router';

type AccountData = {
  user_id: string;
  name: string | null;
  email: string | null;
  picture?: string | null;
  authenticated: boolean;
};

export default function App() {
  const {
    state,
    activeConversation,
    isPending,
    conversationsLoading,
    conversationsError,
    messagesLoading,
    messagesError,
    deletingId,
    deleteError,
    loadConversations,
    fetchMessages,
    createConversation,
    deleteConversation,
    setActiveConversation,
    renameConversation,
    sendMessage,
    clearDeleteError,
    setTheme,
    saveCustomSkill,
    deleteCustomSkill,
  } = useStore();

  // Authentication state
  const [account, setAccount] = useState<AccountData | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const fetchAccount = useCallback(() => {
    fetch('/api/v1/auth/me', { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        setAccount(data);
        setAuthChecked(true);
      })
      .catch(() => {
        setAccount(null);
        setAuthChecked(true);
      });
  }, []);

  useEffect(() => {
    fetchAccount();
  }, [fetchAccount]);

  const handleSignOut = useCallback(async () => {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
    } finally {
      setAccount(null);
      setProfileOpen(false);
    }
  }, []);

  // Load backend persisted conversations on mount
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // Apply theme
  useThemeEffect(state.theme);

  // Layout & Navigation state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [lifeOpen, setLifeOpen] = useState(false);
  const [pluginsOpen, setPluginsOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [pluginsInitialTab, setPluginsInitialTab] = useState<string | null>(null);
  const [initialPluginPrompt, setInitialPluginPrompt] = useState<string | null>(null);

  const [mem0Enabled, setMem0Enabled] = useState(false);
  const [hostedMemoryAllowed, setHostedMemoryAllowed] = useState(false);
  const [browserUseEnabled, setBrowserUseEnabled] = useState(false);
  const [sttEnabled, setSttEnabled] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [imageUnderstandingEnabled, setImageUnderstandingEnabled] = useState(false);

  const refreshPolicy = useCallback(() => {
    fetch('/api/v1/capabilities', { credentials: 'include', cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((capabilities) => {
        setMem0Enabled(capabilities?.mem0_enabled === true);
        setBrowserUseEnabled(capabilities?.browser_use_enabled === true);
        setSttEnabled(capabilities?.stt_enabled === true);
        setTtsEnabled(capabilities?.tts_enabled === true);
        setImageUnderstandingEnabled(capabilities?.image_understanding_enabled === true);
      })
      .catch(() => {
        setMem0Enabled(false);
        setBrowserUseEnabled(false);
        setSttEnabled(false);
        setTtsEnabled(false);
        setImageUnderstandingEnabled(false);
      });
    fetch('/api/v1/memory-policy', { credentials: 'include', cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((policy) => setHostedMemoryAllowed(policy?.enabled === true && policy?.hosted_memory_allowed === true))
      .catch(() => setHostedMemoryAllowed(false));
  }, []);

  useEffect(() => {
    refreshPolicy();
    window.addEventListener('focus', refreshPolicy);
    return () => window.removeEventListener('focus', refreshPolicy);
  }, [refreshPolicy]);

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
    setLifeOpen(false);
    setPluginsOpen(false);
    setProfileOpen(false);
    setMobileMenuOpen(false);
  }, [createConversation]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      setActiveConversation(id);
      setLifeOpen(false);
      setPluginsOpen(false);
      setProfileOpen(false);
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
    async (userMessage: string, remember: boolean, browse: boolean, attachments: FileAttachment[]) => {
      if (!activeConversation) return '{}';
      return sendMessage(activeConversation.id, userMessage, remember, browse, attachments);
    },
    [activeConversation, sendMessage]
  );

  const handleOpenPlugins = useCallback((tab?: string) => {
    setPluginsInitialTab(tab || null);
    setPluginsOpen(true);
    setLifeOpen(false);
    setProfileOpen(false);
    setMobileMenuOpen(false);
  }, []);

  const handleClosePlugins = useCallback(() => {
    setPluginsOpen(false);
    setPluginsInitialTab(null);
  }, []);

  const handleOpenProfile = useCallback(() => {
    setProfileOpen(true);
    setLifeOpen(false);
    setPluginsOpen(false);
    setMobileMenuOpen(false);
  }, []);

  const handleCloseProfile = useCallback(() => {
    setProfileOpen(false);
  }, []);

  const handleUsePluginInChat = useCallback(
    (prompt: string) => {
      setInitialPluginPrompt(prompt);
      setPluginsOpen(false);
      setLifeOpen(false);
      setProfileOpen(false);
      setMobileMenuOpen(false);
      if (!activeConversation) {
        createConversation();
      }
    },
    [activeConversation, createConversation]
  );

  const isUserAuthenticated = Boolean(account?.authenticated);
  const isGateActive = authChecked && !isUserAuthenticated;

  return (
    <>
      {/* ─── Mandatory Sign-In Gate Popup ──────────────────── */}
      <AuthModal isOpen={isGateActive} />

      <div className={`h-dvh flex overflow-hidden bg-bg ${isGateActive ? 'pointer-events-none select-none filter blur-[1.5px]' : ''}`}>
        {/* ─── Mobile header ────────────────────────────────── */}
        {isMobile && (
          <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 py-2.5 bg-bg border-b border-border">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-1.5 rounded-md hover:bg-surface-hover text-fg-muted cursor-pointer"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span className="flex items-center gap-2 text-sm font-semibold text-fg">
              <img src="/lifesandbox-icon.svg" alt="" aria-hidden="true" className="h-6 w-6 rounded-md" />
              LifeSandbox
            </span>
            <div className="w-8" />
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
                onOpenLifePanel={() => {
                  setLifeOpen(true);
                  setPluginsOpen(false);
                  setProfileOpen(false);
                  setMobileMenuOpen(false);
                }}
                onOpenPlugins={handleOpenPlugins}
                onOpenProfile={handleOpenProfile}
                onPromptSignIn={() => fetchAccount()}
                isProfileActive={profileOpen}
                isLifeActive={lifeOpen}
                isPluginsActive={pluginsOpen}
                onSetTheme={setTheme}
                account={account}
                isLoading={conversationsLoading}
                error={conversationsError}
                onRetryLoad={loadConversations}
                deletingId={deletingId}
                deleteError={deleteError}
                onClearDeleteError={clearDeleteError}
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
            onOpenLifePanel={() => {
              setLifeOpen(true);
              setPluginsOpen(false);
              setProfileOpen(false);
            }}
            onOpenPlugins={handleOpenPlugins}
            onOpenProfile={handleOpenProfile}
            onPromptSignIn={() => fetchAccount()}
            isProfileActive={profileOpen}
            isLifeActive={lifeOpen}
            isPluginsActive={pluginsOpen}
            onSetTheme={setTheme}
            account={account}
            isLoading={conversationsLoading}
            error={conversationsError}
            onRetryLoad={loadConversations}
            deletingId={deletingId}
            deleteError={deleteError}
            onClearDeleteError={clearDeleteError}
          />
        )}

        {/* ─── Main workspace ───────────────────────────────── */}
        <main className={`flex-1 flex overflow-hidden ${isMobile ? 'pt-11' : ''}`}>
          {profileOpen ? (
            <ProfilePage
              account={account}
              theme={state.theme}
              onSetTheme={setTheme}
              onClose={handleCloseProfile}
              onSignOut={handleSignOut}
            />
          ) : pluginsOpen ? (
            <div className="flex-1 flex flex-col min-w-0">
              <PluginsPanel
                onClose={handleClosePlugins}
                onUseInChat={handleUsePluginInChat}
                customSkills={state.customSkills || {}}
                onSaveCustomSkill={saveCustomSkill}
                onDeleteCustomSkill={deleteCustomSkill}
                initialTab={pluginsInitialTab as any}
              />
            </div>
          ) : lifeOpen ? (
            <LifePanel
              onClose={() => {
                setLifeOpen(false);
                refreshPolicy();
              }}
            />
          ) : activeConversation ? (
            <div className="flex-1 flex flex-col min-w-0">
              <Chat
                key={activeConversation.id}
                conversation={activeConversation}
                onSendMessage={handleSendMessage}
                onRenameConversation={renameConversation}
                onOpenPlugins={handleOpenPlugins}
                onOpenCustomSkills={() => handleOpenPlugins('custom-skills')}
                customSkills={state.customSkills || {}}
                onSaveCustomSkill={saveCustomSkill}
                initialPrompt={initialPluginPrompt}
                onClearInitialPrompt={() => setInitialPluginPrompt(null)}
                isPending={isPending}
                mem0Enabled={mem0Enabled}
                hostedMemoryAllowed={hostedMemoryAllowed}
                browserUseEnabled={browserUseEnabled}
                sttEnabled={sttEnabled}
                ttsEnabled={ttsEnabled}
                imageUnderstandingEnabled={imageUnderstandingEnabled}
                theme={state.theme}
                isMessagesLoading={Boolean(activeConversation && messagesLoading[activeConversation.id])}
                messagesError={activeConversation ? messagesError[activeConversation.id] : null}
                onRetryLoadMessages={() => activeConversation && fetchMessages(activeConversation.id, true)}
              />
            </div>
          ) : (
            /* Welcome state */
            <div className="flex-1 flex flex-col items-center justify-center text-center px-6 max-w-4xl mx-auto w-full animate-fade-in">
              <div className="w-16 h-16 rounded-2xl bg-accent-muted border border-accent/20 flex items-center justify-center mb-5 shadow-sm animate-scale-in">
                <MessageSquare size={30} className="text-accent" />
              </div>
              <h1 className="text-3xl font-bold text-fg mb-3 tracking-tight">
                Life Sandbox
              </h1>
              <p className="text-sm text-fg-secondary max-w-lg leading-relaxed mb-8">
                A decision support and research assistant. Weigh multi-criteria scenarios, browse grounded web facts, and manage your long-term memories.
              </p>

              <div className="flex items-center gap-3 mb-10 flex-wrap justify-center">
                <button
                  onClick={handleCreateConversation}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-accent text-accent-fg text-sm font-semibold hover:bg-accent-hover transition-all duration-150 shadow-xs hover:shadow-sm active:scale-95 cursor-pointer"
                >
                  <Plus size={16} />
                  <span>Start a new chat</span>
                </button>
                <button
                  onClick={() => handleOpenPlugins()}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-border bg-surface hover:bg-surface-hover text-fg text-sm font-semibold transition-all duration-150 shadow-2xs hover:shadow-xs active:scale-95 cursor-pointer"
                >
                  <Blocks size={16} className="text-accent" />
                  <span>Explore Plugins</span>
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 w-full text-left">
                <div className="p-4 rounded-xl bg-surface border border-border shadow-2xs transition-all hover:-translate-y-0.5 hover:border-accent/40">
                  <span className="text-xs font-semibold text-fg block mb-1">Decision Modeling</span>
                  <p className="text-[11px] text-fg-muted leading-relaxed">
                    Evaluate trade-offs between competing priorities, time constraints, and budgets.
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-surface border border-border shadow-2xs transition-all hover:-translate-y-0.5 hover:border-accent/40">
                  <span className="text-xs font-semibold text-fg block mb-1">Verified Research</span>
                  <p className="text-[11px] text-fg-muted leading-relaxed">
                    Incorporate grounded facts and web evidence with cited public sources.
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-surface border border-border shadow-2xs transition-all hover:-translate-y-0.5 hover:border-accent/40">
                  <span className="text-xs font-semibold text-fg block mb-1">Durable Neon Storage</span>
                  <p className="text-[11px] text-fg-muted leading-relaxed">
                    Durable Google-authenticated memories and projects backed by PostgreSQL.
                  </p>
                </div>
              </div>
              <p className="mt-7 text-xs text-fg-muted">
                By using Life Sandbox, you agree to our{' '}
                <button type="button" onClick={() => navigate('/terms')} className="font-semibold text-accent hover:underline cursor-pointer">Terms</button>{' '}
                and acknowledge our{' '}
                <button type="button" onClick={() => navigate('/privacy')} className="font-semibold text-accent hover:underline cursor-pointer">Privacy Policy</button>.
              </p>
            </div>
          )}
        </main>
      </div>
    </>
  );
}
