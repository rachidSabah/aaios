const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface ReviewReport {
  review_type: string;
  summary: string;
  observations: Array<{ title: string; description: string; evidence: string[] }>;
  weaknesses: Array<{ title: string; description: string; severity: string; recommendation: string }>;
  risk_score: number;
  confidence: number;
  recommendations: string[];
}

export default async function DependenciesPage() {
  let report: ReviewReport | null = null;
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/engineering/reviews/dependency`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: '.' }),
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    report = (await res.json()) as ReviewReport;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Dependencies
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          Dependency review — count, pinning, security, license concerns
        </p>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      {report && (
        <>
          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
            <MetricCard label="Risk Score" value={`${(report.risk_score * 100).toFixed(0)}%`} />
            <MetricCard label="Confidence" value={`${(report.confidence * 100).toFixed(0)}%`} />
            <MetricCard label="Observations" value={report.observations.length} />
            <MetricCard label="Weaknesses" value={report.weaknesses.length} />
          </section>

          <section style={panelStyle}>
            <h2 style={h2Style}>Summary</h2>
            <p style={{ margin: 0, fontSize: '0.875rem' }}>{report.summary}</p>
          </section>

          {report.observations.length > 0 && (
            <section style={{ ...panelStyle, marginTop: '1.5rem' }}>
              <h2 style={h2Style}>Observations</h2>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                {report.observations.map((o, i) => (
                  <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                    <strong>{o.title}</strong> — {o.description}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {report.weaknesses.length > 0 && (
            <section style={{ ...panelStyle, marginTop: '1.5rem' }}>
              <h2 style={h2Style}>Weaknesses</h2>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                {report.weaknesses.map((w, i) => (
                  <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                    <strong style={{ color: w.severity === 'high' ? '#991b1b' : '#854d0e' }}>[{w.severity.toUpperCase()}]</strong>{' '}
                    <strong>{w.title}</strong> — {w.description}
                    <br />
                    <span style={{ color: 'var(--color-muted)' }}>→ {w.recommendation}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {report.recommendations.length > 0 && (
            <section style={{ ...panelStyle, marginTop: '1.5rem' }}>
              <h2 style={h2Style}>Recommendations</h2>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                {report.recommendations.map((r, i) => (
                  <li key={i} style={{ marginBottom: '0.25rem', fontSize: '0.875rem' }}>{r}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </main>
  );
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

const h2Style: React.CSSProperties = {
  fontSize: '1.25rem',
  fontWeight: 600,
  margin: '0 0 0.75rem 0',
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
