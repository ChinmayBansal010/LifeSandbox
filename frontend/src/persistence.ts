/* ─── Local storage persistence ────────────────────────────────────── */

import type { AppState } from './types';

const STORAGE_KEY = 'life-sandbox-state';
const STORAGE_VERSION = 1;

type StoredState = {
  version: number;
  data: AppState;
};

const DEFAULT_STATE: AppState = {
  scenarios: {},
  nodes: {},
  activeScenarioId: null,
  theme: 'system',
};

/**
 * Load application state from localStorage.
 * Returns default state if nothing is stored or data is invalid.
 */
export function loadState(): AppState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_STATE };

    const parsed: StoredState = JSON.parse(raw);
    if (!parsed || parsed.version !== STORAGE_VERSION || !parsed.data) {
      return { ...DEFAULT_STATE };
    }

    // Validate basic structure
    const { data } = parsed;
    if (
      typeof data.scenarios !== 'object' ||
      typeof data.nodes !== 'object'
    ) {
      return { ...DEFAULT_STATE };
    }

    return {
      scenarios: data.scenarios ?? {},
      nodes: data.nodes ?? {},
      activeScenarioId: data.activeScenarioId ?? null,
      theme: data.theme ?? 'system',
    };
  } catch {
    return { ...DEFAULT_STATE };
  }
}

/**
 * Save application state to localStorage.
 */
export function saveState(state: AppState): void {
  try {
    const stored: StoredState = {
      version: STORAGE_VERSION,
      data: state,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
  } catch {
    // Storage full or unavailable — silently fail
    console.warn('Failed to persist state to localStorage');
  }
}

/**
 * Load theme preference (fast path for initial render).
 */
export function loadThemePreference(): 'light' | 'dark' | 'system' {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return 'system';
    const parsed = JSON.parse(raw);
    return parsed?.data?.theme ?? 'system';
  } catch {
    return 'system';
  }
}
