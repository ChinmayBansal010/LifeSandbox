/* ─── Chat interface: Clean Linear Conversation + Composer ──────────── */

import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import {
  Send,
  Copy,
  Check,
  Loader2,
  Pencil,
  Sparkles,
  Globe,
  MessageSquare,
  Activity,
  Command,
  type LucideIcon,
} from 'lucide-react';
import type { Conversation, ChatMessage } from '../types';
import { formatTimestamp } from '../graph-utils';
import { FormattedMessage } from './FormattedMessage';

type ChatProps = {
  conversation: Conversation;
  onSendMessage: (
    userMessage: string,
    remember: boolean,
    browse: boolean,
  ) => Promise<boolean>;
  mem0Enabled: boolean;
  browserUseEnabled: boolean;
  onRenameConversation?: (conversationId: string, title: string) => void;
  onOpenAdminPanel?: (traceId?: string) => void;
  isPending: boolean;
};

function IntegrationOption({
  id,
  icon: Icon,
  title,
  description,
  setupHint,
  configured,
  checked,
  disabled,
  onChange,
}: {
  id: string;
  icon: LucideIcon;
  title: string;
  description: string;
  setupHint: string;
  configured: boolean;
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  const status = checked ? 'On for this reply' : configured ? 'Ready' : 'Setup required';

  return (
    <label
      htmlFor={id}
      className={`flex items-start gap-3 p-3 rounded-xl border transition-colors cursor-pointer ${
        checked
          ? 'bg-accent-muted border-accent/40'
          : 'bg-surface border-border hover:border-accent/30'
      } ${!configured || disabled ? 'opacity-75' : ''}`}
    >
      <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${checked ? 'bg-accent text-accent-fg' : 'bg-bg-secondary text-fg-secondary'}`}>
        <Icon size={16} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-fg">{title}</span>
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-medium ${
            checked
              ? 'bg-accent text-accent-fg'
              : configured
                ? 'bg-success/10 text-success'
                : 'bg-bg-secondary text-fg-muted'
          }`}>
            {status}
          </span>
        </span>
        <span className="mt-1 block text-[10px] leading-relaxed text-fg-secondary">
          {configured ? description : setupHint}
        </span>
      </span>
      <span className="relative mt-1 inline-flex h-5 w-9 shrink-0 items-center">
        <input
          id={id}
          type="checkbox"
          role="switch"
          checked={checked}
          disabled={!configured || disabled}
          onChange={(event) => onChange(event.target.checked)}
          className="peer sr-only"
          aria-label={title}
        />
        <span className="absolute inset-0 rounded-full bg-border transition-colors peer-checked:bg-accent peer-disabled:cursor-not-allowed peer-focus-visible:ring-2 peer-focus-visible:ring-accent/50" />
        <span className="pointer-events-none absolute left-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-4" />
      </span>
    </label>
  );
}

