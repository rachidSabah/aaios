import { checkApiHealth } from '@/lib/api';

export default async function HomePage() {
  const health = await checkApiHealth().catch((err) => ({
    status: 'unreachable',
    error: err instanceof Error ? err.message : String(err),
  }));

  const agents = await fetch(`${process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000'}/api/v1/agents`, {
    cache: 'no-store',
  })
    .then((res) => res.json())
    .catch(() => ({ agents: [] }));

  const providers = await fetch(`${process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000'}/api/v1/providers`, {
    cache: 'no-store',
  })
    .then((res) => res.json())
    .catch(() => ({ providers: [] }));

  return (
    <main
      style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '2rem 1.5rem',
      }}
    >
      <header style={{ marginBottom: '2rem' }}>
        <h1
          style={{
            fontSize: '2rem',
            fontWeight: 700,
            margin: 0,
            color: 'var(--color-fg)',
          }}
        >
          AAiOS Dashboard
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem' }}>
          Agentic AI Operating System — v2.0 (Dashboard Agent)
        </p>
      </header>

      {/* Health status */}
      <section
        style={{
          backgroundColor: 'var(--color-card)',
          border: '1px solid var(--color-border)',
          borderRadius: '0.5rem',
          padding: '1rem 1.5rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
        }}
      >
        <div
          style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor:
              health.status === 'ok' ? '#22c55e' : '#ef4444',
          }}
        />
        <div>
          <strong>API Server:</strong>{' '}
          <span style={{ color: health.status === 'ok' ? '#22c55e' : '#ef4444' }}>
            {health.status}
          </span>
          {'status' in health && (
            <span style={{ color: 'var(--color-muted)', marginLeft: '0.5rem' }}>
              v{(health as { version?: string }).version ?? '?'}
            </span>
          )}
        </div>
      </section>

      {/* Agents */}
      <section
        style={{
          backgroundColor: 'var(--color-card)',
          border: '1px solid var(--color-border)',
          borderRadius: '0.5rem',
          padding: '1.5rem',
          marginBottom: '1.5rem',
        }}
      >
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginTop: 0, marginBottom: '1rem' }}>
          Registered Agents ({agents.agents?.length ?? 0})
        </h2>
        {agents.agents && agents.agents.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                <th style={{ textAlign: 'left', padding: '0.5rem' }}>Agent</th>
                <th style={{ textAlign: 'left', padding: '0.5rem' }}>Type</th>
                <th style={{ textAlign: 'left', padding: '0.5rem' }}>Health</th>
                <th style={{ textAlign: 'left', padding: '0.5rem' }}>Capabilities</th>
              </tr>
            </thead>
            <tbody>
              {agents.agents.map((agent: Record<string, unknown>) => (
                <tr key={agent.agent_id as string} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '0.5rem' }}>{agent.implementation_name as string}</td>
                  <td style={{ padding: '0.5rem', color: 'var(--color-muted)' }}>{agent.agent_type as string}</td>
                  <td style={{ padding: '0.5rem' }}>
                    <span style={{ color: agent.health === 'healthy' ? '#22c55e' : '#ef4444' }}>
                      {agent.health as string}
                    </span>
                  </td>
                  <td style={{ padding: '0.5rem', color: 'var(--color-muted)' }}>
                    {(agent.capabilities as string[])?.slice(0, 3).join(', ')}
                    {(agent.capabilities as string[])?.length > 3 ? '...' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ color: 'var(--color-muted)', fontSize: '0.875rem' }}>
            No agents registered. Start the API server and register agents.
          </p>
        )}
      </section>

      {/* Providers */}
      <section
        style={{
          backgroundColor: 'var(--color-card)',
          border: '1px solid var(--color-border)',
          borderRadius: '0.5rem',
          padding: '1.5rem',
          marginBottom: '1.5rem',
        }}
      >
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginTop: 0, marginBottom: '1rem' }}>
          LLM Providers ({providers.providers?.length ?? 0})
        </h2>
        {providers.providers && providers.providers.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                <th style={{ textAlign: 'left', padding: '0.5rem' }}>Provider</th>
                <th style={{ textAlign: 'left', padding: '0.5rem' }}>Status</th>
                <th style={{ textAlign: 'left', padding: '0.5rem' }}>Success Rate</th>
                <th style={{ textAlign: 'left', padding: '0.5rem' }}>Avg Latency</th>
              </tr>
            </thead>
            <tbody>
              {providers.providers.map((p: Record<string, unknown>) => (
                <tr key={p.provider as string} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '0.5rem' }}>{p.provider as string}</td>
                  <td style={{ padding: '0.5rem' }}>
                    <span style={{ color: p.status === 'healthy' ? '#22c55e' : '#ef4444' }}>
                      {p.status as string}
                    </span>
                  </td>
                  <td style={{ padding: '0.5rem' }}>{((p.success_rate as number) * 100).toFixed(1)}%</td>
                  <td style={{ padding: '0.5rem' }}>{(p.avg_latency_s as number).toFixed(2)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ color: 'var(--color-muted)', fontSize: '0.875rem' }}>
            No providers configured.
          </p>
        )}
      </section>

      {/* Quick links */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: '1rem',
        }}
      >
        {[
          { label: 'Tasks', desc: 'View active tasks' },
          { label: 'Memory', desc: 'Explore memory' },
          { label: 'Plugins', desc: 'Manage plugins' },
          { label: 'Audit Log', desc: 'Security audit trail' },
          { label: 'Costs', desc: 'Cost analytics' },
          { label: 'Settings', desc: 'Configuration' },
        ].map((card) => (
          <div
            key={card.label}
            style={{
              backgroundColor: 'var(--color-card)',
              border: '1px solid var(--color-border)',
              borderRadius: '0.5rem',
              padding: '1rem',
              cursor: 'pointer',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{card.label}</div>
            <div style={{ color: 'var(--color-muted)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
              {card.desc}
            </div>
          </div>
        ))}
      </section>

      <footer style={{ marginTop: '2rem', color: 'var(--color-muted)', fontSize: '0.75rem' }}>
        AAiOS v2.0 — Dashboard Agent with workflow builder, live monitoring, and analytics.
      </footer>
    </main>
  );
}
