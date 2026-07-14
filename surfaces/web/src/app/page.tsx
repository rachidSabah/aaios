import { checkApiHealth } from '@/lib/api';

export default async function HomePage() {
  const health = await checkApiHealth().catch((err) => ({
    status: 'unreachable',
    error: err instanceof Error ? err.message : String(err),
  }));

  return (
    <main
      style={{
        maxWidth: '900px',
        margin: '0 auto',
        padding: '4rem 1.5rem',
      }}
    >
      <header style={{ marginBottom: '3rem' }}>
        <h1
          style={{
            fontSize: '2.5rem',
            fontWeight: 700,
            margin: 0,
            color: 'var(--color-fg)',
          }}
        >
          Agentic AI Operating System
        </h1>
        <p
          style={{
            fontSize: '1.125rem',
            color: 'var(--color-muted)',
            marginTop: '0.5rem',
          }}
        >
          Windows-first. Modular. Capability-based. v0.1.0-dev (Phase 2 —
          repository structure)
        </p>
      </header>

      <section
        style={{
          backgroundColor: 'var(--color-card)',
          border: '1px solid var(--color-border)',
          borderRadius: '0.5rem',
          padding: '1.5rem',
          marginBottom: '1.5rem',
        }}
      >
        <h2
          style={{
            fontSize: '1.25rem',
            fontWeight: 600,
            marginTop: 0,
            marginBottom: '1rem',
          }}
        >
          API health
        </h2>
        <dl style={{ margin: 0, display: 'grid', gap: '0.5rem' }}>
          <div>
            <dt
              style={{
                display: 'inline-block',
                width: '120px',
                color: 'var(--color-muted)',
              }}
            >
              Status:
            </dt>
            <dd
              style={{
                display: 'inline',
                margin: 0,
                color:
                  health.status === 'ok'
                    ? 'var(--color-accent)'
                    : '#dc2626',
                fontWeight: 600,
              }}
            >
              {health.status}
            </dd>
          </div>
          {'version' in health && (
            <div>
              <dt
                style={{
                  display: 'inline-block',
                  width: '120px',
                  color: 'var(--color-muted)',
                }}
              >
                Version:
              </dt>
              <dd style={{ display: 'inline', margin: 0 }}>
                {health.version}
              </dd>
            </div>
          )}
          {'error' in health && (
            <div>
              <dt
                style={{
                  display: 'inline-block',
                  width: '120px',
                  color: 'var(--color-muted)',
                }}
              >
                Error:
              </dt>
              <dd style={{ display: 'inline', margin: 0, color: '#dc2626' }}>
                {health.error}
              </dd>
            </div>
          )}
        </dl>
      </section>

      <section
        style={{
          color: 'var(--color-muted)',
          fontSize: '0.875rem',
          lineHeight: 1.6,
        }}
      >
        <p>
          This is a Phase 2 stub of the AAiOS dashboard. The full dashboard
          (tasks, agents, memory, plugins, marketplace, providers, workflows,
          prompts, logs, audit, telemetry, settings) lands in Phase 12.
        </p>
        <p style={{ marginTop: '0.75rem' }}>
          See <code>docs/architecture/09-roadmap.md</code> for the build plan.
        </p>
      </section>
    </main>
  );
}
