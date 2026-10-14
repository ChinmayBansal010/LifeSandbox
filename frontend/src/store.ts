/* ─── Application store hook ───────────────────────────────────────── */

import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';
import type { AppState, Scenario, ScenarioNode, ThemePreference } from './types';
import { createId } from './graph-utils';
import { loadState, saveState } from './persistence';
import { getMockResponse } from './mock-ai';

// ─── Singleton store ──────────────────────────────────────────────
let state: AppState = loadState();
const listeners = new Set<() => void>();

function getState(): AppState {
  return state;
}

function setState(next: AppState) {
  state = next;
  saveState(state);
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// ─── Actions ──────────────────────────────────────────────────────
function createScenario(title?: string): Scenario {
  const id = createId();
  const now = Date.now();
  const scenario: Scenario = {
    id,
    title: title || 'New scenario',
    rootNodeId: null,
    activeNodeId: null,
    nodeIds: [],
    createdAt: now,
    updatedAt: now,
  };
  setState({
    ...state,
    scenarios: { ...state.scenarios, [id]: scenario },
    activeScenarioId: id,
  });
  return scenario;
}

function deleteScenario(scenarioId: string) {
  const scenario = state.scenarios[scenarioId];
  if (!scenario) return;

  const newNodes = { ...state.nodes };
  for (const nodeId of scenario.nodeIds) {
    delete newNodes[nodeId];
  }

  const newScenarios = { ...state.scenarios };
  delete newScenarios[scenarioId];

  const scenarioIds = Object.keys(newScenarios);
  setState({
    ...state,
    scenarios: newScenarios,
    nodes: newNodes,
    activeScenarioId:
      state.activeScenarioId === scenarioId
        ? scenarioIds[0] ?? null
        : state.activeScenarioId,
  });
}

function setActiveScenario(scenarioId: string) {
  if (!state.scenarios[scenarioId]) return;
  setState({ ...state, activeScenarioId: scenarioId });
}

function renameScenario(scenarioId: string, title: string) {
  const scenario = state.scenarios[scenarioId];
  if (!scenario) return;
  setState({
    ...state,
    scenarios: {
      ...state.scenarios,
      [scenarioId]: { ...scenario, title, updatedAt: Date.now() },
    },
  });
}

function setActiveNode(scenarioId: string, nodeId: string) {
  const scenario = state.scenarios[scenarioId];
  if (!scenario || !scenario.nodeIds.includes(nodeId)) return;
  setState({
    ...state,
    scenarios: {
      ...state.scenarios,
      [scenarioId]: { ...scenario, activeNodeId: nodeId, updatedAt: Date.now() },
    },
  });
}

function addNode(
  scenarioId: string,
  userMessage: string,
  assistantMessage: string,
  parentId: string | null
): ScenarioNode {
  const scenario = state.scenarios[scenarioId];
  if (!scenario) throw new Error(`Scenario ${scenarioId} not found`);

  const nodeId = createId();
  const now = Date.now();
  const node: ScenarioNode = {
    id: nodeId,
    parentId,
    scenarioId,
    userMessage,
    assistantMessage,
    createdAt: now,
    rememberEnabled: false,
  };

  const updatedScenario: Scenario = {
    ...scenario,
    nodeIds: [...scenario.nodeIds, nodeId],
    activeNodeId: nodeId,
    rootNodeId: scenario.rootNodeId ?? nodeId,
    updatedAt: now,
  };

  // Auto-title from first message
  if (!scenario.rootNodeId) {
    updatedScenario.title =
      userMessage.length > 40
        ? userMessage.slice(0, 40) + '…'
        : userMessage;
  }

  setState({
    ...state,
    nodes: { ...state.nodes, [nodeId]: node },
    scenarios: { ...state.scenarios, [scenarioId]: updatedScenario },
  });

  return node;
}

function toggleRemember(nodeId: string) {
  const node = state.nodes[nodeId];
  if (!node) return;
  setState({
    ...state,
    nodes: {
      ...state.nodes,
      [nodeId]: { ...node, rememberEnabled: !node.rememberEnabled },
    },
  });
}

function setTheme(theme: ThemePreference) {
  setState({ ...state, theme });
}

// ─── Hook ─────────────────────────────────────────────────────────
export function useStore() {
  const appState = useSyncExternalStore(subscribe, getState, getState);

  const activeScenario = appState.activeScenarioId
    ? appState.scenarios[appState.activeScenarioId] ?? null
    : null;

  // Track in-flight AI requests to prevent double-sends
  const pendingRef = useRef(false);

  const sendMessage = useCallback(
    async (scenarioId: string, userMessage: string, parentId: string | null) => {
      if (pendingRef.current) return;
      pendingRef.current = true;

      // Immediately create node with empty assistant message (loading state)
      const node = addNode(scenarioId, userMessage, '', parentId);

      try {
        const response = await getMockResponse(userMessage);
        // Update the node with the AI response
        const currentState = getState();
        const existingNode = currentState.nodes[node.id];
        if (existingNode) {
          setState({
            ...currentState,
            nodes: {
              ...currentState.nodes,
              [node.id]: { ...existingNode, assistantMessage: response },
            },
          });
        }
      } catch {
        // On error, set a fallback message
        const currentState = getState();
        const existingNode = currentState.nodes[node.id];
        if (existingNode) {
          setState({
            ...currentState,
            nodes: {
              ...currentState.nodes,
              [node.id]: {
                ...existingNode,
                assistantMessage:
                  'I apologize, but I was unable to generate a response. Please try again.',
              },
            },
          });
        }
      } finally {
        pendingRef.current = false;
      }
    },
    []
  );

  return {
    state: appState,
    activeScenario,
    isPending: pendingRef.current,

    // Actions
    createScenario,
    deleteScenario,
    setActiveScenario,
    renameScenario,
    setActiveNode,
    sendMessage,
    toggleRemember,
    setTheme,
  };
}

// ─── Theme effect hook ────────────────────────────────────────────
export function useThemeEffect(theme: ThemePreference) {
  useEffect(() => {
    const root = document.documentElement;

    function apply(isDark: boolean) {
      if (isDark) {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    }

    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      apply(mq.matches);
      const handler = (e: MediaQueryListEvent) => apply(e.matches);
      mq.addEventListener('change', handler);
      return () => mq.removeEventListener('change', handler);
    } else {
      apply(theme === 'dark');
    }
  }, [theme]);
}
