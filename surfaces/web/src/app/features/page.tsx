const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface Feature {
  title: string;
  status: string;
  introduced_in?: string;
  description?: string;
}

export default async function FeaturesPage() {
  let features: Feature[] = [];
  let error: string | null = null;
  try {
    // Reuse evolution dashboard for feature growth data
    const res = await fetch(`${API_BASE}/api/v1/engineering/repository/evolution`, { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json() as { feature_growth?: Array<{ month: string; features: number }> };
      features = (data.feature_growth ?? []).map(f => ({
        title: `Features in ${f.month}`,
        status: 'shipped',
        introduced_in: f.month,
        description: `${f.features} feature commits`,
      }));
    }
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Features
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          Feature growth — commits categorized as features per month
        </p>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        {features.length === 0 ? (
          <p style={{ color: 'var(--color-muted)' }}>No feature data available.</p>
        ) : (
          features.map((f, i) => (
            <article key={i} style={panelStyle}>
              <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem', fontWeight: 600 }}>{f.title}</h3>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-muted)' }}>{f.description}</p>
            </article>
          ))
        )}
      </section>
    </main>
  );
}

const panelStyle: React.CSSProperties = {
  padding: '1rem',
  background: 'var(--color-card)',
  border: '1px solid var(--color-border)',
  borderRadius: '6px',
};

const errorStyle: React.CSSProperties = {
  padding: '1rem',
  background: '#fef2f2',
  border: '1px solid #fecaca',
  borderRadius: '6px',
  color: '#991b1b',
  marginBottom: '1.5rem',
};
