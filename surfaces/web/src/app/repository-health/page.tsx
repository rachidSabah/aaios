const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface HealthDimension {
  dimension: string;
  score: number;
  status: string;
  summary: string;
  indicators: Record<string, any>;
  recommendation: string;
  confidence: number;
}

interface HealthReport {
  repository: string;
  overall_score: number;
  status: string;
  dimensions: HealthDimension[];
  trend: Array<{ timestamp: string; overall_score: number; by_dimension: Record<string, number> }>;
  improvement_recommendations: Array<{
    dimension: string;
    priority: string;
    current_score: number;
    target_score: number;
    recommendation: string;
    confidence: number;
  }>;
}

export default async function RepositoryHealthPage() {
  let report: HealthReport | null = null;
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/engineering/health`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    report = (await res.json()) as HealthReport;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Repository Health
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          8 health dimensions — repository, architecture, dependency, documentation, security, testing, release, knowledge
        </p>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      {report && (
        <>
          <section style={{ ...panelStyle, marginBottom: '1.5rem', textAlign: 'center' }}>
            <div style={{ fontSize: '0.875rem', color: 'var(--color-muted)', marginBottom: '0.5rem' }}>Overall Health Score</div>
            <div style={{
              fontSize: '3rem',
              fontWeight: 700,
              color: report.status === 'healthy' ? '#166534' : report.status === 'warning' ? '#854d0e' : '#991b1b',
            }}>
              {report.overall_score.toFixed(1)}
            </div>
            <div style={{
              fontSize: '0.875rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              color: report.status === 'healthy' ? '#166534' : report.status === 'warning' ? '#854d0e' : '#991b1b',
            }}>
              {report.status}
            </div>
          </section>

          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
            {report.dimensions.map(d => (
              <article key={d.dimension} style={panelStyle}>
                <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, textTransform: 'capitalize' }}>
                    {d.dimension}
                  </h3>
                  <span style={{ ...badgeStyle, ...statusColor(d.status) }}>{d.status}</span>
                </header>
                <div style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                  {d.score.toFixed(0)}<span style={{ fontSize: '0.875rem', color: 'var(--color-muted)' }}>/100</span>
                </div>
                <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.8rem', color: 'var(--color-muted)' }}>{d.summary}</p>
                <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--color-muted)' }}>{d.recommendation}</p>
              </article>
            ))}
          </section>

          {report.improvement_recommendations.length > 0 && (
            <section style={panelStyle}>
              <h2 style={h2Style}>Improvement Recommendations</h2>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                {report.improvement_recommendations.map((r, i) => (
                  <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                    <strong style={{ color: r.priority === 'high' ? '#991b1b' : '#854d0e' }}>
                      [{r.priority.toUpperCase()}]
                    </strong>{' '}
                    <span style={{ textTransform: 'capitalize' }}>{r.dimension}</span>{' '}
                    — {r.recommendation}{' '}
                    <span style={{ color: 'var(--color-muted)' }}>
                      ({r.current_score.toFixed(0)} → {r.target_score.toFixed(0)})
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {report.trend.length > 1 && (
            <section style={{ ...panelStyle, marginTop: '1.5rem' }}>
              <h2 style={h2Style}>Health Trend</h2>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.25rem', height: '6rem' }}>
                {report.trend.slice(-12).map((t, i) => (
                  <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div style={{
                      width: '100%',
                      height: `${t.overall_score}%`,
                      background: t.overall_score >= 80 ? '#166534' : t.overall_score >= 50 ? '#854d0e' : '#991b1b',
                      borderRadius: '3px 3px 0 0',
                      minHeight: '2px',
                    }} />
                    <span style={{ fontSize: '0.65rem', color: 'var(--color-muted)', marginTop: '0.25rem' }}>
                      {new Date(t.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}

function statusColor(status: string): React.CSSProperties {
  switch (status) {
    case 'healthy': return { background: '#f0fdf4', color: '#166534' };
    case 'warning': return { background: '#fefce8', color: '#854d0e' };
    default: return { background: '#fef2f2', color: '#991b1b' };
  }
}

const panelStyle: React.CSSProperties = {
  padding: '1rem',
  background: 'var(--color-card)',
  border: '1px solid var(--color-border)',
  borderRadius: '6px',
};

const badgeStyle: React.CSSProperties = {
  padding: '0.125rem 0.5rem',
  borderRadius: '4px',
  fontSize: '0.7rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const h2Style: React.CSSProperties = {
  fontSize: '1.25rem',
  fontWeight: 600,
  margin: '0 0 1rem 0',
  color: 'var(--color-fg)',
};

const errorStyle: React.CSSProperties = {
  padding: '1rem',
  background: '#fef2f2',
  border: '1px solid #fecaca',
  borderRadius: '6px',
  color: '#991b1b',
  marginBottom: '1.5rem',
};
