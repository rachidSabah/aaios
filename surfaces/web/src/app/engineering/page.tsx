import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface OverviewData {
  repository?: { name?: string; file_count?: number; line_count?: number };
  architecture_recommendations?: number;
  engineering_agents?: number;
  capabilities?: Record<string, unknown> | number;
  workspaces?: number;
  health_score?: number;
}

export default async function EngineeringPage() {
  let data: OverviewData = {};
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/engineering/overview`, {
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = (await res.json()) as OverviewData;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Engineering Intelligence
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          Autonomous Software Engineering Platform — analysis, reviews, recommendations
        </p>
      </header>

      {error && (
        <div style={{ padding: '1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', color: '#991b1b', marginBottom: '1.5rem' }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <MetricCard label="Files" value={data.repository?.file_count ?? 0} />
        <MetricCard label="Lines" value={data.repository?.line_count ?? 0} />
        <MetricCard label="Arch Recommendations" value={data.architecture_recommendations ?? 0} />
        <MetricCard label="Engineering Agents" value={data.engineering_agents ?? 0} />
        <MetricCard label="Workspaces" value={data.workspaces ?? 0} />
        <MetricCard label="Health Score" value={data.health_score?.toFixed(1) ?? '-'} />
      </section>

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        <Link href="/architecture" style={cardStyle}>
          <h3 style={h3Style}>Architecture</h3>
          <p style={pStyle}>Layer violations, god classes, circular dependencies, and recommendations</p>
        </Link>
        <Link href="/reviews" style={cardStyle}>
          <h3 style={h3Style}>Reviews</h3>
          <p style={pStyle}>12 review types: architecture, code, security, performance, dependency, documentation, testing, API, database, workflow, plugin, mission</p>
        </Link>
        <Link href="/test-intelligence" style={cardStyle}>
          <h3 style={h3Style}>Test Intelligence</h3>
          <p style={pStyle}>Coverage, flaky tests, long-running tests, missing tests, mutation readiness</p>
        </Link>
        <Link href="/release-readiness" style={cardStyle}>
          <h3 style={h3Style}>Release Readiness</h3>
          <p style={pStyle}>10-dimension readiness evaluation, Go/No-Go recommendation, certification report</p>
        </Link>
        <Link href="/repository-health" style={cardStyle}>
          <h3 style={h3Style}>Repository Health</h3>
          <p style={pStyle}>8 health dimensions, overall score, improvement recommendations</p>
        </Link>
        <Link href="/repository" style={cardStyle}>
          <h3 style={h3Style}>Repository Evolution</h3>
          <p style={pStyle}>Commit history, releases, timeline, growth analytics</p>
        </Link>
      </section>
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={{ padding: '1rem', background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '6px' }}>
      <div style={{ color: 'var(--color-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-fg)', marginTop: '0.25rem' }}>{value}</div>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  display: 'block',
  padding: '1.25rem',
  background: 'var(--color-card)',
  border: '1px solid var(--color-border)',
  borderRadius: '6px',
  textDecoration: 'none',
  color: 'var(--color-fg)',
};

const h3Style: React.CSSProperties = {
  margin: '0 0 0.5rem 0',
  fontSize: '1.05rem',
  fontWeight: 600,
};

const pStyle: React.CSSProperties = {
  margin: 0,
  fontSize: '0.875rem',
  color: 'var(--color-muted)',
  lineHeight: 1.5,
};
