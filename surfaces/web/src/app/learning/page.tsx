const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface LearningStats {
  total_experiences: number;
  total_successes: number;
  total_failures: number;
  overall_success_rate: number;
  overall_avg_quality: number;
  overall_avg_latency_s: number;
  overall_avg_cost_usd: number;
  total_cost_usd: number;
  total_tokens: number;
  agent_count: number;
  provider_count: number;
  capability_count: number;
  workflow_count: number;
  last_24h_count: number;
  last_7d_count: number;
}

interface AgentReliability {
  agent_id: string;
  agent_type: string;
  experience_count: number;
  success_rate: number;
  avg_quality: number;
  avg_latency_s: number;
  avg_cost_usd: number;
  reliability_score: number;
  recent_success_rate: number;
  trend: string;
}

interface ProviderReliability {
  provider: string;
  experience_count: number;
  success_rate: number;
  avg_latency_s: number;
  avg_cost_usd: number;
  reliability_score: number;
}

interface PatternReport {
  success_patterns: Array<{ description: string; occurrence_count: number; avg_quality: number }>;
  failure_patterns: Array<{ description: string; occurrence_count: number; recovery_action: string | null }>;
  repeated_fixes: Array<{ description: string; occurrence_count: number }>;
}

export default async function LearningPage() {
  // Fetch all learning data in parallel
  const [statsRes, agentsRes, providersRes, patternsRes] = await Promise.all([
    fetch(`${API_BASE}/api/v1/learning/stats`, { cache: 'no-store' }).catch(() => null),
    fetch(`${API_BASE}/api/v1/learning/agents?limit=10`, { cache: 'no-store' }).catch(() => null),
    fetch(`${API_BASE}/api/v1/learning/providers?limit=10`, { cache: 'no-store' }).catch(() => null),
    fetch(`${API_BASE}/api/v1/learning/patterns`, { cache: 'no-store' }).catch(() => null),
  ]);

  const stats = statsRes?.ok ? ((await statsRes.json()) as LearningStats) : null;
  const agentsData = agentsRes?.ok ? ((await agentsRes.json()) as { agents: AgentReliability[] }) : null;
  const providersData = providersRes?.ok ? ((await providersRes.json()) as { providers: ProviderReliability[] }) : null;
  const patterns = patternsRes?.ok ? ((await patternsRes.json()) as PatternReport) : null;

  if (!stats) {
    return (
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, marginBottom: '1rem' }}>
          Learning Analytics
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

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1
          style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            margin: 0,
            color: 'var(--color-fg)',
          }}
        >
          Learning Analytics
        </h1>
        <p
          style={{
            color: 'var(--color-muted)',
            marginTop: '0.25rem',
            fontSize: '0.875rem',
          }}
        >
          Reliability scores, patterns, and recommendations derived from accumulated experience
        </p>
      </header>

      {/* KPI cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <KpiCard label="Total Experiences" value={stats.total_experiences.toString()} />
        <KpiCard
          label="Success Rate"
          value={`${(stats.overall_success_rate * 100).toFixed(1)}%`}
          color={stats.overall_success_rate >= 0.9 ? '#22c55e' : '#ef4444'}
        />
        <KpiCard label="Avg Quality" value={stats.overall_avg_quality.toFixed(3)} />
        <KpiCard label="Avg Latency" value={`${stats.overall_avg_latency_s.toFixed(3)}s`} />
        <KpiCard label="Total Cost" value={`$${stats.total_cost_usd.toFixed(2)}`} />
        <KpiCard label="Agents Tracked" value={stats.agent_count.toString()} />
        <KpiCard label="Providers" value={stats.provider_count.toString()} />
        <KpiCard label="Last 24h" value={stats.last_24h_count.toString()} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        {/* Agent rankings */}
        <Section title="Agent Reliability Rankings">
          {agentsData && agentsData.agents.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <th style={thStyle}>Agent</th>
                  <th style={thStyle}>Success</th>
                  <th style={thStyle}>Quality</th>
                  <th style={thStyle}>Reliability</th>
                  <th style={thStyle}>Trend</th>
                </tr>
              </thead>
              <tbody>
                {agentsData.agents.map((a) => (
                  <tr key={a.agent_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{a.agent_id}</td>
                    <td style={{ ...tdStyle, color: a.success_rate >= 0.8 ? '#22c55e' : '#ef4444' }}>
                      {(a.success_rate * 100).toFixed(0)}%
                    </td>
                    <td style={tdStyle}>{a.avg_quality.toFixed(3)}</td>
                    <td style={{ ...tdStyle, fontWeight: 600 }}>
                      {a.reliability_score.toFixed(3)}
                    </td>
                    <td style={{ ...tdStyle, color: a.trend === 'improving' ? '#22c55e' : a.trend === 'declining' ? '#ef4444' : 'var(--color-muted)' }}>
                      {a.trend}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty />
          )}
        </Section>

        {/* Provider rankings */}
        <Section title="Provider Reliability Rankings">
          {providersData && providersData.providers.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <th style={thStyle}>Provider</th>
                  <th style={thStyle}>Success</th>
                  <th style={thStyle}>Latency</th>
                  <th style={thStyle}>Cost</th>
                  <th style={thStyle}>Reliability</th>
                </tr>
              </thead>
              <tbody>
                {providersData.providers.map((p) => (
                  <tr key={p.provider} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{p.provider}</td>
                    <td style={{ ...tdStyle, color: p.success_rate >= 0.8 ? '#22c55e' : '#ef4444' }}>
                      {(p.success_rate * 100).toFixed(0)}%
                    </td>
                    <td style={tdStyle}>{p.avg_latency_s.toFixed(3)}s</td>
                    <td style={tdStyle}>${p.avg_cost_usd.toFixed(4)}</td>
                    <td style={{ ...tdStyle, fontWeight: 600 }}>
                      {p.reliability_score.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty />
          )}
        </Section>
      </div>

      {/* Patterns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <Section title="Success Patterns">
          {patterns && patterns.success_patterns.length > 0 ? (
            <ul style={{ margin: 0, padding: '0 0 0 1rem', fontSize: '0.8rem' }}>
              {patterns.success_patterns.slice(0, 8).map((p, i) => (
                <li key={i} style={{ padding: '0.3rem 0', borderBottom: '1px solid var(--color-border)' }}>
                  <div>{p.description}</div>
                  <div style={{ color: 'var(--color-muted)', fontSize: '0.7rem' }}>
                    {p.occurrence_count}x, quality={p.avg_quality.toFixed(2)}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty />
          )}
        </Section>

        <Section title="Failure Patterns">
          {patterns && patterns.failure_patterns.length > 0 ? (
            <ul style={{ margin: 0, padding: '0 0 0 1rem', fontSize: '0.8rem' }}>
              {patterns.failure_patterns.slice(0, 8).map((p, i) => (
                <li key={i} style={{ padding: '0.3rem 0', borderBottom: '1px solid var(--color-border)' }}>
                  <div style={{ color: '#ef4444' }}>{p.description}</div>
                  <div style={{ color: 'var(--color-muted)', fontSize: '0.7rem' }}>
                    {p.occurrence_count}x
                    {p.recovery_action ? ` · recovery: ${p.recovery_action}` : ''}
                  </div>
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
        padding: '0.9rem 1.1rem',
      }}
    >
      <div
        style={{
          fontSize: '0.65rem',
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
          fontSize: '1.3rem',
          fontWeight: 700,
          color: color ?? 'var(--color-fg)',
        }}
      >
        {value}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        backgroundColor: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: '0.5rem',
        padding: '1.25rem',
        marginBottom: '1.5rem',
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
        {title}
      </h3>
      {children}
    </div>
  );
}

function Empty() {
  return (
    <p style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>No data yet.</p>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.4rem 0.5rem',
  fontWeight: 600,
  color: 'var(--color-muted)',
  fontSize: '0.7rem',
  textTransform: 'uppercase',
};

const tdStyle: React.CSSProperties = {
  padding: '0.4rem 0.5rem',
  color: 'var(--color-fg)',
};
