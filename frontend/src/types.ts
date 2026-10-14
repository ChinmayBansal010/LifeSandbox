/* ─── Types: Core scenario graph model ──────────────────────────────── */

export type ScenarioNode = {
  id: string;
  parentId: string | null;
  scenarioId: string;
  userMessage: string;
  assistantMessage: string;
  createdAt: number;
  rememberEnabled: boolean;
};

export type Scenario = {
  id: string;
  title: string;
  rootNodeId: string | null;
  activeNodeId: string | null;
  nodeIds: string[];
  createdAt: number;
  updatedAt: number;
};

export type AppState = {
  scenarios: Record<string, Scenario>;
  nodes: Record<string, ScenarioNode>;
  activeScenarioId: string | null;
  theme: 'light' | 'dark' | 'system';
};

export type ThemePreference = 'light' | 'dark' | 'system';
