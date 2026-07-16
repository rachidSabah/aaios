const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface Dimension {
  dimension: string;
  score: number;
  status: string;
  blocking_issues: string[];
  warnings: string[];
  evidence: string[];
  confidence: number;
  recommendation: string;
}

interface ReadinessReport {
  version: string;
  overall_score: number;
  recommendation: string;
  dimensions: Dimension[];
  blocking_issues: string[];
  warnings: string[];
  certification: {
    certified: boolean;
    certification_level: string;
    overall_score: number;
    required_approvals: string[];
  };
  required_approvals: string[];
  confidence: number;
}

export default async function ReleaseReadinessPage() {
  let report: ReadinessReport | null = null;
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/engineering/release/readiness`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version: '5.2.0' }),
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    report = (await res.json()) as ReadinessReport;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const recColor = (rec: string): React.CSSProperties => {
    switch (rec) {
      case 'go': return { background: '#f0fdf4', color: '#166534' };
      case 'conditional_go': return { background: '#fefce8', color: '#854d0e' };
      default: return { background: '#fef2f2', color: '#991b1b' };
    }
  };

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Release Readiness
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          10-dimension readiness evaluation, Go/No-Go recommendation, certification report
        </p>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      {report && (
        <>
          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
            <MetricCard label="Version" value={report.version || '-'} />
            <MetricCard label="Overall Score" value={`${(report.overall_score * 100).toFixed(1)}%`} />
            <MetricCard label="Blocking Issues" value={report.blocking_issues.length} />
            <MetricCard label="Warnings" value={report.warnings.length} />
            <MetricCard label="Confidence" value={`${(report.confidence * 100).toFixed(0)}%`} />
          </section>

          <section style={{ ...panelStyle, marginBottom: '1.5rem', textAlign: 'center' }}>
            <div style={{ fontSize: '0.875rem', color: 'var(--color-muted)', marginBottom: '0.5rem' }}>Recommendation</div>
            <div style={{
              fontSize: '2rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              padding: '0.5rem 2rem',
              display: 'inline-block',
              borderRadius: '6px',
              ...recColor(report.recommendation),
            }}>
              {report.recommendation.replace('_', ' ')}
            </div>
            {report.certification && (
              <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.875rem' }}>
                Certification: <strong>{report.certification.certification_level}</strong> ·
                Certified: <strong>{report.certification.certified ? 'Yes' : 'No'}</strong>
              </p>
            )}
          </section>

          <section style={{ display: 'grid', gap: '0.75rem' }}>
            <h2 style={h2Style}>Dimensions ({report.dimensions.length})</h2>
            {report.dimensions.map(d => (
              <article key={d.dimension} style={panelStyle}>
                <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, textTransform: 'capitalize' }}>
                    {d.dimension.replace(/_/g, ' ')}
                  </h3>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <span style={{ ...badgeStyle, ...statusColor(d.status) }}>{d.status}</span>
                    <span style={{ ...badgeStyle, background: '#f1f5f9', color: '#475569' }}>
                      Score: {(d.score * 100).toFixed(0)}%
                    </span>
                  </div>
                </header>
                {d.blocking_issues.length > 0 && (
                  <ul style={{ margin: '0 0 0.5rem 0', paddingLeft: '1.25rem', fontSize: '0.8rem', color: '#991b1b' }}>
                    {d.blocking_issues.map((b, i) => <li key={i}>{b}</li>)}
                  </ul>
                )}
                {d.warnings.length > 0 && (
                  <ul style={{ margin: '0 0 0.5rem 0', paddingLeft: '1.25rem', fontSize: '0.8rem', color: '#854d0e' }}>
                    {d.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                )}
                <p style={{ margin: '0', fontSize: '0.75rem', color: 'var(--color-muted)' }}>{d.recommendation}</p>
              </article>
            ))}
          </section>

          {report.required_approvals.length > 0 && (
            <section style={{ ...panelStyle, marginTop: '1.5rem' }}>
              <h2 style={h2Style}>Required Approvals</h2>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                {report.required_approvals.map(a => <li key={a} style={{ fontSize: '0.875rem' }}>{a}</li>)}
              </ul>
            </section>
          )}
        </>
      )}
    </main>
  );
}

function statusColor(status: string): React.CSSProperties {
  switch (status) {
    case 'pass': return { background: '#f0fdf4', color: '#166534' };
    case 'warning': return { background: '#fefce8', color: '#854d0e' };
    default: return { background: '#fef2f2', color: '#991b1b' };
  }
}

function MetricCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={panelStyle}>
      <div style={{ color: 'var(--color-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-fg)', marginTop: '0.25rem' }}>{value}</div>
    </div>
  );
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
  fontSize: '0.75rem',
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
