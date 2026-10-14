/* ─── Scenario Graph: Interactive SVG tree visualization ───────────── */

import { useMemo, useRef, useState, useCallback, useEffect } from 'react';
import { ZoomIn, ZoomOut, Maximize2, GitBranch } from 'lucide-react';
import type { Scenario, ScenarioNode } from '../types';
import {
  buildTree,
  flattenTree,
  getAncestorPath,
  truncate,
} from '../graph-utils';

type ScenarioGraphProps = {
  scenario: Scenario;
  nodes: Record<string, ScenarioNode>;
  onSelectNode: (nodeId: string) => void;
};

const NODE_RADIUS = 24;
const PADDING = 60;

export default function ScenarioGraph({
  scenario,
  nodes,
  onSelectNode,
}: ScenarioGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // Pan and zoom state
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 600, h: 400 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, vx: 0, vy: 0 });

  const activePath = useMemo(() => {
    if (!scenario.activeNodeId) return new Set<string>();
    return new Set(getAncestorPath(scenario.activeNodeId, nodes));
  }, [scenario.activeNodeId, nodes]);

  const tree = useMemo(
    () => buildTree(scenario, nodes),
    [scenario, nodes]
  );

  const { nodes: flatNodes, edges } = useMemo(
    () => flattenTree(tree, scenario.activeNodeId, activePath),
    [tree, scenario.activeNodeId, activePath]
  );

  // Compute bounds and set initial viewBox
  useEffect(() => {
    if (flatNodes.length === 0) return;
    const minX = Math.min(...flatNodes.map((n) => n.x)) - PADDING;
    const maxX = Math.max(...flatNodes.map((n) => n.x)) + PADDING;
    const minY = Math.min(...flatNodes.map((n) => n.y)) - PADDING;
    const maxY = Math.max(...flatNodes.map((n) => n.y)) + PADDING;
    setViewBox({
      x: minX,
      y: minY,
      w: Math.max(maxX - minX, 200),
      h: Math.max(maxY - minY, 200),
    });
  }, [flatNodes]);

  const zoom = useCallback(
    (factor: number) => {
      setViewBox((vb) => {
        const cx = vb.x + vb.w / 2;
        const cy = vb.y + vb.h / 2;
        const nw = vb.w * factor;
        const nh = vb.h * factor;
        return { x: cx - nw / 2, y: cy - nh / 2, w: nw, h: nh };
      });
    },
    []
  );

  const fitToView = useCallback(() => {
    if (flatNodes.length === 0) return;
    const minX = Math.min(...flatNodes.map((n) => n.x)) - PADDING;
    const maxX = Math.max(...flatNodes.map((n) => n.x)) + PADDING;
    const minY = Math.min(...flatNodes.map((n) => n.y)) - PADDING;
    const maxY = Math.max(...flatNodes.map((n) => n.y)) + PADDING;
    setViewBox({
      x: minX,
      y: minY,
      w: Math.max(maxX - minX, 200),
      h: Math.max(maxY - minY, 200),
    });
  }, [flatNodes]);

  // Pan handlers
  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      setIsDragging(true);
      dragStart.current = {
        x: e.clientX,
        y: e.clientY,
        vx: viewBox.x,
        vy: viewBox.y,
      };
      (e.target as SVGElement).setPointerCapture?.(e.pointerId);
    },
    [viewBox.x, viewBox.y]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isDragging) return;
      const container = containerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const scaleX = viewBox.w / rect.width;
      const scaleY = viewBox.h / rect.height;
      const dx = (e.clientX - dragStart.current.x) * scaleX;
      const dy = (e.clientY - dragStart.current.y) * scaleY;
      setViewBox((vb) => ({
        ...vb,
        x: dragStart.current.vx - dx,
        y: dragStart.current.vy - dy,
      }));
    },
    [isDragging, viewBox.w, viewBox.h]
  );

  const handlePointerUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY > 0 ? 1.1 : 0.9;
      zoom(factor);
    },
    [zoom]
  );

  if (flatNodes.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center px-6">
        <div className="w-10 h-10 rounded-lg bg-bg-tertiary flex items-center justify-center mb-3">
          <GitBranch size={18} className="text-fg-muted" />
        </div>
        <p className="text-xs text-fg-muted">
          Your conversation timeline will appear here
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col" ref={containerRef}>
      {/* Graph header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        <span className="text-xs font-medium text-fg-secondary">
          Timeline
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => zoom(0.8)}
            className="p-1 rounded hover:bg-surface-hover text-fg-muted hover:text-fg transition-colors"
            aria-label="Zoom in"
          >
            <ZoomIn size={14} />
          </button>
          <button
            onClick={() => zoom(1.25)}
            className="p-1 rounded hover:bg-surface-hover text-fg-muted hover:text-fg transition-colors"
            aria-label="Zoom out"
          >
            <ZoomOut size={14} />
          </button>
          <button
            onClick={fitToView}
            className="p-1 rounded hover:bg-surface-hover text-fg-muted hover:text-fg transition-colors"
            aria-label="Fit to view"
          >
            <Maximize2 size={14} />
          </button>
        </div>
      </div>

      {/* SVG canvas */}
      <div className="flex-1 overflow-hidden">
        <svg
          ref={svgRef}
          className={`w-full h-full ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
          viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp}
          onWheel={handleWheel}
          role="img"
          aria-label="Scenario timeline graph"
        >
          {/* Edges */}
          {edges.map((edge) => (
            <line
              key={`${edge.fromId}-${edge.toId}`}
              x1={edge.fromX}
              y1={edge.fromY + NODE_RADIUS}
              x2={edge.toX}
              y2={edge.toY - NODE_RADIUS}
              strokeWidth={edge.isActive ? 2 : 1.5}
              className={
                edge.isActive
                  ? 'stroke-edge-active'
                  : 'stroke-edge'
              }
              strokeLinecap="round"
            />
          ))}

          {/* Nodes */}
          {flatNodes.map((fn) => {
            const isHovered = hoveredId === fn.id;
            return (
              <g
                key={fn.id}
                className="cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectNode(fn.id);
                }}
                onPointerEnter={() => setHoveredId(fn.id)}
                onPointerLeave={() => setHoveredId(null)}
                tabIndex={0}
                role="button"
                aria-label={`Node: ${fn.label}`}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectNode(fn.id);
                  }
                }}
              >
                {/* Outer ring for active node */}
                {fn.isActive && (
                  <circle
                    cx={fn.x}
                    cy={fn.y}
                    r={NODE_RADIUS + 4}
                    className="fill-none stroke-node-active"
                    strokeWidth={2}
                    strokeDasharray="4 3"
                  />
                )}

                {/* Main circle */}
                <circle
                  cx={fn.x}
                  cy={fn.y}
                  r={NODE_RADIUS}
                  className={
                    fn.isActive
                      ? 'fill-node-active'
                      : fn.isOnActivePath
                      ? 'fill-node'
                      : 'fill-node-inactive'
                  }
                  opacity={isHovered ? 0.9 : 1}
                />

                {/* Node index number */}
                <text
                  x={fn.x}
                  y={fn.y + 1}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-white text-[11px] font-semibold pointer-events-none select-none"
                >
                  {flatNodes.indexOf(fn) + 1}
                </text>

                {/* Label */}
                <text
                  x={fn.x}
                  y={fn.y + NODE_RADIUS + 14}
                  textAnchor="middle"
                  className={`text-[9px] pointer-events-none select-none ${
                    fn.isOnActivePath ? 'fill-fg' : 'fill-fg-muted'
                  }`}
                >
                  {truncate(fn.label, 20)}
                </text>

                {/* Remember indicator */}
                {fn.node.rememberEnabled && (
                  <circle
                    cx={fn.x + NODE_RADIUS - 4}
                    cy={fn.y - NODE_RADIUS + 4}
                    r={5}
                    className="fill-accent stroke-bg"
                    strokeWidth={2}
                  />
                )}

                {/* Tooltip on hover */}
                {isHovered && (
                  <foreignObject
                    x={fn.x - 110}
                    y={fn.y - NODE_RADIUS - 52}
                    width={220}
                    height={44}
                    className="pointer-events-none"
                  >
                    <div className="bg-fg text-fg-inverse text-[10px] px-2.5 py-1.5 rounded-md shadow-lg leading-snug text-center">
                      <div className="font-medium truncate">{truncate(fn.node.userMessage, 50)}</div>
                      <div className="text-[9px] opacity-70 mt-0.5">
                        {new Date(fn.node.createdAt).toLocaleString()}
                      </div>
                    </div>
                  </foreignObject>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
