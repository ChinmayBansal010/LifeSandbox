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
} from 'lucide-react';
import type { ScenarioNode, Scenario } from '../types';
import { getActiveBranch } from '../graph-utils';

type ChatProps = {
  scenario: Scenario;
  nodes: Record<string, ScenarioNode>;
  onSendMessage: (userMessage: string, parentId: string | null) => Promise<void>;
  onToggleRemember: (nodeId: string) => void;
  onSelectNode: (nodeId: string) => void;
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
          <div className="bg-surface border border-border px-4 py-2.5 rounded-2xl rounded-bl-md text-sm leading-relaxed text-fg">
            {isLoading ? (
              <div className="flex items-center gap-2 text-fg-muted py-1">
                <Loader2 size={14} className="animate-spin" />
                <span className="text-xs">Thinking…</span>
              </div>
            ) : (
              <div className="whitespace-pre-wrap">{node.assistantMessage}</div>
            )}
          </div>

          {/* Actions row */}
          {!isLoading && (
            <div className="flex items-center gap-1 mt-1.5">
              <button
                onClick={() => onToggleRemember(node.id)}
                className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition-colors ${
                  node.rememberEnabled
                    ? 'text-accent bg-accent-muted'
                    : 'text-fg-muted hover:text-fg hover:bg-surface-hover'
                }`}
                title={node.rememberEnabled ? 'Remembered — click to forget' : 'Remember this exchange'}
                aria-label={node.rememberEnabled ? 'Disable remember' : 'Enable remember'}
              >
                {node.rememberEnabled ? (
                  <BookmarkCheck size={12} />
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
                {copied ? <Check size={12} /> : <Copy size={12} />}
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
  isPending,
}: ChatProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const conversation = getActiveBranch(scenario, nodes);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation.length, conversation[conversation.length - 1]?.assistantMessage]);

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

  const handleCopyResponse = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  // Check if user is viewing a historical point (not the latest leaf)
  const isAtHistoricalPoint =
    scenario.activeNodeId !== null &&
    conversation.length > 0 &&
    conversation[conversation.length - 1].id === scenario.activeNodeId;

  const hasChildren =
    scenario.activeNodeId !== null &&
    scenario.nodeIds.some((nid) => nodes[nid]?.parentId === scenario.activeNodeId);

  const isViewingHistory = isAtHistoricalPoint && hasChildren;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="flex items-center justify-between px-5 py-3 border-b border-border bg-bg shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <GitBranch size={15} className="text-fg-muted shrink-0" />
          <h1 className="text-sm font-semibold text-fg truncate">
            {scenario.title}
          </h1>
        </div>
        {conversation.length > 0 && (
          <span className="text-[11px] text-fg-muted shrink-0">
            {conversation.length} exchange{conversation.length !== 1 ? 's' : ''}
          </span>
        )}
      </header>

      {/* Time travel banner */}
      {isViewingHistory && (
        <div className="bg-accent-muted border-b border-accent/20 px-5 py-2 flex items-center justify-between animate-fade-in">
          <span className="text-xs text-accent font-medium">
            You're viewing a historical point. Continue to create a new branch.
          </span>
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
              Start a conversation
            </h2>
            <p className="text-sm text-fg-secondary max-w-sm leading-relaxed">
              Ask a question or describe a scenario. Every exchange becomes a node you can revisit and branch from.
            </p>
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
          <div className="flex items-end gap-2 bg-surface border border-border rounded-xl px-3 py-2 focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/30 transition-all">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isViewingHistory
                  ? 'Continue from this point to create a branch…'
                  : 'Ask something…'
              }
              rows={1}
              disabled={isPending}
              className="flex-1 resize-none bg-transparent text-sm text-fg placeholder:text-fg-muted focus:outline-none py-1 max-h-[150px]"
              aria-label="Message input"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isPending}
              className="p-2 rounded-lg bg-accent text-accent-fg hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
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
            Press Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}
