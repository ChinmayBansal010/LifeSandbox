import React, { useMemo, useState } from 'react';
import { Table, GitCommit, Copy, Check, Code, Eye } from 'lucide-react';

interface FormattedMessageProps {
  content: string;
}

type ContentBlock =
  | { type: 'text'; content: string }
  | { type: 'table'; headers: string[]; rows: string[][] }
  | { type: 'mermaid'; raw: string; nodes: { id: string; label: string }[]; edges: { from: string; to: string; label?: string }[] }
  | { type: 'diagram'; content: string }
  | { type: 'code'; language: string; content: string };

function parseMermaid(code: string): { nodes: { id: string; label: string }[]; edges: { from: string; to: string; label?: string }[] } {
  const nodesMap = new Map<string, string>();
  const edges: { from: string; to: string; label?: string }[] = [];

  const lines = code.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('graph') || trimmed.startsWith('flowchart') || trimmed.startsWith('sequenceDiagram') || trimmed.startsWith('classDiagram') || trimmed.startsWith('stateDiagram')) {
      continue;
    }

    // Match patterns like A[Label] --> B[Label] or A -->|label| B or A --> B
    const edgeRegex = /([A-Za-z0-9_]+)(?:\[([^\]]+)\])?\s*(?:-->|---|->|==>)\s*(?:\|([^|]+)\|)?\s*([A-Za-z0-9_]+)(?:\[([^\]]+)\])?/;
    const match = trimmed.match(edgeRegex);
    if (match) {
      const fromId = match[1];
      const fromLabel = match[2] || fromId;
      const edgeLabel = match[3];
      const toId = match[4];
      const toLabel = match[5] || toId;

      nodesMap.set(fromId, fromLabel);
      nodesMap.set(toId, toLabel);
      edges.push({ from: fromId, to: toId, label: edgeLabel });
      continue;
    }

    // Match individual node declaration: A[Label]
    const nodeRegex = /^([A-Za-z0-9_]+)\[([^\]]+)\]$/;
    const nMatch = trimmed.match(nodeRegex);
    if (nMatch) {
      nodesMap.set(nMatch[1], nMatch[2]);
    }
  }

  const nodes = Array.from(nodesMap.entries()).map(([id, label]) => ({ id, label }));
  return { nodes, edges };
}

function isAsciiDiagram(text: string): boolean {
  const lines = text.split('\n');
  if (lines.length < 2) return false;
  let diagramIndicators = 0;
  for (const line of lines) {
    if (
      line.includes('-->') ||
      line.includes('->') ||
      line.includes('|') && line.includes('+') ||
      line.includes('+--') ||
      line.includes('| v') ||
      line.includes('====') ||
      line.includes('┌') ||
      line.includes('└') ||
      line.includes('├') ||
      line.includes('│') ||
      /\[\s*[^\]]+\s*\]\s*(?:-|–|=)+>/.test(line)
    ) {
      diagramIndicators++;
    }
  }
  return diagramIndicators >= 2;
}