function MessageBubble({
  message,
  onCopyResponse,
  onOpenAdminPanel,
}: {
  message: ChatMessage;
  onCopyResponse: (text: string) => void;
  onOpenAdminPanel?: (traceId?: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const isLoading = message.assistantMessage === '';
  const toolsCount = message.toolsAccessed?.length ?? 0;

  const handleCopy = () => {
    onCopyResponse(message.assistantMessage);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="animate-fade-in space-y-4 mb-6">
      {/* User message */}
      <div className="flex justify-end">
        <div className="max-w-[85%] sm:max-w-[70%] lg:max-w-[60%]">
          <div className="bg-accent text-accent-fg px-4 py-3 rounded-2xl rounded-br-md text-sm leading-relaxed shadow-xs">
            {message.userMessage}
          </div>
          <div className="flex justify-end mt-1 px-1">
            <span className="text-[10px] text-fg-muted">
              {formatTimestamp(message.createdAt)}
            </span>
          </div>
        </div>
      </div>

      {/* Assistant message */}
      <div className="flex justify-start">
        <div className="max-w-[85%] sm:max-w-[70%] lg:max-w-[65%]">
          <div className="bg-surface border border-border px-4 py-3 rounded-2xl rounded-bl-md text-sm leading-relaxed text-fg shadow-xs">
            {isLoading ? (
              <div className="flex items-center gap-2.5 text-fg-muted py-1.5">
                <Loader2 size={15} className="animate-spin text-accent" />
                <span className="text-xs">Processing prompt and accessing tools…</span>
              </div>
            ) : (
              <div>
                {message.skill && (
                  <div className="flex items-center gap-1.5 mb-2.5 pb-2 border-b border-border/60 text-[11px] text-fg-muted flex-wrap">
                    <Sparkles size={13} className="text-accent shrink-0" />
                    <span className="font-semibold text-fg">Skill Applied:</span>
                    <span className="px-2 py-0.5 rounded-full bg-accent-muted text-accent font-medium text-[10px] border border-accent/20">
                      /{message.skill.replace('_', '-')}
                    </span>
                    {message.skillTrigger && (
                      <span className="text-[10px] text-fg-muted font-mono bg-bg-secondary px-1.5 py-0.5 rounded border border-border/50">
                        {message.skillTrigger === 'slash_command' ? 'slash command' : 'context detected'}
                      </span>
                    )}
                  </div>
                )}
                <FormattedMessage content={message.assistantMessage} />
              </div>
            )}
          </div>

          {/* Actions & Tool trace row */}
          {!isLoading && (
            <div className="flex items-center justify-between gap-2 mt-2 px-1 flex-wrap">
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-fg-muted hover:text-fg hover:bg-surface-hover transition-colors"
                  aria-label="Copy response"
                >
                  {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>

              {toolsCount > 0 && onOpenAdminPanel && (
                <button
                  onClick={() => onOpenAdminPanel(message.traceId)}
                  className="flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-medium bg-accent-muted text-accent hover:bg-accent/20 transition-colors border border-accent/20"
                  title="View tool calls and execution timestamps in Admin Panel"
                >
                  <Activity size={11} />
                  <span>{toolsCount} tool{toolsCount !== 1 ? 's' : ''} accessed · View trace</span>
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
  conversation,
  onSendMessage,
  onRenameConversation,
  onOpenAdminPanel,
  isPending,
  mem0Enabled,
  browserUseEnabled,
}: ChatProps) {
  const [input, setInput] = useState('');
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(conversation.title);
  const [rememberWithMem0, setRememberWithMem0] = useState(false);
  const [allowBrowserUse, setAllowBrowserUse] = useState(false);
  const [memoryStatus, setMemoryStatus] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);

  const startEditing = () => {
    setTitleDraft(conversation.title);
    setIsEditingTitle(true);
  };

  useEffect(() => {
    if (isEditingTitle) {
      titleInputRef.current?.focus();
      titleInputRef.current?.select();
    }
  }, [isEditingTitle]);

  // Auto-scroll on new messages
  const messages = conversation.messages;
  const lastMessage = messages[messages.length - 1];
  const lastAssistantMessage = lastMessage?.assistantMessage;
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, lastAssistantMessage]);

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
    setMemoryStatus('');
    const saved = await onSendMessage(
      msg,
      rememberWithMem0,
      allowBrowserUse,
    );
    if (rememberWithMem0 && !saved) {
      setMemoryStatus('Mem0 did not confirm saving this exchange.');
    }
    setRememberWithMem0(false);
    setAllowBrowserUse(false);
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
    if (trimmed && trimmed !== conversation.title && onRenameConversation) {
      onRenameConversation(conversation.id, trimmed);
    } else {
      setTitleDraft(conversation.title);
    }
  };

  const handleCopyResponse = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="flex flex-col h-full bg-bg overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-5 py-3.5 border-b border-border bg-bg shrink-0">
        <div className="flex items-center gap-2.5 min-w-0 flex-1 mr-3">
          <MessageSquare size={16} className="text-accent shrink-0" />
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
                  setTitleDraft(conversation.title);
                  setIsEditingTitle(false);
                }
              }}
              className="text-sm font-semibold text-fg bg-surface px-2.5 py-1 rounded-md border border-accent focus:outline-none w-full max-w-sm"
              aria-label="Rename conversation"
            />
          ) : (
            <div
              className="flex items-center gap-1.5 min-w-0 group cursor-pointer"
              onClick={startEditing}
            >
              <h1 className="text-sm font-semibold text-fg truncate group-hover:text-accent transition-colors">
                {conversation.title}
              </h1>
              <button
                className="opacity-0 group-hover:opacity-100 p-1 text-fg-muted hover:text-accent rounded transition-all"
                aria-label="Rename conversation"
                title="Click to rename"
              >
                <Pencil size={12} />
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {messages.length > 0 && (
            <span className="text-[11px] text-fg-muted font-medium">
              {messages.length} message{messages.length !== 1 ? 's' : ''}
            </span>
          )}
          {onOpenAdminPanel && (
            <button
              onClick={() => onOpenAdminPanel()}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-border bg-surface hover:bg-surface-hover text-fg-secondary hover:text-fg text-xs font-medium transition-colors"
              title="Open Admin Panel to view tools accessed"
            >
              <Activity size={13} className="text-accent" />
              <span>Admin Panel</span>
            </button>
          )}
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-6">
            <div className="w-12 h-12 rounded-2xl bg-accent-muted flex items-center justify-center mb-4">
              <MessageSquare size={22} className="text-accent" />
            </div>
            <h2 className="text-lg font-bold text-fg mb-2">
              Start a conversation
            </h2>
            <p className="text-sm text-fg-secondary max-w-sm leading-relaxed mb-6">
              Ask questions, compare decision options, or seek live research. All tool calls and timestamps are recorded for developer inspection in the Admin Panel.
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-md">
              {[
                'Compare plan A (20 mins code) vs plan B (30 mins study) for 60 mins',
                'Should I switch careers to software engineering?',
                'Moving to a new city vs staying close to family',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => {
                    setInput(suggestion);
                    textareaRef.current?.focus();
                  }}
                  className="text-xs text-fg-secondary bg-surface border border-border px-3.5 py-2 rounded-full hover:border-accent hover:text-accent transition-colors"
                >
                  "{suggestion}"
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto w-full">
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onCopyResponse={handleCopyResponse}
                onOpenAdminPanel={onOpenAdminPanel}
              />
            ))}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="border-t border-border bg-bg px-4 py-3 shrink-0">
        <div className="max-w-3xl mx-auto">
          {/* Quick Skill Slash Commands */}
          <div className="flex items-center gap-1.5 mb-2 overflow-x-auto pb-1 text-xs">
            <span className="text-[11px] font-medium text-fg-muted flex items-center gap-1 shrink-0">
              <Command size={11} className="text-accent" />
              <span>Skills:</span>
            </span>
            {[
              { name: 'budgeting', cmd: '/budgeting' },
              { name: 'career', cmd: '/career' },
              { name: 'education', cmd: '/education' },
              { name: 'purchasing', cmd: '/purchasing' },
              { name: 'travel', cmd: '/travel' },
              { name: 'time-management', cmd: '/time-management' },
            ].map((s) => (
              <button
                key={s.cmd}
                type="button"
                onClick={() => {
                  const prefix = `${s.cmd} `;
                  setInput((prev) => (prev.startsWith('/') ? `${prefix}${prev.replace(/^\/\S+\s*/, '')}` : `${prefix}${prev}`));
                  textareaRef.current?.focus();
                }}
                className="px-2 py-0.5 rounded-md bg-surface border border-border hover:border-accent hover:text-accent text-[11px] font-mono text-fg-secondary transition-colors shrink-0 shadow-2xs"
                title={`Trigger ${s.name} skill`}
              >
                {s.cmd}
              </button>
            ))}
          </div>

          <div className="flex items-end gap-2 bg-surface border border-border rounded-xl px-3 py-2 focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/30 transition-all shadow-xs">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question, comparison, or use /<skill> (e.g. /budgeting, /career)…"
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
            Press Enter to send · Shift+Enter for new line
          </p>

          <section
            className="mt-3 rounded-2xl border border-border bg-bg-secondary/70 p-3"
            aria-label="Optional integrations for this reply"
          >
            <div className="mb-2.5 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-[11px] font-semibold text-fg">Tools for this reply</h2>
                <p className="mt-0.5 text-[10px] text-fg-muted">Optional tool integrations · Resets after send</p>
              </div>
              {(rememberWithMem0 || allowBrowserUse) && (
                <span className="rounded-full bg-accent-muted px-2 py-1 text-[9px] font-medium text-accent">
                  {Number(rememberWithMem0) + Number(allowBrowserUse)} enabled
                </span>
              )}
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <IntegrationOption
                id="remember-with-mem0"
                icon={Sparkles}
                title="Mem0 hosted memory"
                description="Your message is sent to Mem0 for search; the exchange is sent after the reply to save."
                setupHint="Add MEM0_API_KEY to backend environment to enable hosted memory."
                configured={mem0Enabled}
                checked={rememberWithMem0}
                disabled={isPending}
                onChange={setRememberWithMem0}
              />
              <IntegrationOption
                id="allow-browser-use"
                icon={Globe}
                title="Browser Use research"
                description="A fresh local browser visits public GitHub pages only; it uses no login profile and downloads no files."
                setupHint="Install Browser Use and Chromium in the backend, enable BROWSER_USE_ENABLED, and configure a model."
                configured={browserUseEnabled}
                checked={allowBrowserUse}
                disabled={isPending}
                onChange={setAllowBrowserUse}
              />
            </div>
          </section>
          {memoryStatus && (
            <p className="text-[10px] text-error mt-1 text-center">{memoryStatus}</p>
          )}
        </div>
      </div>
    </div>
  );
}
