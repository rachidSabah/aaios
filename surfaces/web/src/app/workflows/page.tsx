import Link from 'next/link';

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

export default async function WorkflowsPage() {
  let workflows: Workflow[] = [];
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/workflows`, {
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as { workflows: Workflow[] };
    workflows = data.workflows ?? [];
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main
      style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '2rem 1.5rem',
      }}
    >
      <header
        style={{
          marginBottom: '2rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        <div>
          <h1
            style={{
              fontSize: '1.75rem',
              fontWeight: 700,
              margin: 0,
              color: 'var(--color-fg)',
            }}
          >
            Workflows
          </h1>
          <p
            style={{
              color: 'var(--color-muted)',
              marginTop: '0.25rem',
              fontSize: '0.875rem',
            }}
          >
            Visual DAG builder for multi-step agent pipelines
          </p>
        </div>
        <button
          type="button"
          style={{
            backgroundColor: 'var(--color-accent)',
            color: 'var(--color-accent-fg)',
            border: 'none',
            borderRadius: '0.375rem',
            padding: '0.5rem 1rem',
            fontSize: '0.875rem',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          + New Workflow
        </button>
      </header>

      {error && (
        <div
          style={{
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: '0.5rem',
            padding: '1rem 1.5rem',
            marginBottom: '1.5rem',
            color: '#ef4444',
            fontSize: '0.875rem',
          }}
        >
          Could not reach API server: {error}. Start it with{' '}
          <code>aaios dev</code>.
        </div>
      )}

      {workflows.length === 0 && !error ? (
        <div
          style={{
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: '0.5rem',
            padding: '3rem 1.5rem',
            textAlign: 'center',
            color: 'var(--color-muted)',
          }}
        >
          <p style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>
            No workflows yet.
          </p>
          <p style={{ fontSize: '0.8rem' }}>
            Create your first workflow to chain agents into reusable pipelines.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: '1rem',
          }}
        >
          {workflows.map((wf) => (
            <Link
              key={wf.id}
              href={`/workflows/${wf.id}`}
              style={{
                backgroundColor: 'var(--color-card)',
                border: '1px solid var(--color-border)',
                borderRadius: '0.5rem',
                padding: '1.25rem',
                textDecoration: 'none',
                color: 'var(--color-fg)',
                display: 'block',
              }}
            >
              <h3
                style={{
                  margin: 0,
                  fontSize: '1rem',
                  fontWeight: 600,
                  marginBottom: '0.25rem',
                }}
              >
                {wf.name}
              </h3>
              {wf.description && (
                <p
                  style={{
                    margin: 0,
                    fontSize: '0.8rem',
                    color: 'var(--color-muted)',
                    marginBottom: '0.75rem',
                  }}
                >
                  {wf.description}
                </p>
              )}
              <div
                style={{
                  display: 'flex',
                  gap: '1rem',
                  fontSize: '0.75rem',
                  color: 'var(--color-muted)',
                }}
              >
                <span>{wf.nodes.length} nodes</span>
                <span>{wf.edges.length} edges</span>
              </div>
              {wf.tags.length > 0 && (
                <div
                  style={{
                    marginTop: '0.5rem',
                    display: 'flex',
                    gap: '0.25rem',
                    flexWrap: 'wrap',
                  }}
                >
                  {wf.tags.map((tag) => (
                    <span
                      key={tag}
                      style={{
                        fontSize: '0.7rem',
                        padding: '0.1rem 0.4rem',
                        backgroundColor: 'var(--color-bg)',
                        border: '1px solid var(--color-border)',
                        borderRadius: '0.25rem',
                        color: 'var(--color-muted)',
                      }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
