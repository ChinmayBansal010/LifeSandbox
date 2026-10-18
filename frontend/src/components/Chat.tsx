/* ─── Chat interface: Clean Linear Conversation + Composer ──────────── */

import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import {
  Send,
  Copy,
  Check,
  Loader2,
  Pencil,
  Sparkles,
  MessageSquare,
  Activity,
  Menu,
  FileText,
  X,
  Upload,
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

type SelectedFile = {
  name: string;
  size: number;
  type: string;
};

const SLASH_COMMANDS = [
  { cmd: '/budgeting', name: 'Budgeting', desc: 'Budget & spending trade-offs' },
  { cmd: '/career', name: 'Career', desc: 'Career goals & compensation' },
  { cmd: '/education', name: 'Education', desc: 'Learning & study planning' },
  { cmd: '/purchasing', name: 'Purchasing', desc: 'Purchase comparison & alternatives' },
  { cmd: '/travel', name: 'Travel', desc: 'Travel dates & budget trade-offs' },
  { cmd: '/time-management', name: 'Time Management', desc: 'Schedule & commitment planning' },
];

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
        <div className="max-w-[85%] sm:max-w-[78%] lg:max-w-[75%] xl:max-w-[72%]">
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
        <div className="max-w-[88%] sm:max-w-[82%] lg:max-w-[80%] xl:max-w-[78%]">
          <div className="bg-surface border border-border px-4 py-3.5 rounded-2xl rounded-bl-md text-sm leading-relaxed text-fg shadow-xs">
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
}: ChatProps) {
  const [input, setInput] = useState('');
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(conversation.title);

  // Slash command popup state
  const [showSlashPopup, setShowSlashPopup] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');
  const [slashSelectedIndex, setSlashSelectedIndex] = useState(0);

  // Attachment menu and files state
  const [showAttachmentMenu, setShowAttachmentMenu] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const attachmentMenuRef = useRef<HTMLDivElement>(null);

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

  // Close attachment menu on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        attachmentMenuRef.current &&
        !attachmentMenuRef.current.contains(event.target as Node)
      ) {
        setShowAttachmentMenu(false);
      }
    }
    if (showAttachmentMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showAttachmentMenu]);

  // Filter slash commands
  const filteredCommands = SLASH_COMMANDS.filter(
    (c) =>
      c.cmd.toLowerCase().includes(slashFilter.toLowerCase()) ||
      c.name.toLowerCase().includes(slashFilter.toLowerCase()) ||
      c.desc.toLowerCase().includes(slashFilter.toLowerCase())
  );

  // Update slash popup status on input change
  const handleInputChange = (val: string) => {
    setInput(val);
    if (val.startsWith('/')) {
      const match = val.match(/^\/(\S*)/);
      if (match && !val.includes(' ')) {
        setShowSlashPopup(true);
        setSlashFilter(match[1] || '');
        setSlashSelectedIndex(0);
        return;
      }
    }
    setShowSlashPopup(false);
  };

  const handleSelectSlashCommand = (cmd: string) => {
    setInput(`${cmd} `);
    setShowSlashPopup(false);
    textareaRef.current?.focus();
  };

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || isPending) return;
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setShowSlashPopup(false);
    setSelectedFiles([]);
    await onSendMessage(msg, false, false);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSlashPopup && filteredCommands.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSlashSelectedIndex((prev) =>
          prev < filteredCommands.length - 1 ? prev + 1 : 0
        );
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSlashSelectedIndex((prev) =>
          prev > 0 ? prev - 1 : filteredCommands.length - 1
        );
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        const selected = filteredCommands[slashSelectedIndex];
        if (selected) {
          handleSelectSlashCommand(selected.cmd);
        }
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setShowSlashPopup(false);
        return;
      }
    }

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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const newFiles: SelectedFile[] = Array.from(files).map((f) => ({
      name: f.name,
      size: f.size,
      type: f.type || 'unknown',
    }));
    setSelectedFiles((prev) => [...prev, ...newFiles]);
    setShowAttachmentMenu(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
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
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-border bg-surface hover:bg-surface-hover text-fg-secondary hover:text-fg text-xs font-medium transition-all shadow-2xs hover:shadow-xs active:scale-95"
              title="Open Admin Panel to view tools accessed"
            >
              <Activity size={13} className="text-accent" />
              <span>Admin Panel</span>
            </button>
          )}
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-4 max-w-4xl mx-auto animate-fade-in">
            <div className="w-14 h-14 rounded-2xl bg-accent-muted flex items-center justify-center mb-4 shadow-sm border border-accent/20 animate-scale-in">
              <MessageSquare size={26} className="text-accent" />
            </div>
            <h2 className="text-xl font-bold text-fg mb-2 tracking-tight">
              What decision would you like to explore?
            </h2>
            <p className="text-xs sm:text-sm text-fg-secondary max-w-lg leading-relaxed mb-8">
              Life Sandbox models scenarios, evaluates trade-offs, and inspects verified evidence. Select a suggestion below or type your scenario.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 w-full text-left">
              {[
                {
                  title: 'Career Switch',
                  desc: 'Weigh job growth, compensation, and learning curve',
                  prompt: 'Should I transition into software engineering or stay in my current path?',
                  badge: '/career',
                },
                {
                  title: 'Budget Allocation',
                  desc: 'Model trade-offs between saving vs investing',
                  prompt: 'Help me evaluate saving $500/month vs paying down a loan faster',
                  badge: '/budgeting',
                },
                {
                  title: 'Relocation vs Family',
                  desc: 'Compare moving to a high-cost city vs staying close',
                  prompt: 'Moving to a new city for a higher salary vs staying close to family',
                  badge: '/travel',
                },
                {
                  title: 'Time & Study Schedule',
                  desc: 'Balance side projects with full-time commitments',
                  prompt: 'Compare plan A (20 mins code) vs plan B (30 mins study) for 60 mins',
                  badge: '/time-management',
                },
                {
                  title: 'High-Ticket Purchase',
                  desc: 'Compare requirements, total cost & alternatives',
                  prompt: 'Evaluate buying a premium laptop vs a budget alternative for productivity',
                  badge: '/purchasing',
                },
                {
                  title: 'Learning Milestones',
                  desc: 'Break ambitious goals into weekly checkpoints',
                  prompt: 'Create a structured 8-week plan to learn systems architecture',
                  badge: '/education',
                },
              ].map((item, idx) => (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => {
                    setInput(item.prompt);
                    textareaRef.current?.focus();
                  }}
                  style={{ animationDelay: `${idx * 40}ms` }}
                  className="group flex flex-col justify-between p-3.5 rounded-xl bg-surface border border-border hover:border-accent/50 hover:bg-surface-hover/80 transition-all duration-150 hover:-translate-y-0.5 shadow-2xs hover:shadow-xs text-left"
                >
                  <div>
                    <div className="flex items-center justify-between gap-1 mb-1.5">
                      <span className="font-semibold text-xs text-fg group-hover:text-accent transition-colors">
                        {item.title}
                      </span>
                      <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-accent-muted text-accent border border-accent/20">
                        {item.badge}
                      </span>
                    </div>
                    <p className="text-[11px] text-fg-muted leading-relaxed line-clamp-2">
                      {item.desc}
                    </p>
                  </div>
                  <span className="mt-3 text-[10px] text-accent font-medium group-hover:underline flex items-center gap-1">
                    Try prompt →
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="max-w-4xl lg:max-w-5xl mx-auto w-full">
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
      <div className="border-t border-border bg-bg px-4 sm:px-6 lg:px-8 py-3.5 shrink-0">
        <div className="max-w-4xl lg:max-w-5xl mx-auto relative">
          {/* Hidden native file input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileChange}
            className="hidden"
            aria-label="Upload files"
          />

          {/* Slash command suggestion popup - Positioned ABOVE composer */}
          {showSlashPopup && filteredCommands.length > 0 && (
            <div
              className="absolute bottom-full mb-2 left-0 w-full max-w-md bg-surface border border-border rounded-xl shadow-lg overflow-hidden z-30 animate-fade-in"
              role="listbox"
              aria-label="Slash commands"
            >
              <div className="px-3 py-1.5 bg-bg-secondary border-b border-border text-[11px] font-semibold text-fg-muted flex items-center justify-between">
                <span>SKILL COMMANDS</span>
                <span className="text-[10px]">↑↓ to navigate · Enter to select · Esc to close</span>
              </div>
              <div className="max-h-56 overflow-y-auto p-1.5 space-y-0.5">
                {filteredCommands.map((command, idx) => (
                  <button
                    key={command.cmd}
                    type="button"
                    onClick={() => handleSelectSlashCommand(command.cmd)}
                    onMouseEnter={() => setSlashSelectedIndex(idx)}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left text-xs transition-colors ${
                      idx === slashSelectedIndex
                        ? 'bg-accent text-accent-fg'
                        : 'hover:bg-surface-hover text-fg'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono font-semibold shrink-0">
                        {command.cmd}
                      </span>
                      <span className={`text-[11px] truncate ${idx === slashSelectedIndex ? 'text-accent-fg/80' : 'text-fg-muted'}`}>
                        {command.desc}
                      </span>
                    </div>
                    <span className={`text-[10px] shrink-0 font-medium px-1.5 py-0.5 rounded ${
                      idx === slashSelectedIndex
                        ? 'bg-white/20 text-white'
                        : 'bg-bg-secondary text-fg-muted'
                    }`}>
                      {command.name}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Selected files preview tray */}
          {selectedFiles.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2 animate-fade-in">
              {selectedFiles.map((file, idx) => (
                <div
                  key={`${file.name}-${idx}`}
                  className="flex items-center gap-1.5 bg-surface border border-border rounded-lg px-2.5 py-1 text-xs text-fg shadow-2xs"
                >
                  <FileText size={13} className="text-accent shrink-0" />
                  <span className="truncate max-w-[150px] font-medium text-[11px]">
                    {file.name}
                  </span>
                  <span className="text-[10px] text-fg-muted">
                    ({Math.round(file.size / 1024)} KB)
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveFile(idx)}
                    className="p-0.5 hover:bg-surface-hover rounded text-fg-muted hover:text-error transition-colors"
                    aria-label={`Remove ${file.name}`}
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
              <span className="text-[10px] text-fg-muted self-center italic">
                (Local selection preview)
              </span>
            </div>
          )}

          {/* Composer Input Box */}
          <div className="relative flex items-end gap-2 bg-surface border border-border rounded-xl px-2 py-1.5 focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/30 transition-all shadow-xs">
            {/* Attachment Menu Button on Left */}
            <div className="relative shrink-0" ref={attachmentMenuRef}>
              <button
                type="button"
                onClick={() => setShowAttachmentMenu((prev) => !prev)}
                disabled={isPending}
                className="p-1.5 rounded-lg text-fg-muted hover:text-fg hover:bg-surface-hover transition-colors disabled:opacity-40"
                aria-label="Attachment options"
                title="Add files"
              >
                <Menu size={18} />
              </button>

              {/* Attachment Dropdown */}
              {showAttachmentMenu && (
                <div className="absolute bottom-full mb-2 left-0 w-48 bg-surface border border-border rounded-xl shadow-lg p-1 z-30 animate-fade-in text-xs">
                  <button
                    type="button"
                    onClick={() => {
                      fileInputRef.current?.click();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-fg hover:bg-surface-hover hover:text-accent transition-colors"
                  >
                    <Upload size={14} className="text-accent" />
                    <span>Upload files from device</span>
                  </button>
                </div>
              )}
            </div>

            {/* Main Textarea */}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question, comparison, or type / for skills…"
              rows={1}
              disabled={isPending}
              className="flex-1 resize-none bg-transparent text-sm text-fg placeholder:text-fg-muted focus:outline-none py-1.5 max-h-[150px]"
              aria-label="Message input"
            />

            {/* Send Button */}
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
            Press Enter to send · Shift+Enter for new line · Type / for skills
          </p>
        </div>
      </div>
    </div>
  );
}
