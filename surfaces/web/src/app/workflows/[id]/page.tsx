import Link from 'next/link';
import { notFound } from 'next/navigation';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface WorkflowNode {
  id: string;
  capability: string;
  label: string;
  parameters?: Record<string, unknown>;
  position?: { x: number; y: number };
}

interface WorkflowEdge {
  source: string;
  target: string;
  label?: string;
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  created_at: string;
  updated_at: string;
  tags: string[];
}

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function WorkflowDetailPage({ params }: PageProps) {
  const { id } = await params;
  let workflow: Workflow | null = null;
  let errorMsg: string | null = null;

  try {
    const res = await fetch(`${API_BASE}/api/v1/workflows/${id}`, {
      cache: 'no-store',
    });
    if (res.status === 404) notFound();
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    workflow = (await res.json()) as Workflow;
  } catch (e) {
    errorMsg = e instanceof Error ? e.message : String(e);
  }

  if (errorMsg) {
    return (
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <p style={{ color: '#ef4444' }}>Failed to load workflow: {errorMsg}</p>
        <Link href="/workflows" style={{ color: 'var(--color-accent)' }}>
          ← Back to workflows
        </Link>
      </main>
    );
  }

  if (!workflow) return null;

  // Topological layout: assign positions if missing
  const NODE_W = 200;
  const NODE_H = 80;
  const H_GAP = 80;
  const V_GAP = 60;

  // Group nodes by topological level
  const inDegree: Record<string, number> = {};
  const adj: Record<string, string[]> = {};
  workflow.nodes.forEach((n) => {
    inDegree[n.id] = 0;
    adj[n.id] = [];
  });
  workflow.edges.forEach((e) => {
    adj[e.source]?.push(e.target);
    inDegree[e.target] = (inDegree[e.target] ?? 0) + 1;
  });
  const levels: Record<string, number> = {};
  let queue = workflow.nodes.filter((n) => (inDegree[n.id] ?? 0) === 0).map((n) => n.id);
  queue.forEach((id) => (levels[id] = 0));
  while (queue.length > 0) {
    const next: string[] = [];
    queue.forEach((id) => {
      (adj[id] ?? []).forEach((nbr) => {
        levels[nbr] = Math.max((levels[nbr] ?? 0), (levels[id] ?? 0) + 1);
        next.push(nbr);
      });
    });
    queue = next;
  }
  const levelGroups: Record<number, string[]> = {};
  Object.entries(levels).forEach(([nid, lvl]) => {
    (levelGroups[lvl] ??= []).push(nid);
  });

  const positions: Record<string, { x: number; y: number }> = {};
  Object.entries(levelGroups).forEach(([lvl, ids]) => {
    const level = Number(lvl);
    ids.forEach((nid, idx) => {
      positions[nid] = {
        x: 40 + level * (NODE_W + H_GAP),
        y: 40 + idx * (NODE_H + V_GAP),
      };
    });
  });

  const SVG_W =
    Math.max(...Object.values(positions).map((p) => p.x), 0) + NODE_W + 60;
  const SVG_H =
    Math.max(...Object.values(positions).map((p) => p.y), 0) + NODE_H + 60;

  return (
    <main
      style={{
        maxWidth: '1400px',
        margin: '0 auto',
        padding: '2rem 1.5rem',
      }}
    >
      <Link
        href="/workflows"
        style={{
          color: 'var(--color-muted)',
          fontSize: '0.8rem',
          textDecoration: 'none',
        }}
      >
        ← Back to workflows
      </Link>

      <header style={{ marginTop: '0.5rem', marginBottom: '1.5rem' }}>
        <h1
          style={{
            fontSize: '1.5rem',
            fontWeight: 700,
            margin: 0,
            color: 'var(--color-fg)',
          }}
        >
          {workflow.name}
        </h1>
        {workflow.description && (
          <p
            style={{
              color: 'var(--color-muted)',
              marginTop: '0.25rem',
              fontSize: '0.875rem',
            }}
          >
            {workflow.description}
          </p>
        )}
      </header>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 320px',
          gap: '1.5rem',
        }}
      >
        {/* DAG canvas */}
        <div
          style={{
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: '0.5rem',
            padding: '1rem',
            overflow: 'auto',
          }}
        >
          <svg
            width={SVG_W}
            height={SVG_H}
            style={{ display: 'block' }}
          >
            {/* Edges */}
            {workflow.edges.map((edge, i) => {
              const src = positions[edge.source];
              const tgt = positions[edge.target];
              if (!src || !tgt) return null;
              const sx = src.x + NODE_W;
              const sy = src.y + NODE_H / 2;
              const tx = tgt.x;
              const ty = tgt.y + NODE_H / 2;
              const midX = (sx + tx) / 2;
              return (
                <g key={`edge-${i}`}>
                  <path
                    d={`M ${sx} ${sy} C ${midX} ${sy}, ${midX} ${ty}, ${tx} ${ty}`}
                    stroke="var(--color-muted)"
                    strokeWidth="1.5"
                    fill="none"
                  />
                  <polygon
                    points={`${tx},${ty} ${tx - 8},${ty - 4} ${tx - 8},${ty + 4}`}
                    fill="var(--color-muted)"
                  />
                  {edge.label && (
                    <text
                      x={midX}
                      y={(sy + ty) / 2 - 4}
                      fill="var(--color-muted)"
                      fontSize="10"
                      textAnchor="middle"
                    >
                      {edge.label}
                    </text>
                  )}
                </g>
              );
            })}
            {/* Nodes */}
            {workflow.nodes.map((node) => {
              const pos = positions[node.id];
              if (!pos) return null;
              return (
                <g key={`node-${node.id}`}>
                  <rect
                    x={pos.x}
                    y={pos.y}
                    width={NODE_W}
                    height={NODE_H}
                    rx="8"
                    fill="var(--color-card)"
                    stroke="var(--color-accent)"
                    strokeWidth="1.5"
                  />
                  <text
                    x={pos.x + 12}
                    y={pos.y + 22}
                    fill="var(--color-fg)"
                    fontSize="13"
                    fontWeight="600"
                  >
                    {node.label.length > 22
                      ? `${node.label.slice(0, 22)}…`
                      : node.label}
                  </text>
                  <text
                    x={pos.x + 12}
                    y={pos.y + 42}
                    fill="var(--color-muted)"
                    fontSize="11"
                    fontFamily="monospace"
                  >
                    {node.capability}
                  </text>
                  <text
                    x={pos.x + 12}
                    y={pos.y + 62}
                    fill="var(--color-muted)"
                    fontSize="10"
                  >
                    id: {node.id}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Sidebar: node list + metadata */}
        <aside
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
          }}
        >
          <div
            style={{
              backgroundColor: 'var(--color-card)',
              border: '1px solid var(--color-border)',
              borderRadius: '0.5rem',
              padding: '1rem',
            }}
          >
            <h3
              style={{
                margin: 0,
                fontSize: '0.875rem',
                fontWeight: 600,
                marginBottom: '0.75rem',
              }}
            >
              Nodes ({workflow.nodes.length})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {workflow.nodes.map((node) => (
                <div
                  key={node.id}
                  style={{
                    fontSize: '0.75rem',
                    padding: '0.5rem',
                    backgroundColor: 'var(--color-bg)',
                    borderRadius: '0.25rem',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: '0.15rem' }}>
                    {node.label}
                  </div>
                  <div style={{ color: 'var(--color-muted)', fontFamily: 'monospace' }}>
                    {node.capability}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div
            style={{
              backgroundColor: 'var(--color-card)',
              border: '1px solid var(--color-border)',
              borderRadius: '0.5rem',
              padding: '1rem',
              fontSize: '0.75rem',
              color: 'var(--color-muted)',
            }}
          >
            <div>Created: {new Date(workflow.created_at).toLocaleString()}</div>
            <div>Updated: {new Date(workflow.updated_at).toLocaleString()}</div>
            {workflow.tags.length > 0 && (
              <div style={{ marginTop: '0.5rem' }}>
                Tags: {workflow.tags.join(', ')}
              </div>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
