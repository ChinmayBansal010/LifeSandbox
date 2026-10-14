/* ─── Graph utility functions ──────────────────────────────────────── */

import type { ScenarioNode, Scenario } from './types';

/** Generate a unique ID */
export function createId(): string {
  return crypto.randomUUID();
}

/**
 * Walk from a node back to root, collecting ancestor IDs in root-first order.
 * Returns the ordered list of node IDs from root to the given node.
 * Handles missing parents gracefully by stopping the walk.
 */
export function getAncestorPath(
  nodeId: string,
  nodes: Record<string, ScenarioNode>
): string[] {
  const path: string[] = [];
  const visited = new Set<string>();
  let currentId: string | null = nodeId;

  while (currentId !== null) {
    if (visited.has(currentId)) break; // cycle guard
    const node: ScenarioNode | undefined = nodes[currentId];
    if (!node) break; // missing parent guard
    visited.add(currentId);
    path.unshift(currentId);
    currentId = node.parentId;
  }

  return path;
}

/**
 * Get the conversation for the current active branch.
 * Returns an ordered array of nodes from root to the active node.
 */
export function getActiveBranch(
  scenario: Scenario,
  nodes: Record<string, ScenarioNode>
): ScenarioNode[] {
  if (!scenario.activeNodeId) return [];
  const path = getAncestorPath(scenario.activeNodeId, nodes);
  return path.map((id) => nodes[id]).filter(Boolean);
}

/**
 * Get direct children of a node within a scenario.
 */
export function getChildren(
  nodeId: string,
  scenario: Scenario,
  nodes: Record<string, ScenarioNode>
): ScenarioNode[] {
  return scenario.nodeIds
    .map((id) => nodes[id])
    .filter((n) => n && n.parentId === nodeId);
}

/**
 * Determine whether a node is on the active path.
 */
export function isOnActivePath(
  nodeId: string,
  scenario: Scenario,
  nodes: Record<string, ScenarioNode>
): boolean {
  if (!scenario.activeNodeId) return false;
  const path = getAncestorPath(scenario.activeNodeId, nodes);
  return path.includes(nodeId);
}

/**
 * Find the leaf (deepest) node of the active branch.
 * Exported for use in context-building and navigation.
 */
export function getLeafNode(
  nodeId: string,
  scenario: Scenario,
  nodes: Record<string, ScenarioNode>
): ScenarioNode | null {
  let current: ScenarioNode | undefined = nodes[nodeId];
  if (!current) return null;

  for (;;) {
    const children = getChildren(current.id, scenario, nodes);
    if (children.length === 0) return current;
    // Follow the last child (newest branch)
    current = children[children.length - 1];
  }
}

// Re-export for external consumers
void getLeafNode;

/**
 * Get all nodes that have Remember enabled and are NOT on the given path.
 * These constitute supplemental remembered context.
 */
export function getRememberedContext(
  activePath: string[],
  scenario: Scenario,
  nodes: Record<string, ScenarioNode>
): ScenarioNode[] {
  const activeSet = new Set(activePath);
  return scenario.nodeIds
    .map((id) => nodes[id])
    .filter((n) => n && n.rememberEnabled && !activeSet.has(n.id));
}

/**
 * Build the full tree structure for graph rendering.
 */
export type TreeNode = {
  node: ScenarioNode;
  children: TreeNode[];
  depth: number;
  x: number;
  y: number;
};

export function buildTree(
  scenario: Scenario,
  nodes: Record<string, ScenarioNode>
): TreeNode | null {
  if (!scenario.rootNodeId || !nodes[scenario.rootNodeId]) return null;

  const NODE_SPACING_X = 180;
  const NODE_SPACING_Y = 100;

  let leafCounter = 0;

  function build(nodeId: string, depth: number): TreeNode | null {
    const node = nodes[nodeId];
    if (!node) return null;

    const childNodes = getChildren(nodeId, scenario, nodes);
    const childTrees = childNodes
      .map((c) => build(c.id, depth + 1))
      .filter(Boolean) as TreeNode[];

    if (childTrees.length === 0) {
      // Leaf node
      const treeNode: TreeNode = {
        node,
        children: [],
        depth,
        x: leafCounter * NODE_SPACING_X,
        y: depth * NODE_SPACING_Y,
      };
      leafCounter++;
      return treeNode;
    }

    // Position at center of children
    const minX = Math.min(...childTrees.map((c) => c.x));
    const maxX = Math.max(...childTrees.map((c) => c.x));

    return {
      node,
      children: childTrees,
      depth,
      x: (minX + maxX) / 2,
      y: depth * NODE_SPACING_Y,
    };
  }

  return build(scenario.rootNodeId, 0);
}

/**
 * Flatten a tree into an array of nodes with edges.
 */
export type FlatNode = {
  id: string;
  x: number;
  y: number;
  label: string;
  isActive: boolean;
  isOnActivePath: boolean;
  node: ScenarioNode;
};

export type Edge = {
  fromId: string;
  toId: string;
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  isActive: boolean;
};

export function flattenTree(
  tree: TreeNode | null,
  activeNodeId: string | null,
  activePath: Set<string>
): { nodes: FlatNode[]; edges: Edge[] } {
  if (!tree) return { nodes: [], edges: [] };

  const flatNodes: FlatNode[] = [];
  const edges: Edge[] = [];

  function traverse(t: TreeNode) {
    const label =
      t.node.userMessage.length > 28
        ? t.node.userMessage.slice(0, 28) + '…'
        : t.node.userMessage || 'New node';

    flatNodes.push({
      id: t.node.id,
      x: t.x,
      y: t.y,
      label,
      isActive: t.node.id === activeNodeId,
      isOnActivePath: activePath.has(t.node.id),
      node: t.node,
    });

    for (const child of t.children) {
      edges.push({
        fromId: t.node.id,
        toId: child.node.id,
        fromX: t.x,
        fromY: t.y,
        toX: child.x,
        toY: child.y,
        isActive:
          activePath.has(t.node.id) && activePath.has(child.node.id),
      });
      traverse(child);
    }
  }

  traverse(tree);
  return { nodes: flatNodes, edges };
}

/**
 * Truncate text with ellipsis.
 */
export function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '…';
}
