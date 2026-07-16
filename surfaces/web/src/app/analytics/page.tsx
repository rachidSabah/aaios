const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface AnalyticsSummary {
  window_minutes: number;
  total_events: number;
  events_per_minute: number;
  success_rate: number;
  avg_latency_s: number;
  total_cost_usd: number;
  top_agents: Array<[string, number]>;
  top_capabilities: Array<[string, number]>;
  active_agents: string[];
  active_capabilities: string[];
}

interface LatencyPercentiles {
  window_minutes: number;
  p50: number;
  p90: number;
  p95: number;
  p99: number;
  count: number;
}

interface CostBreakdown {
  window_minutes: number;
  by_capability: Array<{ capability: string; cost_usd: number }>;
  total_cost_usd: number;
}

interface ThroughputResponse {
  window_minutes: number;
  series: Array<{ timestamp: number; value: number }>;
}

export default async function AnalyticsPage() {
  // Fetch all analytics endpoints in parallel
  const [summaryRes, latencyRes, costRes, throughputRes] = await Promise.all([
    fetch(`${API_BASE}/api/v1/analytics/summary`, { cache: 'no-store' }).catch(() => null),
    fetch(`${API_BASE}/api/v1/analytics/latency?window_minutes=60`, {
      cache: 'no-store',
    }).catch(() => null),
    fetch(`${API_BASE}/api/v1/analytics/costs?window_minutes=60`, {
      cache: 'no-store',
    }).catch(() => null),
    fetch(`${API_BASE}/api/v1/analytics/throughput?window_minutes=60`, {
      cache: 'no-store',
    }).catch(() => null),
  ]);

  const summary = summaryRes?.ok
    ? ((await summaryRes.json()) as AnalyticsSummary)
    : null;
  const latency = latencyRes?.ok
    ? ((await latencyRes.json()) as LatencyPercentiles)
    : null;
  const costs = costRes?.ok
    ? ((await costRes.json()) as CostBreakdown)
    : null;
  const throughput = throughputRes?.ok
    ? ((await throughputRes.json()) as ThroughputResponse)
    : null;

  if (!summary) {
    return (
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, marginBottom: '1rem' }}>
          Analytics
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
          Could not reach API server. Start it with <code>aaios dev</code>.
        </div>
      </main>
    );
  }

  // Throughput chart
  const series = throughput?.series ?? [];
  const maxThroughput = Math.max(1, ...series.map((s) => s.value));
  const chartW = 800;
  const chartH = 150;
  const barW = series.length > 0 ? chartW / series.length : 1;

  // Cost breakdown horizontal bars
  const maxCost = Math.max(1, ...(costs?.by_capability ?? []).map((c) => c.cost_usd));

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
          Analytics
        </h1>
        <p
          style={{
            color: 'var(--color-muted)',
            marginTop: '0.25rem',
            fontSize: '0.875rem',
          }}
        >
          Aggregated metrics over the last 60 minutes
        </p>
      </header>

      {/* KPI cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <KpiCard
          label="Total Events"
          value={summary.total_events.toString()}
        />
        <KpiCard
          label="Events / min"
          value={summary.events_per_minute.toFixed(1)}
        />
        <KpiCard
          label="Success Rate"
          value={`${(summary.success_rate * 100).toFixed(1)}%`}
          color={summary.success_rate >= 0.9 ? '#22c55e' : '#ef4444'}
        />
        <KpiCard
          label="Avg Latency"
          value={`${summary.avg_latency_s.toFixed(3)}s`}
        />
        <KpiCard
          label="Total Cost"
          value={`$${summary.total_cost_usd.toFixed(4)}`}
        />
      </div>

      {/* Throughput chart */}
      <Section title="Throughput — Events per Minute">
        {series.length === 0 ? (
          <Empty />
        ) : (
          <svg width={chartW} height={chartH} style={{ display: 'block' }}>
            {series.map((s, i) => {
              const h = (s.value / maxThroughput) * (chartH - 20);
              return (
                <rect
                  key={i}
                  x={i * barW + 1}
                  y={chartH - h - 10}
                  width={Math.max(1, barW - 2)}
                  height={h}
                  fill="var(--color-accent)"
                  opacity={0.7}
                />
              );
            })}
          </svg>
        )}
      </Section>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '1.5rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Latency percentiles */}
        <Section title="Latency Percentiles">
          {latency ? (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: '0.75rem',
              }}
            >
              <PercentileTile label="p50" value={latency.p50} />
              <PercentileTile label="p90" value={latency.p90} />
              <PercentileTile label="p95" value={latency.p95} />
              <PercentileTile label="p99" value={latency.p99} />
            </div>
          ) : (
            <Empty />
          )}
        </Section>

        {/* Cost breakdown */}
        <Section title="Cost by Capability">
          {costs && costs.by_capability.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {costs.by_capability.slice(0, 8).map((c) => (
                <div key={c.capability}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '0.75rem',
                      marginBottom: '0.2rem',
                    }}
                  >
                    <span style={{ fontFamily: 'monospace' }}>{c.capability}</span>
                    <span style={{ color: 'var(--color-muted)' }}>
                      ${c.cost_usd.toFixed(4)}
                    </span>
                  </div>
                  <div
                    style={{
                      height: '6px',
                      backgroundColor: 'var(--color-bg)',
                      borderRadius: '3px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${(c.cost_usd / maxCost) * 100}%`,
                        backgroundColor: 'var(--color-accent)',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Empty />
          )}
        </Section>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '1.5rem',
        }}
      >
        {/* Top agents */}
        <Section title="Top Agents (by event count)">
          {summary.top_agents.length > 0 ? (
            <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {summary.top_agents.map(([agent, count]) => (
                <li
                  key={agent}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '0.4rem 0',
                    borderBottom: '1px solid var(--color-border)',
                    fontSize: '0.8rem',
                  }}
                >
                  <span style={{ fontFamily: 'monospace' }}>{agent}</span>
                  <span style={{ color: 'var(--color-muted)' }}>{count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty />
          )}
        </Section>

        {/* Top capabilities */}
        <Section title="Top Capabilities (by event count)">
          {summary.top_capabilities.length > 0 ? (
            <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {summary.top_capabilities.map(([cap, count]) => (
                <li
                  key={cap}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '0.4rem 0',
                    borderBottom: '1px solid var(--color-border)',
                    fontSize: '0.8rem',
                  }}
                >
                  <span style={{ fontFamily: 'monospace' }}>{cap}</span>
                  <span style={{ color: 'var(--color-muted)' }}>{count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty />
          )}
        </Section>
      </div>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        backgroundColor: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: '0.5rem',
        padding: '1.5rem',
        marginBottom: '1.5rem',
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
        {title}
      </h3>
      {children}
    </div>
  );
}

function Empty() {
  return (
    <p style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>No data.</p>
  );
}

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
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
      <div
        style={{
          fontSize: '1.5rem',
          fontWeight: 700,
          color: color ?? 'var(--color-fg)',
        }}
      >
        {value}
      </div>
    </div>
  );
}

function PercentileTile({ label, value }: { label: string; value: number }) {
  return (
    <div
      style={{
        textAlign: 'center',
        padding: '0.75rem 0.5rem',
        backgroundColor: 'var(--color-bg)',
        borderRadius: '0.375rem',
      }}
    >
      <div
        style={{
          fontSize: '0.7rem',
          color: 'var(--color-muted)',
          marginBottom: '0.25rem',
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>
        {value.toFixed(3)}s
      </div>
    </div>
  );
}
