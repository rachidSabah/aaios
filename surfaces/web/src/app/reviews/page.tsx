const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface ReviewReport {
  review_id: string;
  review_type: string;
  target: string;
  summary: string;
  strengths: any[];
  weaknesses: any[];
  observations: any[];
  risk_score: number;
  confidence: number;
  recommendations: string[];
  approval_required: boolean;
  historical_comparison: Record<string, any>;
  reviewed_at: string;
}

export default async function ReviewsPage() {
  let reports: Record<string, ReviewReport> = {};
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/engineering/reviews`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: '.' }),
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    reports = (await res.json()) as Record<string, ReviewReport>;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const reviewTypes = Object.keys(reports).sort();

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Engineering Reviews
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          12 review types — every review produces strengths, weaknesses, evidence, risk, confidence, recommendations
        </p>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      <section style={{ display: 'grid', gap: '1.5rem' }}>
        {reviewTypes.map(rt => {
          const r = reports[rt];
          return (
            <article key={rt} style={panelStyle}>
              <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, textTransform: 'capitalize' }}>{rt}</h2>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <span style={{ ...badgeStyle, ...riskColor(r.risk_score) }}>Risk: {(r.risk_score * 100).toFixed(0)}%</span>
                  <span style={{ ...badgeStyle, background: '#f1f5f9', color: '#475569' }}>Conf: {(r.confidence * 100).toFixed(0)}%</span>
                </div>
              </header>
              <p style={{ margin: '0 0 0.75rem 0', fontSize: '0.875rem', color: 'var(--color-muted)' }}>{r.summary}</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: '#166534' }}>Strengths ({r.strengths.length})</h3>
                  <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8rem' }}>
                    {r.strengths.slice(0, 5).map((s: any, i: number) => (
                      <li key={i}>{s.title}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: '#991b1b' }}>Weaknesses ({r.weaknesses.length})</h3>
                  <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8rem' }}>
                    {r.weaknesses.slice(0, 5).map((w: any, i: number) => (
                      <li key={i}>{w.title}</li>
                    ))}
                  </ul>
                </div>
              </div>
              {r.recommendations.length > 0 && (
                <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                  <strong>Recommendations:</strong> {r.recommendations.slice(0, 2).join(' · ')}
                </p>
              )}
            </article>
          );
        })}
      </section>
    </main>
  );
}

function riskColor(score: number): React.CSSProperties {
  if (score >= 0.7) return { background: '#fef2f2', color: '#991b1b' };
  if (score >= 0.4) return { background: '#fff7ed', color: '#9a3412' };
  return { background: '#f0fdf4', color: '#166534' };
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
};

const errorStyle: React.CSSProperties = {
  padding: '1rem',
  background: '#fef2f2',
  border: '1px solid #fecaca',
  borderRadius: '6px',
  color: '#991b1b',
  marginBottom: '1.5rem',
};