function parseMarkdownBlocks(rawText: string): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  const lines = rawText.split('\n');
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // 1. Code blocks or Mermaid blocks
    if (line.trim().startsWith('```')) {
      const langMatch = line.trim().match(/^```([a-zA-Z0-9_-]*)/);
      const language = langMatch ? langMatch[1].toLowerCase() : '';
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      const fullCode = codeLines.join('\n');

      if (language === 'mermaid') {
        const { nodes, edges } = parseMermaid(fullCode);
        blocks.push({ type: 'mermaid', raw: fullCode, nodes, edges });
      } else if (language === 'diagram' || isAsciiDiagram(fullCode)) {
        blocks.push({ type: 'diagram', content: fullCode });
      } else {
        blocks.push({ type: 'code', language, content: fullCode });
      }
      continue;
    }

    // 2. Markdown Tables
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        tableLines.push(lines[i].trim());
        i++;
      }

      if (tableLines.length >= 2) {
        const headerCells = tableLines[0]
          .split('|')
          .slice(1, -1)
          .map((c) => c.trim());
        const separatorLine = tableLines[1];
        const isSeparator = /^\|(?:\s*:?-+:?\s*\|)+$/.test(separatorLine);

        if (isSeparator) {
          const rows: string[][] = [];
          for (let r = 2; r < tableLines.length; r++) {
            const cells = tableLines[r]
              .split('|')
              .slice(1, -1)
              .map((c) => c.trim());
            // Align column count with headers
            while (cells.length < headerCells.length) cells.push('');
            rows.push(cells.slice(0, headerCells.length));
          }
          blocks.push({ type: 'table', headers: headerCells, rows });
          continue;
        }
      }

      // If not a valid table structure, fall back to text
      blocks.push({ type: 'text', content: tableLines.join('\n') });
      continue;
    }

    // 3. Regular text accumulator
    const textLines: string[] = [];
    while (
      i < lines.length &&
      !lines[i].trim().startsWith('```') &&
      !(lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|'))
    ) {
      textLines.push(lines[i]);
      i++;
    }

    const joinedText = textLines.join('\n');
    if (isAsciiDiagram(joinedText)) {
      blocks.push({ type: 'diagram', content: joinedText });
    } else if (joinedText.trim()) {
      blocks.push({ type: 'text', content: joinedText });
    }
  }

  return blocks;
}

