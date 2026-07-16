const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface HealthScore {
  overall_score: number;
  grade: string;
  status: string;
  operational: number;
  mission: number;
  agent_efficiency: number;
  provider_efficiency: number;
  workflow_quality: number;
  execution_success: number;
  risk_level: number;
  reliability: number;
  cost_efficiency: number;
  learning_velocity: number;
  innovation: number;
  component_health: Array<{ component: string; score: number; status: string }>;
}

interface Forecast {
  forecast_type: string;
  prediction: string;
  probability: number;
  confidence: string;
  time_horizon: string;
}

interface Recommendation {
  optimization_type: string;
  title: string;
  priority: string;
  estimated_impact: number;
  expected_improvement: string;
}

interface Risk {
  level: string;
  risk_type: string;
  description: string;
  risk_score: number;
  mitigation: string;
}

export default async function IntelligencePage() {
  // Fetch all intelligence data in parallel
  const [healthRes, forecastRes, optRes, riskRes] = await Promise.all([
    fetch(`${API_BASE}/api/v1/intelligence/health`, { cache: 'no-store' }).catch(() => null),
    fetch(`${API_BASE}/api/v1/intelligence/forecast`, { cache: 'no-store' }).catch(() => null),
    fetch(`${API_BASE}/api/v1/intelligence/optimization`, { cache: 'no-store' }).catch(() => null),
    fetch(`${API_BASE}/api/v1/intelligence/risks`, { cache: 'no-store' }).catch(() => null),
  ]);

  const health = healthRes?.ok ? ((await healthRes.json()) as HealthScore) : null;
  const forecasts = forecastRes?.ok
    ? ((await forecastRes.json()) as { forecasts: Forecast[] }).forecasts
    : [];
  const recs = optRes?.ok
    ? ((await optRes.json()) as { recommendations: Recommendation[] }).recommendations
    : [];
  const riskData = riskRes?.ok ? ((await riskRes.json()) as { risks: Risk[]; heat_map: { by_level: Record<string, number> } }) : null;

  if (!health) {
    return (
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, marginBottom: '1rem' }}>
          Intelligence Command Center
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

  const score = health.overall_score;
  const scoreColor = score >= 0.8 ? '#22c55e' : score >= 0.6 ? '#f59e0b' : '#ef4444';

  const dimensions: Array<{ label: string; value: number }> = [
    { label: 'Operational', value: health.operational },
    { label: 'Mission', value: health.mission },
    { label: 'Agent Eff.', value: health.agent_efficiency },
    { label: 'Provider Eff.', value: health.provider_efficiency },
    { label: 'Workflow Qual.', value: health.workflow_quality },
    { label: 'Exec. Success', value: health.execution_success },
    { label: 'Risk Level', value: health.risk_level },
    { label: 'Reliability', value: health.reliability },
    { label: 'Cost Eff.', value: health.cost_efficiency },
    { label: 'Learning Vel.', value: health.learning_velocity },
    { label: 'Innovation', value: health.innovation },
  ];

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Intelligence Command Center
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          Enterprise health, forecasts, optimization, and risk — continuously self-analyzing
        </p>
      </header>

      {/* Enterprise Health Score */}
      <div
        style={{
          backgroundColor: 'var(--color-card)',
          border: '1px solid var(--color-border)',
          borderRadius: '0.5rem',
          padding: '1.5rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '2rem',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', fontWeight: 800, color: scoreColor }}>
            {health.grade}
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: scoreColor }}>
            {(score * 100).toFixed(1)}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)', textTransform: 'uppercase' }}>
            {health.status}
          </div>
        </div>
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: '0.75rem' }}>
          {dimensions.map((dim) => (
            <div key={dim.label}>
              <div style={{ fontSize: '0.65rem', color: 'var(--color-muted)', textTransform: 'uppercase', marginBottom: '0.2rem' }}>
                {dim.label}
              </div>
              <div style={{ height: '4px', backgroundColor: 'var(--color-bg)', borderRadius: '2px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${dim.value * 100}%`,
                    backgroundColor: dim.value >= 0.8 ? '#22c55e' : dim.value >= 0.6 ? '#f59e0b' : '#ef4444',
                  }}
                />
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--color-fg)', marginTop: '0.1rem' }}>
                {dim.value.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        {/* Forecasts */}
        <Section title={`Forecasts (${forecasts.length})`}>
          {forecasts.length === 0 ? (
            <Empty />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <th style={thStyle}>Type</th>
                  <th style={thStyle}>Prob.</th>
                  <th style={thStyle}>Horizon</th>
                  <th style={thStyle}>Prediction</th>
                </tr>
              </thead>
              <tbody>
                {forecasts.slice(0, 8).map((f, i) => {
                  const prob = f.probability;
                  const color = prob > 0.5 ? '#ef4444' : prob > 0.3 ? '#f59e0b' : '#22c55e';
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: '0.7rem' }}>
                        {f.forecast_type}
                      </td>
                      <td style={{ ...tdStyle, color, fontWeight: 600 }}>
                        {(prob * 100).toFixed(0)}%
                      </td>
                      <td style={tdStyle}>{f.time_horizon}</td>
                      <td style={{ ...tdStyle, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {f.prediction}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Section>

        {/* Recommendations */}
        <Section title={`Optimization Recommendations (${recs.length})`}>
          {recs.length === 0 ? (
            <Empty />
          ) : (
            recs.slice(0, 6).map((r, i) => (
              <div key={i} style={{ padding: '0.5rem 0', borderBottom: '1px solid var(--color-border)' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>
                  <span style={{ color: r.priority === 'high' ? '#ef4444' : r.priority === 'critical' ? '#dc2626' : 'var(--color-muted)' }}>
                    [{r.priority}]
                  </span>{' '}
                  {r.title}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--color-muted)', marginTop: '0.15rem' }}>
                  Impact: {(r.estimated_impact * 100).toFixed(0)}% · {r.expected_improvement}
                </div>
              </div>
            ))
          )}
        </Section>

        {/* Risk Heat Map */}
        <Section title="Risk Heat Map">
          {riskData ? (
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              {['critical', 'high', 'medium', 'low', 'negligible'].map((level) => {
                const count = riskData.heat_map.by_level[level] || 0;
                const color = level === 'critical' ? '#dc2626' : level === 'high' ? '#ef4444' : level === 'medium' ? '#f59e0b' : '#22c55e';
                return (
                  <div key={level} style={{ textAlign: 'center', padding: '0.75rem 1rem', backgroundColor: 'var(--color-bg)', borderRadius: '0.375rem' }}>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color }}>{count}</div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--color-muted)', textTransform: 'uppercase' }}>{level}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            <Empty />
          )}
          {riskData && riskData.risks.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              {riskData.risks.slice(0, 5).map((r, i) => (
                <div key={i} style={{ padding: '0.3rem 0', fontSize: '0.75rem', borderBottom: '1px solid var(--color-border)' }}>
                  <span style={{ color: r.level === 'critical' ? '#dc2626' : r.level === 'high' ? '#ef4444' : r.level === 'medium' ? '#f59e0b' : '#22c55e' }}>
                    [{r.level}]
                  </span>{' '}
                  {r.description}
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Component Health */}
        <Section title="Component Health">
          {health.component_health.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <th style={thStyle}>Component</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Score</th>
                </tr>
              </thead>
              <tbody>
                {health.component_health.map((c, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{c.component}</td>
                    <td style={{ ...tdStyle, color: c.status === 'healthy' ? '#22c55e' : c.status === 'degraded' ? '#f59e0b' : '#ef4444' }}>
                      {c.status}
                    </td>
                    <td style={tdStyle}>{c.score.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty />
          )}
        </Section>
      </div>
    </main>
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
      <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.75rem' }}>
        {title}
      </h3>
      {children}
    </div>
  );
}

function Empty() {
  return <p style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>No data available.</p>;
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
