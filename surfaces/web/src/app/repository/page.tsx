const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface AnalysisData {
  repo_id?: string;
  name?: string;
  path?: string;
  file_count?: number;
  line_count?: number;
  language_breakdown?: Record<string, number>;
  health_score?: number;
  issues?: Array<{ issue_type: string; severity: string; file: string; description: string }>;
}

interface EvolutionData {
  total_commits?: number;
  total_authors?: number;
  total_branches?: number;
  total_releases?: number;
  commits_last_30d?: number;
  avg_commits_per_week?: number;
  by_month?: Array<{ month: string; commits: number }>;
  bug_trend?: Array<{ month: string; bug_fixes: number }>;
  feature_growth?: Array<{ month: string; features: number }>;
}

export default async function RepositoryPage() {
  let analysis: AnalysisData = {};
  let evolution: EvolutionData = {};
  let error: string | null = null;
  try {
    const [aRes, eRes] = await Promise.all([
      fetch(`${API_BASE}/api/v1/engineering/repository/analysis`, { cache: 'no-store' }),
      fetch(`${API_BASE}/api/v1/engineering/repository/evolution`, { cache: 'no-store' }),
    ]);
    if (aRes.ok) analysis = (await aRes.json()) as AnalysisData;
    if (eRes.ok) evolution = (await eRes.json()) as EvolutionData;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Repository
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          Repository intelligence and evolution dashboard
        </p>
      </header>

      {error && (
        <div style={errorStyle}>{error}</div>
      )}

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <MetricCard label="Name" value={analysis.name ?? '-'} />
        <MetricCard label="Files" value={analysis.file_count ?? 0} />
        <MetricCard label="Lines" value={analysis.line_count ?? 0} />
        <MetricCard label="Health" value={analysis.health_score?.toFixed(1) ?? '-'} />
        <MetricCard label="Commits (30d)" value={evolution.commits_last_30d ?? 0} />
        <MetricCard label="Authors" value={evolution.total_authors ?? 0} />
        <MetricCard label="Branches" value={evolution.total_branches ?? 0} />
        <MetricCard label="Releases" value={evolution.total_releases ?? 0} />
      </section>

      <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <div style={panelStyle}>
          <h2 style={h2Style}>Languages</h2>
          {analysis.language_breakdown && Object.keys(analysis.language_breakdown).length > 0 ? (
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {Object.entries(analysis.language_breakdown)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 10)
                .map(([lang, count]) => (
                  <li key={lang} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0', borderBottom: '1px solid var(--color-border)' }}>
                    <span>{lang}</span>
                    <span style={{ color: 'var(--color-muted)' }}>{count}</span>
                  </li>
                ))}
            </ul>
          ) : (
            <p style={{ color: 'var(--color-muted)' }}>No language data.</p>
          )}
        </div>
        <div style={panelStyle}>
          <h2 style={h2Style}>Monthly Commits</h2>
          {evolution.by_month && evolution.by_month.length > 0 ? (
            <BarChart data={evolution.by_month.map(m => ({ label: m.month, value: m.commits }))} />
          ) : (
            <p style={{ color: 'var(--color-muted)' }}>No commit history.</p>
          )}
        </div>
      </section>
    </main>
  );
}

function BarChart({ data }: { data: Array<{ label: string; value: number }> }) {
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
      {data.slice(-12).map(d => (
        <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ width: '5rem', fontSize: '0.75rem', color: 'var(--color-muted)' }}>{d.label}</span>
          <div style={{ flex: 1, background: 'var(--color-border)', borderRadius: '3px', height: '0.5rem' }}>
            <div style={{ width: `${(d.value / max) * 100}%`, background: 'var(--color-accent)', height: '100%', borderRadius: '3px' }} />
          </div>
          <span style={{ width: '2.5rem', fontSize: '0.75rem', textAlign: 'right' }}>{d.value}</span>
        </div>
      ))}
    </div>
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
  fontSize: '1rem',
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
