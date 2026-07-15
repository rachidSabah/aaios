const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface MonitorSnapshot {
  timestamp: number;
  total_events: number;
  events_last_minute: number;
  events_last_hour: number;
  active_agents: string[];
  active_capabilities: string[];
  recent_events: Array<{
    timestamp: number;
    event_type: string;
    agent_id: string | null;
    capability: string | null;
    success: boolean | null;
    duration_s: number | null;
  }>;
  buckets_last_hour: Array<{
    bucket_start: number;
    sample_count: number;
    success_count: number;
    failure_count: number;
    success_rate: number;
    avg_duration_s: number;
    total_cost_usd: number;
  }>;
}

export default async function MonitoringPage() {
  let snapshot: MonitorSnapshot | null = null;
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/monitor/snapshot`, {
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    snapshot = (await res.json()) as MonitorSnapshot;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  if (error || !snapshot) {
    return (
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <h1
          style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            margin: 0,
            marginBottom: '1rem',
          }}
        >
          Live Monitoring
        </h1>
        <div
          style={{
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: '0.5rem',
            padding: '1rem 1.5rem',
            color: '#ef4444',
            fontSize: '0.875rem',
          }}
        >
          Could not reach API server: {error}. Start it with <code>aaios dev</code>.
        </div>
      </main>
    );
  }

  // Sparkline: events per bucket (last 30 buckets)
  const recentBuckets = snapshot.buckets_last_hour.slice(-30);
  const maxCount = Math.max(1, ...recentBuckets.map((b) => b.sample_count));
  const sparklineW = 600;
  const sparklineH = 100;
  const barW = recentBuckets.length > 0 ? sparklineW / recentBuckets.length : 1;

  return (
    <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1
          style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            margin: 0,
            color: 'var(--color-fg)',
          }}
        >
          Live Monitoring
        </h1>
        <p
          style={{
            color: 'var(--color-muted)',
            marginTop: '0.25rem',
            fontSize: '0.875rem',
          }}
        >
          Real-time view of events, agents, and capabilities
        </p>
      </header>

      {/* KPI cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <KpiCard label="Events (total)" value={snapshot.total_events.toString()} />
        <KpiCard label="Events (last min)" value={snapshot.events_last_minute.toString()} />
        <KpiCard label="Events (last hr)" value={snapshot.events_last_hour.toString()} />
        <KpiCard label="Active Agents" value={snapshot.active_agents.length.toString()} />
        <KpiCard
          label="Active Capabilities"
          value={snapshot.active_capabilities.length.toString()}
        />
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr',
          gap: '1.5rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Throughput chart */}
        <div
          style={{
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: '0.5rem',
            padding: '1.5rem',
          }}
        >
          <h3
            style={{
              margin: 0,
              fontSize: '0.95rem',
              fontWeight: 600,
              marginBottom: '1rem',
            }}
          >
            Throughput (last 30 minutes)
          </h3>
          {recentBuckets.length === 0 ? (
            <p style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
              No events yet.
            </p>
          ) : (
            <svg width={sparklineW} height={sparklineH} style={{ display: 'block' }}>
              {recentBuckets.map((b, i) => {
                const h = (b.sample_count / maxCount) * (sparklineH - 10);
                return (
                  <rect
                    key={i}
                    x={i * barW + 1}
                    y={sparklineH - h}
                    width={Math.max(1, barW - 2)}
                    height={h}
                    fill="var(--color-accent)"
                    opacity={0.7}
                  />
                );
              })}
            </svg>
          )}
        </div>

        {/* Active agents */}
        <div
          style={{
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: '0.5rem',
            padding: '1.5rem',
          }}
        >
          <h3
            style={{
              margin: 0,
              fontSize: '0.95rem',
              fontWeight: 600,
              marginBottom: '0.75rem',
            }}
          >
            Active Agents
          </h3>
          {snapshot.active_agents.length === 0 ? (
            <p style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
              No active agents in the last hour.
            </p>
          ) : (
            <ul
              style={{
                margin: 0,
                padding: 0,
                listStyle: 'none',
                fontSize: '0.8rem',
              }}
            >
              {snapshot.active_agents.map((a) => (
                <li
                  key={a}
                  style={{
                    padding: '0.3rem 0',
                    borderBottom: '1px solid var(--color-border)',
                    fontFamily: 'monospace',
                  }}
                >
                  {a}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Recent events table */}
      <div
        style={{
          backgroundColor: 'var(--color-card)',
          border: '1px solid var(--color-border)',
          borderRadius: '0.5rem',
          padding: '1.5rem',
        }}
      >
        <h3
          style={{
            margin: 0,
            fontSize: '0.95rem',
            fontWeight: 600,
            marginBottom: '1rem',
          }}
        >
          Recent Events
        </h3>
        {snapshot.recent_events.length === 0 ? (
          <p style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
            No events recorded yet.
          </p>
        ) : (
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.8rem',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                <th style={thStyle}>Time</th>
                <th style={thStyle}>Topic</th>
                <th style={thStyle}>Agent</th>
                <th style={thStyle}>Capability</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Duration</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.recent_events.map((e, i) => (
                <tr
                  key={i}
                  style={{ borderBottom: '1px solid var(--color-border)' }}
                >
                  <td style={tdStyle}>
                    {new Date(e.timestamp * 1000).toLocaleTimeString()}
                  </td>
                  <td style={{ ...tdStyle, fontFamily: 'monospace' }}>
                    {e.event_type}
                  </td>
                  <td style={tdStyle}>{e.agent_id ?? '—'}</td>
                  <td style={tdStyle}>{e.capability ?? '—'}</td>
                  <td style={tdStyle}>
                    {e.success === null
                      ? '—'
                      : e.success
                        ? (
                          <span style={{ color: '#22c55e' }}>✓ success</span>
                        )
                        : (
                          <span style={{ color: '#ef4444' }}>✗ failed</span>
                        )}
                  </td>
                  <td style={tdStyle}>
                    {e.duration_s !== null ? `${e.duration_s.toFixed(3)}s` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.4rem 0.5rem',
  fontWeight: 600,
  color: 'var(--color-muted)',
  fontSize: '0.75rem',
};

const tdStyle: React.CSSProperties = {
  padding: '0.4rem 0.5rem',
  color: 'var(--color-fg)',
};

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        backgroundColor: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: '0.5rem',
        padding: '1rem 1.25rem',
      }}
    >
      <div
        style={{
          fontSize: '0.7rem',
          color: 'var(--color-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          marginBottom: '0.25rem',
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{value}</div>
    </div>
  );
}