function renderInlineMarkdown(text: string): React.ReactNode {
  // Simple regex for bold, inline code, and links
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Bold: **text**
    const boldMatch = remaining.match(/^(.*?)\*\*(.+?)\*\*(.*)$/s);
    // Inline code: `code`
    const codeMatch = remaining.match(/^(.*?)`([^`]+)`(.*)$/s);

    if (boldMatch && (!codeMatch || boldMatch[1].length <= codeMatch[1].length)) {
      if (boldMatch[1]) parts.push(<span key={key++}>{boldMatch[1]}</span>);
      parts.push(
        <strong key={key++} className="font-semibold text-fg">
          {boldMatch[2]}
        </strong>
      );
      remaining = boldMatch[3];
    } else if (codeMatch) {
      if (codeMatch[1]) parts.push(<span key={key++}>{codeMatch[1]}</span>);
      parts.push(
        <code
          key={key++}
          className="px-1.5 py-0.5 rounded bg-bg-secondary text-accent font-mono text-[12px] border border-border/60"
        >
          {codeMatch[2]}
        </code>
      );
      remaining = codeMatch[3];
    } else {
      parts.push(<span key={key++}>{remaining}</span>);
      break;
    }
  }

  return parts;
}

export function FormattedMessage({ content }: FormattedMessageProps) {
  const blocks = useMemo(() => parseMarkdownBlocks(content), [content]);

  return (
    <div className="space-y-3.5 text-sm leading-relaxed text-fg break-words">
      {blocks.map((block, idx) => {
        if (block.type === 'table') {
          return <TableBlock key={idx} headers={block.headers} rows={block.rows} />;
        }
        if (block.type === 'mermaid') {
          return <MermaidBlock key={idx} block={block} />;
        }
        if (block.type === 'diagram') {
          return <DiagramBlock key={idx} content={block.content} />;
        }
        if (block.type === 'code') {
          return <CodeBlock key={idx} language={block.language} content={block.content} />;
        }
        // Text block
        return <TextBlock key={idx} content={block.content} />;
      })}
    </div>
  );
}

function TableBlock({ headers, rows }: { headers: string[]; rows: string[][] }) {
  const [copied, setCopied] = useState(false);

  const copyAsTsv = () => {
    const tsv = [headers.join('\t'), ...rows.map((r) => r.join('\t'))].join('\n');
    navigator.clipboard.writeText(tsv).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-border bg-bg-secondary/40 overflow-hidden shadow-xs my-2.5">
      <div className="flex items-center justify-between px-3.5 py-2 border-b border-border bg-surface text-xs font-medium text-fg-muted">
        <div className="flex items-center gap-1.5 text-accent font-semibold">
          <Table size={14} />
          <span>Structured Comparison Table</span>
        </div>
        <button
          onClick={copyAsTsv}
          className="flex items-center gap-1 text-[11px] hover:text-fg transition-colors"
          title="Copy as TSV"
        >
          {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
          <span>{copied ? 'Copied' : 'Copy Table'}</span>
        </button>
      </div>

      <div className="overflow-x-auto max-w-full">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-border bg-surface-hover/80">
              {headers.map((h, i) => (
                <th key={i} className="px-3.5 py-2.5 font-semibold text-fg whitespace-nowrap">
                  {renderInlineMarkdown(h)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {rows.map((row, rIdx) => (
              <tr
                key={rIdx}
                className={rIdx % 2 === 0 ? 'bg-surface/50 hover:bg-surface-hover/60 transition-colors' : 'bg-surface/20 hover:bg-surface-hover/60 transition-colors'}
              >
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="px-3.5 py-2 text-fg-secondary">
                    {renderInlineMarkdown(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MermaidBlock({
  block,
}: {
  block: { raw: string; nodes: { id: string; label: string }[]; edges: { from: string; to: string; label?: string }[] };
}) {
  const [showCode, setShowCode] = useState(false);
  const [copied, setCopied] = useState(false);

  const copySource = () => {
    navigator.clipboard.writeText(block.raw).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-accent/25 bg-gradient-to-br from-surface to-bg-secondary overflow-hidden shadow-xs my-3">
      <div className="flex items-center justify-between px-3.5 py-2 border-b border-border bg-surface/90 text-xs font-medium text-fg-muted">
        <div className="flex items-center gap-1.5 text-accent font-semibold">
          <GitCommit size={14} />
          <span>Workflow Flowchart Diagram</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCode(!showCode)}
            className="flex items-center gap-1 text-[11px] hover:text-fg transition-colors"
          >
            {showCode ? <Eye size={12} /> : <Code size={12} />}
            <span>{showCode ? 'View Diagram' : 'View Code'}</span>
          </button>
          <button
            onClick={copySource}
            className="flex items-center gap-1 text-[11px] hover:text-fg transition-colors"
          >
            {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {showCode ? (
        <pre className="p-3 text-[11px] font-mono leading-relaxed text-fg-secondary overflow-x-auto whitespace-pre-wrap bg-bg-secondary/60">
          {block.raw}
        </pre>
      ) : (
        <div className="p-4 overflow-x-auto">
          {block.nodes.length > 0 ? (
            <div className="flex flex-col items-center gap-3 py-2 min-w-[280px]">
              {block.nodes.map((node, i) => {
                const outgoingEdge = block.edges.find((e) => e.from === node.id);
                return (
                  <React.Fragment key={node.id}>
                    <div className="px-4 py-2.5 rounded-xl border border-border bg-surface shadow-xs text-xs font-medium text-fg text-center min-w-[160px] max-w-[320px] transition-transform hover:scale-[1.02]">
                      <span className="font-semibold text-accent block text-[10px] uppercase tracking-wider mb-0.5">
                        Step {i + 1}
                      </span>
                      {node.label}
                    </div>
                    {outgoingEdge && i < block.nodes.length - 1 && (
                      <div className="flex flex-col items-center my-0.5 text-accent/80">
                        {outgoingEdge.label && (
                          <span className="text-[10px] bg-bg-secondary px-2 py-0.5 rounded-full border border-border text-fg-muted mb-0.5 font-mono">
                            {outgoingEdge.label}
                          </span>
                        )}
                        <svg width="18" height="20" viewBox="0 0 18 20" fill="none" className="text-accent">
                          <line x1="9" y1="0" x2="9" y2="14" stroke="currentColor" strokeWidth="2" />
                          <polygon points="9,20 4,13 14,13" fill="currentColor" />
                        </svg>
                      </div>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          ) : (
            <pre className="text-xs font-mono text-fg-secondary whitespace-pre-wrap">{block.raw}</pre>
          )}
        </div>
      )}
    </div>
  );
}

function DiagramBlock({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(content).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-accent/20 bg-bg-secondary/70 overflow-hidden my-2.5 shadow-xs">
      <div className="flex items-center justify-between px-3.5 py-1.5 border-b border-border bg-surface text-xs font-medium text-fg-muted">
        <div className="flex items-center gap-1.5 text-accent font-semibold">
          <GitCommit size={14} />
          <span>Flow Diagram</span>
        </div>
        <button
          onClick={copy}
          className="flex items-center gap-1 text-[11px] hover:text-fg transition-colors"
        >
          {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-[12px] font-mono leading-relaxed text-fg max-h-80 select-text">
        {content}
      </pre>
    </div>
  );
}

function CodeBlock({ language, content }: { language: string; content: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(content).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-border bg-bg-secondary overflow-hidden my-2.5 text-xs">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-surface text-[11px] font-medium text-fg-muted">
        <span className="font-mono">{language || 'code'}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1 hover:text-fg transition-colors"
        >
          {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="p-3 overflow-x-auto font-mono text-[11px] leading-relaxed text-fg-secondary max-h-72 whitespace-pre-wrap">
        {content}
      </pre>
    </div>
  );
}

function TextBlock({ content }: { content: string }) {
  const paragraphs = content.split('\n\n');

  return (
    <div className="space-y-2">
      {paragraphs.map((p, pIdx) => {
        const trimmed = p.trim();
        if (!trimmed) return null;

        // Headings
        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={pIdx} className="text-sm font-bold text-fg pt-1 pb-0.5">
              {renderInlineMarkdown(trimmed.replace(/^###\s+/, ''))}
            </h4>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={pIdx} className="text-base font-bold text-fg pt-1.5 pb-0.5">
              {renderInlineMarkdown(trimmed.replace(/^##\s+/, ''))}
            </h3>
          );
        }
        if (trimmed.startsWith('# ')) {
          return (
            <h2 key={pIdx} className="text-lg font-bold text-fg pt-2 pb-1">
              {renderInlineMarkdown(trimmed.replace(/^#\s+/, ''))}
            </h2>
          );
        }

        // Bullet lists
        if (trimmed.split('\n').every((l) => /^\s*[-*•]\s+/.test(l) || !l.trim())) {
          const listItems = trimmed
            .split('\n')
            .filter((l) => l.trim())
            .map((l) => l.replace(/^\s*[-*•]\s+/, ''));
          return (
            <ul key={pIdx} className="list-disc pl-5 space-y-1 text-fg-secondary">
              {listItems.map((item, itemIdx) => (
                <li key={itemIdx}>{renderInlineMarkdown(item)}</li>
              ))}
            </ul>
          );
        }

        // Numbered lists
        if (trimmed.split('\n').every((l) => /^\s*\d+\.\s+/.test(l) || !l.trim())) {
          const listItems = trimmed
            .split('\n')
            .filter((l) => l.trim())
            .map((l) => l.replace(/^\s*\d+\.\s+/, ''));
          return (
            <ol key={pIdx} className="list-decimal pl-5 space-y-1 text-fg-secondary">
              {listItems.map((item, itemIdx) => (
                <li key={itemIdx}>{renderInlineMarkdown(item)}</li>
              ))}
            </ol>
          );
        }

        // Regular paragraph
        return (
          <p key={pIdx} className="text-fg-secondary leading-relaxed whitespace-pre-line">
            {renderInlineMarkdown(p)}
          </p>
        );
      })}
    </div>
  );
}
