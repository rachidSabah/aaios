const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface Recommendation {
  recommendation_id: string;
  title: string;
  category: string;
  severity: string;
  confidence: number;
  risk: string;
  impact: string;
  affected_files: string[];
  reasoning: string;
  estimated_effort_hours: number;
  rollback_strategy: string;
  requires_approval: boolean;
}

export default async function ArchitecturePage() {
  let recs: Recommendation[] = [];
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/engineering/architecture/recommendations`, {
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json() as { recommendations?: Recommendation[] };
    recs = data.recommendations ?? [];
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Architecture
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          Architecture intelligence — layer violations, coupling, god classes, recommendations
        </p>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      <section style={{ marginBottom: '2rem' }}>
        <h2 style={h2Style}>Recommendations ({recs.length})</h2>
        {recs.length === 0 ? (
          <p style={{ color: 'var(--color-muted)' }}>No architecture recommendations.</p>
        ) : (
          <div style={{ display: 'grid', gap: '1rem' }}>
            {recs.map(r => (
              <article key={r.recommendation_id} style={panelStyle}>
                <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                  <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>{r.title}</h3>
                  <span style={{ ...badgeStyle, ...severityColor(r.severity) }}>{r.severity}</span>
                </header>
                <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', color: 'var(--color-muted)' }}>
                  Category: {r.category} · Confidence: {(r.confidence * 100).toFixed(0)}% · Risk: {r.risk} · Impact: {r.impact}
                </p>
                <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem' }}>{r.reasoning}</p>
                {r.affected_files.length > 0 && (
                  <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                    Affected: {r.affected_files.slice(0, 5).join(', ')}
                    {r.affected_files.length > 5 ? ` (+${r.affected_files.length - 5} more)` : ''}
                  </p>
                )}
                <p style={{ margin: '0', fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                  Effort: {r.estimated_effort_hours}h · Rollback: {r.rollback_strategy} · Requires approval: {r.requires_approval ? 'Yes' : 'No'}
                </p>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function severityColor(sev: string): React.CSSProperties {
  switch (sev.toLowerCase()) {
    case 'critical': return { background: '#fef2f2', color: '#991b1b' };
    case 'high': return { background: '#fff7ed', color: '#9a3412' };
    case 'medium': return { background: '#fefce8', color: '#854d0e' };
    case 'low': return { background: '#f0fdf4', color: '#166534' };
    default: return { background: '#f1f5f9', color: '#475569' };
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
