/* ─── General utility functions ──────────────────────────────────────── */

/** Generate a unique ID */
export function createId(): string {
  return crypto.randomUUID();
}

/** Truncate text with ellipsis */
export function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '…';
}

/** Format milliseconds or ISO timestamps into readable local time */
export function formatTimestamp(value: number | string | null | undefined): string {
  if (!value) return '';
  const date = typeof value === 'number' ? new Date(value) : new Date(value);
  if (isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/** Format duration in milliseconds */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}
