/* ─── Chat interface: Message list + Composer ──────────────────────── */

import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import {
  Send,
  Bookmark,
  BookmarkCheck,
  Copy,
  Check,
  CornerUpLeft,
  Loader2,
  GitBranch,
  Pencil,
  FastForward,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from 'lucide-react';
import type { ScenarioNode, Scenario } from '../types';
import {
  getActiveBranch,
  getRememberedContext,
  getAncestorPath,
  getLeafNode,
  truncate,
} from '../graph-utils';

type ChatProps = {
  scenario: Scenario;
  nodes: Record<string, ScenarioNode>;
  onSendMessage: (userMessage: string, parentId: string | null) => Promise<void>;
  onToggleRemember: (nodeId: string) => void;
  onSelectNode: (nodeId: string) => void;
  onRenameScenario?: (scenarioId: string, title: string) => void;
  isPending: boolean;
};

function MessageBubble({
  node,
  isOnActiveTip,
  onToggleRemember,
  onCopyResponse,
  onTimeTravel,
}: {
  node: ScenarioNode;
  isOnActiveTip: boolean;
  onToggleRemember: (nodeId: string) => void;
  onCopyResponse: (text: string) => void;
  onTimeTravel: (nodeId: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const isLoading = node.assistantMessage === '';

  const handleCopy = () => {
    onCopyResponse(node.assistantMessage);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="animate-fade-in">
      {/* User message */}
      <div className="flex justify-end mb-3">
        <div className="max-w-[75%] lg:max-w-[60%]">
          <div className="bg-accent text-accent-fg px-4 py-2.5 rounded-2xl rounded-br-md text-sm leading-relaxed">
            {node.userMessage}
          </div>
          <div className="flex justify-end mt-1 gap-1">
            <span className="text-[10px] text-fg-muted">
              {new Date(node.createdAt).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
        </div>
      </div>

      {/* Assistant message */}
      <div className="flex justify-start mb-5">
        <div className="max-w-[75%] lg:max-w-[60%]">
          <div className="bg-surface border border-border px-4 py-2.5 rounded-2xl rounded-bl-md text-sm leading-relaxed text-fg shadow-xs">
            {isLoading ? (
              <div className="flex items-center gap-2 text-fg-muted py-1">
                <Loader2 size={14} className="animate-spin text-accent" />
                <span className="text-xs">Exploring possibility…</span>
              </div>
            ) : (
              <div className="whitespace-pre-wrap">{node.assistantMessage}</div>
            )}
          </div>

          {/* Actions row */}
          {!isLoading && (
            <div className="flex items-center gap-1 mt-1.5 flex-wrap">
              <button
                onClick={() => onToggleRemember(node.id)}
                className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  node.rememberEnabled
                    ? 'text-accent bg-accent-muted'
                    : 'text-fg-muted hover:text-fg hover:bg-surface-hover'
                }`}
                title={node.rememberEnabled ? 'Remembered — persists across branches' : 'Remember this exchange for alternate branches'}
                aria-label={node.rememberEnabled ? 'Disable remember' : 'Enable remember'}
              >
                {node.rememberEnabled ? (
                  <BookmarkCheck size={12} className="text-accent" />
                ) : (
                  <Bookmark size={12} />
                )}
                <span>{node.rememberEnabled ? 'Remembered' : 'Remember'}</span>
              </button>

              <button
                onClick={handleCopy}
                className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-fg-muted hover:text-fg hover:bg-surface-hover transition-colors"
                aria-label="Copy response"
              >
                {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>

              {!isOnActiveTip && (
                <button
                  onClick={() => onTimeTravel(node.id)}
                  className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-fg-muted hover:text-accent hover:bg-accent-muted transition-colors"
                  aria-label="Branch from this point"
                >
                  <CornerUpLeft size={12} />
                  <span>Branch here</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Chat({
  scenario,
  nodes,
  onSendMessage,
  onToggleRemember,
  onSelectNode,
  onRenameScenario,
  isPending,
}: ChatProps) {
  const [input, setInput] = useState('');
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(scenario.title);
  const [showRememberedPanel, setShowRememberedPanel] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);

  const conversation = getActiveBranch(scenario, nodes);
  const activeBranchIds = scenario.activeNodeId ? getAncestorPath(scenario.activeNodeId, nodes) : [];
  const rememberedContext = getRememberedContext(activeBranchIds, scenario, nodes);

  const startEditing = () => {
    setTitleDraft(scenario.title);
    setIsEditingTitle(true);
  };

  // Focus title input when editing
  useEffect(() => {
    if (isEditingTitle) {
      titleInputRef.current?.focus();
      titleInputRef.current?.select();
    }
  }, [isEditingTitle]);

  // Auto-scroll on new messages
  const lastMessage = conversation[conversation.length - 1];
  const lastAssistantMessage = lastMessage?.assistantMessage;
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation.length, lastAssistantMessage]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [input]);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || isPending) return;
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    await onSendMessage(msg, scenario.activeNodeId);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSaveTitle = () => {
    setIsEditingTitle(false);
    const trimmed = titleDraft.trim();
    if (trimmed && trimmed !== scenario.title && onRenameScenario) {
      onRenameScenario(scenario.id, trimmed);
    } else {
      setTitleDraft(scenario.title);
    }
  };

  const handleCopyResponse = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  // Check if user is viewing a historical point (has children)
  const isAtHistoricalPoint =
    scenario.activeNodeId !== null &&
    conversation.length > 0 &&
    conversation[conversation.length - 1].id === scenario.activeNodeId;

  const hasChildren =
    scenario.activeNodeId !== null &&
    scenario.nodeIds.some((nid) => nodes[nid]?.parentId === scenario.activeNodeId);

  const isViewingHistory = isAtHistoricalPoint && hasChildren;

  // Find leaf node for jumping forward to newest point
  const leafNode = scenario.activeNodeId ? getLeafNode(scenario.activeNodeId, scenario, nodes) : null;

  return (
    <div className="flex flex-col h-full bg-bg">
      {/* Header */}
      <header className="flex items-center justify-between px-5 py-3 border-b border-border bg-bg shrink-0">
        <div className="flex items-center gap-2 min-w-0 flex-1 mr-3">
          <GitBranch size={16} className="text-accent shrink-0" />
          {isEditingTitle ? (
            <input
              ref={titleInputRef}
              type="text"
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={handleSaveTitle}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveTitle();
                if (e.key === 'Escape') {
                  setTitleDraft(scenario.title);
                  setIsEditingTitle(false);
                }
              }}
              className="text-sm font-semibold text-fg bg-surface px-2 py-0.5 rounded border border-accent focus:outline-none w-full max-w-sm"
              aria-label="Rename scenario"
            />
          ) : (
            <div className="flex items-center gap-1.5 min-w-0 group cursor-pointer" onClick={startEditing}>
              <h1 className="text-sm font-semibold text-fg truncate group-hover:text-accent transition-colors">
                {scenario.title}
              </h1>
              <button
                className="opacity-0 group-hover:opacity-100 p-1 text-fg-muted hover:text-accent rounded transition-all"
                aria-label="Rename scenario"
                title="Click to rename"
              >
                <Pencil size={12} />
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {rememberedContext.length > 0 && (
            <button
              onClick={() => setShowRememberedPanel(!showRememberedPanel)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors border ${
                showRememberedPanel
                  ? 'bg-accent text-accent-fg border-accent'
                  : 'bg-accent-muted text-accent border-accent/20 hover:bg-accent/15'
              }`}
              title="Inspect remembered context from alternate branches"
            >
              <Sparkles size={12} />
              <span>{rememberedContext.length} remembered</span>
              {showRememberedPanel ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          )}

          {conversation.length > 0 && (
            <span className="text-[11px] text-fg-muted">
              {conversation.length} exchange{conversation.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </header>

      {/* Remembered Context Drawer */}
      {showRememberedPanel && rememberedContext.length > 0 && (
        <div className="bg-bg-secondary border-b border-border px-5 py-3 animate-fade-in text-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold text-fg flex items-center gap-1.5">
              <BookmarkCheck size={13} className="text-accent" />
              Persistent Context from Other Branches
            </span>
            <span className="text-[11px] text-fg-muted">
              Included as supplemental context for the AI
            </span>
          </div>
          <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
            {rememberedContext.map((rn) => (
              <div
                key={rn.id}
                className="flex items-center justify-between p-2 rounded-md bg-surface border border-border text-fg-secondary hover:border-accent/40 transition-colors"
              >
                <div className="min-w-0 flex-1 mr-3">
                  <p className="font-medium text-fg truncate">
                    {truncate(rn.userMessage, 60)}
                  </p>
                  <p className="text-[10px] text-fg-muted truncate mt-0.5">
                    {truncate(rn.assistantMessage, 80)}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => onSelectNode(rn.id)}
                    className="px-2 py-0.5 rounded text-[10px] font-medium text-accent hover:bg-accent-muted transition-colors"
                    title="Jump to this branch"
                  >
                    Go to branch
                  </button>
                  <button
                    onClick={() => onToggleRemember(rn.id)}
                    className="p-1 rounded text-fg-muted hover:text-error transition-colors"
                    title="Remove from remembered context"
                    aria-label="Remove remembered exchange"
                  >
                    <BookmarkCheck size={13} className="text-accent" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Time travel historical banner */}
      {isViewingHistory && (
        <div className="bg-accent-muted border-b border-accent/20 px-5 py-2 flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-2 min-w-0">
            <CornerUpLeft size={14} className="text-accent shrink-0" />
            <span className="text-xs text-accent font-medium truncate">
              Viewing historical checkpoint. Sending a message here creates a new branch.
            </span>
          </div>
          {leafNode && leafNode.id !== scenario.activeNodeId && (
            <button
              onClick={() => onSelectNode(leafNode.id)}
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-surface hover:bg-surface-hover text-accent text-xs font-medium border border-accent/30 transition-colors shrink-0 ml-3"
            >
              <FastForward size={12} />
              <span>Jump to latest</span>
            </button>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-5">
        {conversation.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-6">
            <div className="w-12 h-12 rounded-xl bg-accent-muted flex items-center justify-center mb-4">
              <GitBranch size={22} className="text-accent" />
            </div>
            <h2 className="text-lg font-semibold text-fg mb-2">
              Start a scenario exploration
            </h2>
            <p className="text-sm text-fg-secondary max-w-sm leading-relaxed mb-4">
              Ask a question or weigh a critical decision. Every exchange becomes an interactive checkpoint you can revisit and branch from.
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-md">
              {[
                'Should I switch careers to software engineering?',
                'Should we bootstrap or raise venture capital?',
                'Moving to a new city vs staying close to family',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => {
                    setInput(suggestion);
                    textareaRef.current?.focus();
                  }}
                  className="text-xs text-fg-secondary bg-surface border border-border px-3 py-1.5 rounded-full hover:border-accent hover:text-accent transition-colors"
                >
                  "{suggestion}"
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {conversation.map((node, i) => (
              <MessageBubble
                key={node.id}
                node={node}
                isOnActiveTip={i === conversation.length - 1}
                onToggleRemember={onToggleRemember}
                onCopyResponse={handleCopyResponse}
                onTimeTravel={onSelectNode}
              />
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="border-t border-border bg-bg px-4 py-3 shrink-0">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2 bg-surface border border-border rounded-xl px-3 py-2 focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/30 transition-all shadow-xs">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isViewingHistory
                  ? 'Continue from this checkpoint to branch off into an alternate path…'
                  : 'Explore a question or possibility…'
              }
              rows={1}
              disabled={isPending}
              className="flex-1 resize-none bg-transparent text-sm text-fg placeholder:text-fg-muted focus:outline-none py-1 max-h-[150px]"
              aria-label="Message input"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isPending}
              className="p-2 rounded-lg bg-accent text-accent-fg hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0 shadow-xs"
              aria-label="Send message"
            >
              {isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Send size={16} />
              )}
            </button>
          </div>
          <p className="text-[10px] text-fg-muted mt-1.5 text-center">
            Press Enter to send · Shift+Enter for new line · Remember exchanges to persist context across branches
          </p>
        </div>
      </div>
    </div>
  );
}
