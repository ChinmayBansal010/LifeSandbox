/* ─── Chat interface: Clean Linear Conversation + Composer ──────────── */

import { useState, useRef, useEffect, useMemo, useCallback, lazy, Suspense, type KeyboardEvent } from 'react';
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
  Mic,
  Paperclip,
  Square,
  Volume2,
  FileText,
  Image as ImageIcon,
  Blocks,
  Plus,
  ChevronRight,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import type { Conversation, ChatMessage, CustomSkill, FileAttachment } from '../types';
import type { ThemePreference } from '../types';
import { formatTimestamp } from '../graph-utils';
import { FormattedMessage } from './FormattedMessage';
const OpenUIMessage = lazy(() => import('./OpenUIMessage'));

function AssistantContent({ content, themeMode }: { content: string; themeMode: 'light' | 'dark' }) {
  const fenced = content.match(/```openui\s*\n([\s\S]*?)\n```/i);
  const program = fenced?.[1] ?? ( /(^|\n)root\s*=/.test(content) ? content : null );
  if (program) return <Suspense fallback={<div className="text-xs text-fg-muted">Loading interactive view…</div>}><OpenUIMessage response={program} mode={themeMode} /></Suspense>;
  return <FormattedMessage content={content} />;
}

type ChatProps = {
  conversation: Conversation;
  onSendMessage: (
    userMessage: string,
    remember: boolean,
    browse: boolean,
    attachments: FileAttachment[],
  ) => Promise<string>;
  mem0Enabled: boolean;
  hostedMemoryAllowed: boolean;
  browserUseEnabled: boolean;
  sttEnabled: boolean;
  ttsEnabled: boolean;
  imageUnderstandingEnabled: boolean;
  onRenameConversation?: (conversationId: string, title: string) => void;
  onOpenAdminPanel?: (traceId?: string) => void;
  onOpenPlugins?: () => void;
  onOpenCustomSkills?: () => void;
  customSkills?: Record<string, CustomSkill>;
  onSaveCustomSkill?: (skill: any) => void;
  initialPrompt?: string | null;
  onClearInitialPrompt?: () => void;
  isPending: boolean;
  theme: ThemePreference;
  isMessagesLoading?: boolean;
  messagesError?: string | null;
  onRetryLoadMessages?: () => void;
};

let activeSpeech: HTMLAudioElement | null = null;

const SLASH_COMMANDS = [
  { cmd: '/plugins', name: 'Plugins & Tools', desc: 'Browse and inspect live backend plugins' },
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
  ttsEnabled,
  autoRead,
  themeMode,
}: {
  message: ChatMessage;
  onCopyResponse: (text: string) => void;
  onOpenAdminPanel?: (traceId?: string) => void;
  ttsEnabled: boolean;
  autoRead: boolean;
  themeMode: 'light' | 'dark';
}) {
  const [copied, setCopied] = useState(false);
  const isLoading = message.assistantMessage === '';
  const toolsCount = message.toolsAccessed?.length ?? 0;
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [speechBusy, setSpeechBusy] = useState(false);
  const [speechPlaying, setSpeechPlaying] = useState(false);
  const [hasAudio, setHasAudio] = useState(false);
  const [speechError, setSpeechError] = useState('');

  const playSpeech = async () => {
    setSpeechError('');
    setSpeechBusy(true);
    try {
      const response = await fetch('/api/v1/audio/speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: message.assistantMessage }),
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail?.message || 'Speech generation failed');
      }
      const url = URL.createObjectURL(await response.blob());
      if (activeSpeech) {
        activeSpeech.pause();
        URL.revokeObjectURL(activeSpeech.src);
      }
      const audio = new Audio(url);
      audioRef.current = audio;
      activeSpeech = audio;
      setHasAudio(true);
      audio.onplay = () => setSpeechPlaying(true);
      audio.onpause = () => setSpeechPlaying(false);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        activeSpeech = null;
        setHasAudio(false);
        setSpeechPlaying(false);
      };
      await audio.play();
    } catch (error) {
      setSpeechError(error instanceof Error ? error.message : 'Speech generation failed');
    } finally {
      setSpeechBusy(false);
    }
  };

  useEffect(() => {
    if (autoRead && ttsEnabled && !isLoading) {
      void playSpeech();
    }
  }, [autoRead, ttsEnabled, isLoading, message.id]);

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
            {message.attachments && message.attachments.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5 border-t border-white/20 pt-2">
                {message.attachments.map((file) => (
                  <span
                    key={file.id}
                    className="inline-flex max-w-full items-center gap-1.5 rounded-md bg-white/15 px-2 py-1 text-[11px]"
                    title={file.filename}
                  >
                    {file.mime_type?.startsWith('image/') ? (
                      <ImageIcon size={12} />
                    ) : (
                      <FileText size={12} />
                    )}
                    <span className="truncate">{file.filename}</span>
                  </span>
                ))}
              </div>
            )}
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
              <div className="flex items-center gap-3 py-1 text-xs text-fg-muted">
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent-muted border border-accent/20">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
                  <span className="text-[11px] font-semibold text-accent">Reasoning</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent/70 animate-bounce-subtle" style={{ animationDelay: '0ms' }} />
                  <span className="h-1.5 w-1.5 rounded-full bg-accent/70 animate-bounce-subtle" style={{ animationDelay: '180ms' }} />
                  <span className="h-1.5 w-1.5 rounded-full bg-accent/70 animate-bounce-subtle" style={{ animationDelay: '360ms' }} />
                </div>
                <span className="text-[11px] text-fg-secondary">Processing prompt and accessing tools…</span>
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
                <AssistantContent content={message.assistantMessage} themeMode={themeMode} />
                {message.mem0OptIn && (
                  <p className="mt-3 border-t border-border/60 pt-2 text-[11px] text-fg-muted" role="status">
                    {message.mem0SearchStatus === 'disabled'
                      ? 'Hosted memory was not used: enable it in Memory & tasks → Memory policy.'
                      : message.mem0SearchStatus === 'failed' || message.mem0SearchStatus === 'timed_out'
                        ? 'Hosted memory could not be searched for this exchange.'
                        : message.mem0SaveStatus === 'saved'
                          ? 'Hosted memory searched and this exchange was saved.'
                          : message.mem0SaveStatus === 'failed' || message.mem0SaveStatus === 'timed_out'
                            ? 'Hosted memory search ran, but saving this exchange failed.'
                            : 'Hosted memory was requested for this exchange.'}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Actions & Tool trace row */}
          {!isLoading && (
            <>
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
                  {ttsEnabled && (
                    <>
                      <button
                        onClick={() => {
                          const audio = audioRef.current;
                          if (audio && !audio.paused) audio.pause();
                          else if (audio) void audio.play();
                          else void playSpeech();
                        }}
                        className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-fg-muted hover:text-fg hover:bg-surface-hover transition-colors"
                        aria-label="Play or pause response"
                      >
                        {speechBusy ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Volume2 size={12} />
                        )}
                        <span>{speechPlaying ? 'Pause' : hasAudio ? 'Resume' : 'Listen'}</span>
                      </button>
                      {hasAudio && (
                        <button
                          onClick={() => {
                            const audio = audioRef.current;
                            if (audio) {
                              audio.pause();
                              audio.currentTime = 0;
                              URL.revokeObjectURL(audio.src);
                              audioRef.current = null;
                              if (activeSpeech === audio) activeSpeech = null;
                              setHasAudio(false);
                              setSpeechPlaying(false);
                            }
                          }}
                          className="text-[11px] text-fg-muted hover:text-fg transition-colors"
                        >
                          Stop
                        </button>
                      )}
                    </>
                  )}
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
              {speechError && <p className="text-[10px] text-error mt-1">{speechError}</p>}
            </>
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
  onOpenPlugins,
  onOpenCustomSkills,
  customSkills = {},
  initialPrompt,
  onClearInitialPrompt,
  isPending,
  mem0Enabled,
  hostedMemoryAllowed,
  sttEnabled,
  ttsEnabled,
  imageUnderstandingEnabled,
  theme,
  isMessagesLoading = false,
  messagesError = null,
  onRetryLoadMessages,
}: ChatProps) {
  const [input, setInput] = useState('');
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(conversation.title);

  // Slash command popup state
  const [showSlashPopup, setShowSlashPopup] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');
  const [slashSelectedIndex, setSlashSelectedIndex] = useState(0);
  const [slashTrigger, setSlashTrigger] = useState<{ start: number; end: number; query: string } | null>(null);
  const [dismissedTriggerStart, setDismissedTriggerStart] = useState<number | null>(null);

  // Tools & Plugins menu in composer
  const [showToolsMenu, setShowToolsMenu] = useState(false);
  const [toolsSearch, setToolsSearch] = useState('');
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);
  const [fileStatus, setFileStatus] = useState('');
  const [recording, setRecording] = useState(false);
  const [autoRead, setAutoRead] = useState(() => localStorage.getItem('life-sandbox-auto-read') === 'true');
  const [rememberThisExchange, setRememberThisExchange] = useState(false);
  const themeMode = theme === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : theme;

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toolsMenuRef = useRef<HTMLDivElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recordedRef = useRef<Blob[]>([]);

  useEffect(() => {
    if (initialPrompt) {
      setInput(initialPrompt);
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.style.height = 'auto';
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
      }
      onClearInitialPrompt?.();
    }
  }, [initialPrompt, onClearInitialPrompt]);

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

  // Close tools menu on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        toolsMenuRef.current &&
        !toolsMenuRef.current.contains(event.target as Node)
      ) {
        setShowToolsMenu(false);
      }
    }
    if (showToolsMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showToolsMenu]);

  // Combined command list: Built-in + Custom Skills
  const allCommands = useMemo(() => {
    const list: Array<{ cmd: string; name: string; desc: string; isCustom?: boolean; id?: string }> = [
      ...SLASH_COMMANDS,
    ];
    if (customSkills) {
      Object.values(customSkills).forEach((cs) => {
        const cmd = `/${cs.slash_command.toLowerCase().replace(/^\/+/, '')}`;
        if (!list.some((existing) => existing.cmd === cmd)) {
          list.push({
            cmd,
            name: cs.name,
            desc: cs.description || 'Custom user skill',
            isCustom: true,
            id: cs.id,
          });
        }
      });
    }
    return list;
  }, [customSkills]);

  // Filtered slash commands
  const filteredCommands = useMemo(() => {
    const q = slashFilter.toLowerCase();
    return allCommands.filter(
      (c) =>
        c.cmd.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q) ||
        c.desc.toLowerCase().includes(q)
    );
  }, [allCommands, slashFilter]);

  // Evaluate slash trigger anywhere in the draft
  const evaluateSlashTrigger = (text: string, cursorPos: number) => {
    const textBefore = text.slice(0, cursorPos);
    // Find a slash at start of line or preceded by whitespace, followed by word characters up to cursor
    const match = textBefore.match(/(?:^|\s)\/([a-zA-Z0-9_-]*)$/);
    if (match) {
      const query = match[1] || '';
      const slashIndex = textBefore.lastIndexOf('/' + query);
      if (dismissedTriggerStart !== null && slashIndex === dismissedTriggerStart) {
        setShowSlashPopup(false);
    setSlashTrigger(null);
    setShowToolsMenu(false);
        setSlashTrigger(null);
        return;
      }
      setSlashTrigger({ start: slashIndex, end: cursorPos, query });
      setSlashFilter(query);
      setShowSlashPopup(true);
      setSlashSelectedIndex(0);
      return;
    }
    setShowSlashPopup(false);
    setSlashTrigger(null);
    setShowToolsMenu(false);
    setSlashTrigger(null);
    setDismissedTriggerStart(null);
  };

  // Update slash popup status on input change with cursor awareness
  const handleInputChange = (val: string, cursorPos?: number) => {
    setInput(val);
    const pos = cursorPos !== undefined ? cursorPos : (textareaRef.current?.selectionStart ?? val.length);
    evaluateSlashTrigger(val, pos);
  };

  const handleSelectSlashCommand = (cmd: string) => {
    if (cmd === '/plugins' && onOpenPlugins) {
      setShowSlashPopup(false);
    setSlashTrigger(null);
    setShowToolsMenu(false);
      setSlashTrigger(null);
      onOpenPlugins();
      return;
    }

    if (slashTrigger && textareaRef.current) {
      const before = input.slice(0, slashTrigger.start);
      const after = input.slice(slashTrigger.end);
      const insertion = `${cmd} `;
      const nextInput = before + insertion + after;
      setInput(nextInput);
      setShowSlashPopup(false);
    setSlashTrigger(null);
    setShowToolsMenu(false);
      setSlashTrigger(null);
      const newCursorPos = before.length + insertion.length;
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
        }
      }, 0);
      return;
    }

    setInput(`${cmd} `);
    setShowSlashPopup(false);
    setSlashTrigger(null);
    setShowToolsMenu(false);
    setSlashTrigger(null);
    textareaRef.current?.focus();
  };

  const activePollersRef = useRef<
    Map<
      string,
      {
        timerId?: number;
        abortController?: AbortController;
        attempts: number;
        networkFailures: number;
      }
    >
  >(new Map());

  const stopPolling = useCallback((fileId: string) => {
    const poller = activePollersRef.current.get(fileId);
    if (poller) {
      if (poller.timerId) window.clearTimeout(poller.timerId);
      if (poller.abortController) poller.abortController.abort();
      activePollersRef.current.delete(fileId);
    }
  }, []);

  useEffect(() => {
    return () => {
      activePollersRef.current.forEach((poller) => {
        if (poller.timerId) window.clearTimeout(poller.timerId);
        if (poller.abortController) poller.abortController.abort();
      });
      activePollersRef.current.clear();
    };
  }, []);

  const pollFileStatus = useCallback(
    (fileId: string, filename: string) => {
      if (activePollersRef.current.has(fileId)) return;

      const pollerState = {
        attempts: 0,
        networkFailures: 0,
        timerId: undefined as number | undefined,
        abortController: undefined as AbortController | undefined,
      };
      activePollersRef.current.set(fileId, pollerState);

      const executePoll = async () => {
        if (!activePollersRef.current.has(fileId)) return;

        const controller = new AbortController();
        pollerState.abortController = controller;

        try {
          const response = await fetch(`/api/v1/files/${encodeURIComponent(fileId)}`, {
            signal: controller.signal,
          });

          if (!activePollersRef.current.has(fileId)) return;

          if (response.ok) {
            pollerState.networkFailures = 0;
            const data = await response.json();
            const serverStatus = data.status;
            const errorMsg = data.error_message || null;

            if (serverStatus === 'ready') {
              setAttachments((prev) =>
                prev.map((item) =>
                  item.id === fileId ? { ...item, status: 'ready', error_message: null } : item
                )
              );
              stopPolling(fileId);
              setFileStatus(`“${filename}” ready`);
              return;
            }

            if (serverStatus === 'error' || serverStatus === 'failed') {
              setAttachments((prev) =>
                prev.map((item) =>
                  item.id === fileId
                    ? { ...item, status: 'error', error_message: errorMsg || 'Processing failed' }
                    : item
                )
              );
              stopPolling(fileId);
              setFileStatus(`“${filename}” failed: ${errorMsg || 'Processing failed'}`);
              return;
            }

            setAttachments((prev) =>
              prev.map((item) => (item.id === fileId ? { ...item, status: serverStatus } : item))
            );

            pollerState.attempts += 1;
            if (pollerState.attempts >= 30) {
              stopPolling(fileId);
              setAttachments((prev) =>
                prev.map((item) =>
                  item.id === fileId
                    ? {
                        ...item,
                        status: 'error',
                        error_message: 'Processing timed out. Please retry.',
                      }
                    : item
                )
              );
              setFileStatus(`“${filename}” processing timed out.`);
              return;
            }

            pollerState.timerId = window.setTimeout(executePoll, 2000);
          } else if (response.status === 404) {
            stopPolling(fileId);
            setAttachments((prev) =>
              prev.map((item) =>
                item.id === fileId
                  ? { ...item, status: 'error', error_message: 'File not found on server' }
                  : item
              )
            );
            setFileStatus(`“${filename}” not found on server`);
          } else {
            handlePollFailure();
          }
        } catch (err: any) {
          if (err?.name === 'AbortError') return;
          handlePollFailure();
        }

        function handlePollFailure() {
          if (!activePollersRef.current.has(fileId)) return;
          pollerState.networkFailures += 1;
          if (pollerState.networkFailures >= 5) {
            stopPolling(fileId);
            setAttachments((prev) =>
              prev.map((item) =>
                item.id === fileId
                  ? {
                      ...item,
                      error_message:
                        'Network error checking file status. Click retry to resume.',
                    }
                  : item
              )
            );
            setFileStatus(`Network error checking status for “${filename}”.`);
            return;
          }
          pollerState.attempts += 1;
          if (pollerState.attempts >= 30) {
            stopPolling(fileId);
            setAttachments((prev) =>
              prev.map((item) =>
                item.id === fileId
                  ? {
                      ...item,
                      status: 'error',
                      error_message: 'Processing timed out. Please retry.',
                    }
                  : item
              )
            );
            return;
          }
          pollerState.timerId = window.setTimeout(executePoll, 2000);
        }
      };

      pollerState.timerId = window.setTimeout(executePoll, 2000);
    },
    [stopPolling]
  );

  const uploadAttachment = async (file: File) => {
    const isImage = file.type.startsWith('image/') || /\.(png|jpe?g)$/i.test(file.name);
    if (isImage && !imageUnderstandingEnabled) {
      setFileStatus(
        `${file.name} stored. Configure a vision-capable model and VISION_ENABLED to ask questions about it.`
      );
    }

    const tempId = `upload-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setAttachments((prev) => [
      ...prev,
      {
        id: tempId,
        filename: file.name,
        status: 'uploading',
        mime_type: file.type,
        size_bytes: file.size,
      },
    ]);
    setFileStatus(`Uploading “${file.name}”…`);

    const form = new FormData();
    form.append('file', file);
    try {
      const response = await fetch('/api/v1/files', { method: 'POST', body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail?.message || 'Upload failed');

      setAttachments((prev) =>
        prev.map((item) =>
          item.id === tempId
            ? {
                id: result.id,
                filename: result.filename,
                status: result.status,
                mime_type: result.mime_type,
                size_bytes: result.size_bytes,
                error_message: result.error_message || null,
              }
            : item
        )
      );

      if (result.status === 'ready') {
        setFileStatus(`“${file.name}” ready`);
      } else if (result.status === 'processing') {
        setFileStatus(`Processing “${file.name}”… Text extraction in progress.`);
        pollFileStatus(result.id, result.filename);
      } else {
        setFileStatus(`“${file.name}” ${result.status}`);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Upload failed';
      setAttachments((prev) =>
        prev.map((item) =>
          item.id === tempId ? { ...item, status: 'error', error_message: msg } : item
        )
      );
      setFileStatus(`Upload failed: ${msg}`);
    }
  };

  const removeAttachment = (fileId: string) => {
    stopPolling(fileId);
    setAttachments((prev) => prev.filter((item) => item.id !== fileId));
  };

  const retryAttachment = async (file: FileAttachment) => {
    if (file.status === 'uploading') return;
    setFileStatus(`Retrying “${file.filename}”…`);
    setAttachments((prev) =>
      prev.map((item) =>
        item.id === file.id ? { ...item, status: 'processing', error_message: null } : item
      )
    );

    try {
      const response = await fetch(`/api/v1/files/${encodeURIComponent(file.id)}/retry`, {
        method: 'POST',
      });
      if (response.ok) {
        const result = await response.json();
        if (result.status === 'ready') {
          setAttachments((prev) =>
            prev.map((item) => (item.id === file.id ? { ...item, status: 'ready' } : item))
          );
          setFileStatus(`“${file.filename}” ready`);
          return;
        }
      }
    } catch {
      // Backend retry call failed or network issue; fall back to status polling
    }

    pollFileStatus(file.id, file.filename);
  };

  const startRecording = async () => {
    if (!sttEnabled || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) return;
    try {
      setFileStatus('Requesting microphone permission…');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recordedRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) recordedRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        const blob = new Blob(recordedRef.current, { type: recorder.mimeType || 'audio/webm' });
        const form = new FormData();
        form.append('file', blob, 'recording.webm');
        setFileStatus('Transcribing audio…');
        try {
          const response = await fetch('/api/v1/audio/transcriptions', { method: 'POST', body: form });
          const body = await response.json();
          if (!response.ok) throw new Error(body.detail?.message || 'Transcription failed');
          setInput(body.text);
          setFileStatus('Transcript ready. Review and edit before sending.');
          textareaRef.current?.focus();
        } catch (error) {
          setFileStatus(error instanceof Error ? error.message : 'Transcription failed');
        }
      };
      recorder.start();
      setRecording(true);
      setFileStatus('Recording…');
    } catch {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setFileStatus('Microphone permission was denied or unavailable.');
    }
  };

  const stopRecording = () => {
    recorderRef.current?.stop();
    setRecording(false);
  };

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  const unreadyAttachment = attachments.find((file) => file.status !== 'ready');
  const hasUnreadyAttachments = Boolean(unreadyAttachment);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || isPending) return;

    if (unreadyAttachment) {
      if (unreadyAttachment.status === 'uploading') {
        setFileStatus(`Uploading “${unreadyAttachment.filename}”… Please wait before sending.`);
      } else if (unreadyAttachment.status === 'processing') {
        setFileStatus(`Processing “${unreadyAttachment.filename}”… Text extraction in progress. Please wait before sending.`);
      } else if (unreadyAttachment.status === 'error' || unreadyAttachment.status === 'failed') {
        setFileStatus(`“${unreadyAttachment.filename}” failed processing. Please remove or retry the attachment before sending.`);
      } else {
        setFileStatus(`“${unreadyAttachment.filename}” is not ready yet.`);
      }
      return;
    }

    const savedInput = input;
    const savedAttachments = [...attachments];
    const useHostedMemory = rememberThisExchange;

    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setShowSlashPopup(false);
    setSlashTrigger(null);
    setShowToolsMenu(false);
    setAttachments([]);
    setRememberThisExchange(false);

    try {
      await onSendMessage(msg, useHostedMemory, false, savedAttachments);
    } catch (error: any) {
      setInput(savedInput);
      setAttachments(savedAttachments);
      const errMsg = error?.message || 'Submission failed';
      setFileStatus(`Submission failed: ${errMsg}. Your draft has been restored.`);
    }
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
    setSlashTrigger(null);
    setShowToolsMenu(false);
        if (slashTrigger) {
          setDismissedTriggerStart(slashTrigger.start);
        }
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
          {onOpenPlugins && (
            <button
              onClick={() => onOpenPlugins()}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-border bg-surface hover:bg-surface-hover text-fg-secondary hover:text-fg text-xs font-medium transition-all shadow-2xs hover:shadow-xs active:scale-95"
              title="Browse backend plugins and dynamic tools"
            >
              <Blocks size={13} className="text-accent" />
              <span>Plugins</span>
            </button>
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
        {isMessagesLoading && messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-8 text-fg-muted" role="status">
            <Loader2 size={24} className="animate-spin text-accent mb-3" />
            <p className="text-sm font-medium text-fg">Loading conversation history…</p>
            <p className="text-xs text-fg-muted mt-1">Retrieving saved messages from server</p>
          </div>
        ) : messagesError ? (
          <div className="mx-auto my-8 max-w-md p-5 rounded-2xl bg-error/10 border border-error/20 text-center animate-fade-in shadow-xs">
            <AlertCircle size={24} className="text-error mx-auto mb-2" />
            <p className="text-sm font-semibold text-error">Failed to load message history</p>
            <p className="text-xs text-fg-muted mt-1 leading-relaxed">{messagesError}</p>
            {onRetryLoadMessages && (
              <button
                type="button"
                onClick={onRetryLoadMessages}
                className="mt-3.5 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-surface border border-border text-xs font-medium hover:bg-surface-hover text-fg transition-colors shadow-2xs"
              >
                <RefreshCw size={12} /> Retry
              </button>
            )}
          </div>
        ) : messages.length === 0 ? (
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
                ttsEnabled={ttsEnabled}
                autoRead={autoRead && message.id === [...messages].reverse().find((item) => item.assistantMessage.trim())?.id}
                themeMode={themeMode}
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
            accept=".pdf,.docx,.txt,.md,.markdown,.csv,.json,.png,.jpg,.jpeg"
            onChange={(event) => {
              const files = event.target.files;
              if (files) {
                Array.from(files).forEach((f) => void uploadAttachment(f));
              }
              event.target.value = '';
            }}
            className="hidden"
            aria-label="Upload files"
          />

          {/* Slash command suggestion popup - Positioned ABOVE composer */}
          {showSlashPopup && filteredCommands.length > 0 && (
            <div
              className="absolute bottom-full mb-2 left-0 w-full max-w-md bg-surface border border-border-strong rounded-xl shadow-lg overflow-hidden z-30 animate-fade-in"
              role="listbox"
              aria-label="Slash commands"
            >
              <div className="px-3 py-1.5 bg-bg-secondary border-b border-border text-[11px] font-semibold text-fg-muted flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Sparkles size={12} className="text-accent" />
                  <span>COMMANDS & SKILLS</span>
                </span>
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
                        ? 'bg-accent text-accent-fg shadow-2xs font-medium'
                        : 'hover:bg-surface-hover text-fg'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono font-semibold shrink-0">
                        {command.cmd}
                      </span>
                      <span className={`text-[11px] truncate ${idx === slashSelectedIndex ? 'text-accent-fg/90' : 'text-fg-muted'}`}>
                        {command.desc}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0 ml-2">
                      {command.isCustom && (
                        <span className={`text-[9px] font-semibold px-1 py-0.2 rounded ${
                          idx === slashSelectedIndex
                            ? 'bg-white/25 text-white'
                            : 'bg-purple-500/10 text-purple-600 dark:text-purple-400'
                        }`}>
                          Custom
                        </span>
                      )}
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                        idx === slashSelectedIndex
                          ? 'bg-white/20 text-white'
                          : 'bg-bg-secondary text-fg-muted'
                      }`}>
                        {command.name}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Composer Input Box */}
          <div className="relative flex items-end gap-2 bg-surface border border-border rounded-xl px-2 py-1.5 focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/30 transition-all shadow-xs">
            {/* Tools & Plugins Menu Button on Left */}
            <div className="relative shrink-0" ref={toolsMenuRef}>
              <button
                type="button"
                onClick={() => {
                  setShowToolsMenu((prev) => !prev);
                  setToolsSearch('');
                }}
                disabled={isPending}
                className={`p-1.5 rounded-lg transition-colors ${
                  showToolsMenu
                    ? 'bg-accent text-accent-fg shadow-xs'
                    : 'text-fg-muted hover:text-fg hover:bg-surface-hover'
                } disabled:opacity-40`}
                aria-label="Tools and skills menu"
                title="Tools & Skills (Plugins, Built-ins, Custom Skills)"
              >
                <Menu size={18} />
              </button>

              {/* Tools & Plugins Popover */}
              {showToolsMenu && (
                <div
                  className="absolute bottom-full mb-2 left-0 w-72 sm:w-80 bg-surface border border-border-strong rounded-2xl shadow-xl p-2 z-40 animate-fade-in text-xs max-h-[380px] flex flex-col overflow-hidden"
                  role="dialog"
                  aria-label="Tools and capabilities"
                >
                  <div className="px-2 py-1.5 border-b border-border flex items-center justify-between">
                    <div className="flex items-center gap-1.5 font-semibold text-fg text-xs">
                      <Blocks size={14} className="text-accent" />
                      <span>Tools & Capabilities</span>
                    </div>
                    <span className="text-[10px] text-fg-muted font-medium">Quick Access</span>
                  </div>

                  {/* Search filter within tools menu */}
                  <div className="p-1.5">
                    <input
                      type="text"
                      placeholder="Search tools & skills…"
                      value={toolsSearch}
                      onChange={(e) => setToolsSearch(e.target.value)}
                      className="w-full px-2.5 py-1 text-xs rounded-lg border border-border bg-bg text-fg placeholder:text-fg-muted focus:outline-none focus:border-accent"
                    />
                  </div>

                  {/* Scrollable list */}
                  <div className="flex-1 overflow-y-auto space-y-2 p-1">
                    {/* Built-in Skills */}
                    <div>
                      <div className="text-[10px] font-semibold text-fg-muted uppercase tracking-wider px-1.5 py-0.5">
                        Decision Skills
                      </div>
                      <div className="space-y-0.5 mt-0.5">
                        {SLASH_COMMANDS.filter((c) =>
                          !toolsSearch ||
                          c.name.toLowerCase().includes(toolsSearch.toLowerCase()) ||
                          c.cmd.toLowerCase().includes(toolsSearch.toLowerCase())
                        ).map((cmd) => (
                          <button
                            key={cmd.cmd}
                            type="button"
                            onClick={() => {
                              handleSelectSlashCommand(cmd.cmd);
                              setShowToolsMenu(false);
                            }}
                            className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-left text-xs hover:bg-surface-hover hover:text-accent transition-colors group"
                          >
                            <div className="min-w-0 pr-2">
                              <span className="font-semibold text-fg block text-xs truncate group-hover:text-accent">
                                {cmd.name}
                              </span>
                              <span className="text-[10px] text-fg-muted font-mono">{cmd.cmd}</span>
                            </div>
                            <span className="text-[10px] font-mono text-accent opacity-0 group-hover:opacity-100 transition-opacity">
                              Use →
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Custom Skills */}
                    <div>
                      <div className="flex items-center justify-between px-1.5 py-0.5 text-[10px] font-semibold text-fg-muted uppercase tracking-wider">
                        <span>Custom Skills</span>
                        {Object.keys(customSkills).length > 0 && (
                          <span className="text-accent">{Object.keys(customSkills).length}</span>
                        )}
                      </div>
                      <div className="space-y-0.5 mt-0.5">
                        {Object.values(customSkills)
                          .filter((cs) =>
                            !toolsSearch ||
                            cs.name.toLowerCase().includes(toolsSearch.toLowerCase()) ||
                            cs.slash_command.toLowerCase().includes(toolsSearch.toLowerCase())
                          )
                          .map((cs) => (
                            <button
                              key={cs.id}
                              type="button"
                              onClick={() => {
                                handleSelectSlashCommand(`/${cs.slash_command}`);
                                setShowToolsMenu(false);
                              }}
                              className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-left text-xs hover:bg-surface-hover hover:text-accent transition-colors group"
                            >
                              <div className="min-w-0 pr-2">
                                <div className="flex items-center gap-1.5">
                                  <span className="font-semibold text-fg text-xs truncate group-hover:text-accent">
                                    {cs.name}
                                  </span>
                                  <span className="text-[9px] font-semibold px-1 py-0.2 rounded bg-purple-500/10 text-purple-600 dark:text-purple-400">
                                    Custom
                                  </span>
                                </div>
                                <span className="text-[10px] text-fg-muted font-mono">/{cs.slash_command}</span>
                              </div>
                              <span className="text-[10px] font-mono text-accent opacity-0 group-hover:opacity-100 transition-opacity">
                                Use →
                              </span>
                            </button>
                          ))}
                        {Object.keys(customSkills).length === 0 && (
                          <div className="px-2 py-2 text-center text-fg-muted text-[11px] rounded-lg bg-bg-secondary/50">
                            No custom skills created yet
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Footer actions */}
                  <div className="pt-2 border-t border-border mt-1 flex flex-col gap-1">
                    {onOpenCustomSkills && (
                      <button
                        type="button"
                        onClick={() => {
                          setShowToolsMenu(false);
                          onOpenCustomSkills();
                        }}
                        className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-muted text-accent font-semibold text-xs hover:bg-accent hover:text-accent-fg transition-colors"
                      >
                        <Plus size={13} />
                        <span>Create Custom Skill</span>
                      </button>
                    )}
                    {onOpenPlugins && (
                      <button
                        type="button"
                        onClick={() => {
                          setShowToolsMenu(false);
                          onOpenPlugins();
                        }}
                        className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-fg-secondary hover:text-fg hover:bg-surface-hover text-xs font-medium transition-colors"
                      >
                        <span>Browse All Plugins & Tools</span>
                        <ChevronRight size={13} />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Direct Paperclip Button */}
            <label
              className={`p-1.5 rounded-lg text-fg-muted hover:text-accent transition-colors ${
                isPending ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'
              }`}
              title="Attach files (.pdf, .docx, .txt, .md, images)"
            >
              <Paperclip size={16} />
              <input
                type="file"
                className="hidden"
                disabled={isPending}
                multiple
                accept=".pdf,.docx,.txt,.md,.markdown,.csv,.json,.png,.jpg,.jpeg"
                onChange={(event) => {
                  const files = event.target.files;
                  if (files) {
                    Array.from(files).forEach((f) => void uploadAttachment(f));
                  }
                  event.target.value = '';
                }}
              />
            </label>

            {/* Voice Input Button */}
            <button
              type="button"
              disabled={!sttEnabled || isPending}
              onClick={recording ? stopRecording : () => void startRecording()}
              className="p-1.5 rounded-lg text-fg-muted hover:text-accent disabled:opacity-40 transition-colors"
              aria-label={recording ? 'Stop recording' : sttEnabled ? 'Record voice message' : 'Speech transcription unavailable'}
              title={fileStatus || (sttEnabled ? 'Record voice message' : 'Enable STT_PROVIDER on the backend')}
            >
              {recording ? <Square size={16} /> : <Mic size={16} />}
            </button>

            {/* Main Textarea */}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => handleInputChange(e.target.value, e.target.selectionStart)}
              onClick={(e) => {
                const target = e.target as HTMLTextAreaElement;
                evaluateSlashTrigger(target.value, target.selectionStart);
              }}
              onKeyUp={(e) => {
                const target = e.target as HTMLTextAreaElement;
                if (!['ArrowUp', 'ArrowDown', 'Enter', 'Escape'].includes(e.key)) {
                  evaluateSlashTrigger(target.value, target.selectionStart);
                }
              }}
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
              disabled={!input.trim() || isPending || hasUnreadyAttachments}
              className="p-2 rounded-lg bg-accent text-accent-fg hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0 shadow-xs active:scale-95"
              aria-label="Send message"
              title={
                hasUnreadyAttachments
                  ? `Waiting for “${unreadyAttachment?.filename}” to finish ${
                      unreadyAttachment?.status === 'uploading' ? 'uploading' : 'processing'
                    }…`
                  : 'Send message'
              }
            >
              {isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Send size={16} />
              )}
            </button>
          </div>

          {/* Attached files preview tray */}
          {attachments.length > 0 && (
            <section
              className="mt-2 rounded-xl border border-accent/25 bg-accent-muted/30 p-2.5 animate-fade-in"
              aria-label="Files for this message"
            >
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <h2 className="text-[11px] font-semibold text-fg">Attached for this message</h2>
                <span className="text-[10px] text-fg-muted">
                  {hasUnreadyAttachments ? 'Waiting for attachments to be ready…' : 'Ready to send'}
                </span>
              </div>
              <div className="space-y-1.5">
                {attachments.map((file) => (
                  <div
                    key={file.id}
                    className="flex min-w-0 items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs shadow-2xs"
                  >
                    {file.mime_type?.startsWith('image/') ? (
                      <ImageIcon size={14} className="shrink-0 text-accent" />
                    ) : (
                      <FileText size={14} className="shrink-0 text-accent" />
                    )}
                    <span
                      className="min-w-0 flex-1 truncate text-xs text-fg font-medium"
                      title={file.filename}
                    >
                      {file.filename}
                    </span>

                    {/* Status indicator badge */}
                    {file.status === 'uploading' && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-accent font-medium">
                        <Loader2 size={11} className="animate-spin" />
                        Uploading…
                      </span>
                    )}
                    {file.status === 'processing' && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-400 font-medium">
                        <Loader2 size={11} className="animate-spin" />
                        Processing…
                      </span>
                    )}
                    {file.status === 'ready' && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                        <Check size={11} />
                        Ready
                      </span>
                    )}
                    {(file.status === 'error' || file.status === 'failed') && (
                      <div className="inline-flex items-center gap-1.5">
                        <span
                          className="inline-flex items-center gap-1 text-[11px] text-error font-medium"
                          title={file.error_message || 'Processing failed'}
                        >
                          <AlertCircle size={11} />
                          Failed
                        </span>
                        <button
                          type="button"
                          onClick={() => void retryAttachment(file)}
                          className="inline-flex items-center gap-1 rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent hover:bg-accent/20 transition-colors cursor-pointer"
                          aria-label={`Retry ${file.filename}`}
                        >
                          <RefreshCw size={9} />
                          Retry
                        </button>
                      </div>
                    )}
                    {!['uploading', 'processing', 'ready', 'error', 'failed'].includes(file.status) && (
                      <span className="text-[10px] text-fg-muted">{file.status}</span>
                    )}

                    <button
                      type="button"
                      className="ml-1 text-fg-muted hover:text-error transition-colors p-0.5 cursor-pointer"
                      onClick={() => removeAttachment(file.id)}
                      aria-label={`Remove ${file.filename} from this message`}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}

          <div className="flex items-center justify-between mt-1.5 px-1">
            <p className="text-[10px] text-fg-muted">
              Press Enter to send · Shift+Enter for new line · Type / for skills
            </p>
            <label className="text-[10px] text-fg-muted flex items-center gap-1 cursor-pointer hover:text-fg transition-colors">
              <input
                type="checkbox"
                checked={autoRead}
                onChange={(event) => {
                  setAutoRead(event.target.checked);
                  localStorage.setItem('life-sandbox-auto-read', String(event.target.checked));
                }}
                disabled={!ttsEnabled}
                className="rounded border-border text-accent focus:ring-accent"
              />
              Read replies aloud
            </label>
          </div>
          {mem0Enabled && (
            <label className="mt-2 inline-flex items-center gap-1.5 px-1 text-[10px] text-fg-muted">
              <input
                type="checkbox"
                checked={rememberThisExchange}
                onChange={(event) => setRememberThisExchange(event.target.checked)}
                disabled={isPending || !hostedMemoryAllowed}
                className="rounded border-border text-accent focus:ring-accent"
              />
              {hostedMemoryAllowed
                ? 'Use hosted memory for this exchange (search and save)'
                : 'Enable hosted memory in Memory & tasks → Memory policy'}
            </label>
          )}

          {fileStatus && (
            <p className="text-[10px] text-fg-muted mt-1 text-center animate-fade-in font-medium">
              {fileStatus}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
