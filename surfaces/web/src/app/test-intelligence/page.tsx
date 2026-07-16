const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface TestAnalysis {
  total_tests: number;
  by_type: Record<string, number>;
  total_files: number;
  total_fixtures: number;
  unused_fixtures: string[];
  duplicate_tests: Array<{ signature: string; occurrences: any[] }>;
  long_running_tests: any[];
  flaky_candidates: any[];
  missing_tests: any[];
  mutation_readiness: number;
}

interface CoverageReport {
  overall_pct: number;
  by_directory: Record<string, number>;
  by_test_type: Record<string, number>;
  uncovered_files: string[];
  undercovered_files: Array<{ file: string; coverage_pct: number }>;
}

export default async function TestIntelligencePage() {
  let analysis: TestAnalysis | null = null;
  let coverage: CoverageReport | null = null;
  let error: string | null = null;
  try {
    const [aRes, cRes] = await Promise.all([
      fetch(`${API_BASE}/api/v1/engineering/test-intelligence/analysis`, { cache: 'no-store' }),
      fetch(`${API_BASE}/api/v1/engineering/test-intelligence/coverage`, { cache: 'no-store' }),
    ]);
    if (aRes.ok) analysis = (await aRes.json()) as TestAnalysis;
    if (cRes.ok) coverage = (await cRes.json()) as CoverageReport;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Test Intelligence
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          Test suite analysis — coverage, flaky tests, missing tests, mutation readiness
        </p>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <MetricCard label="Total Tests" value={analysis?.total_tests ?? 0} />
        <MetricCard label="Test Files" value={analysis?.total_files ?? 0} />
        <MetricCard label="Fixtures" value={analysis?.total_fixtures ?? 0} />
        <MetricCard label="Unused Fixtures" value={analysis?.unused_fixtures.length ?? 0} />
        <MetricCard label="Long-Running" value={analysis?.long_running_tests.length ?? 0} />
        <MetricCard label="Flaky Candidates" value={analysis?.flaky_candidates.length ?? 0} />
        <MetricCard label="Missing Tests" value={analysis?.missing_tests.length ?? 0} />
        <MetricCard label="Mutation Readiness" value={`${((analysis?.mutation_readiness ?? 0) * 100).toFixed(0)}%`} />
        <MetricCard label="Coverage" value={`${(coverage?.overall_pct ?? 0).toFixed(1)}%`} />
      </section>

      <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <div style={panelStyle}>
          <h2 style={h2Style}>Tests by Type</h2>
          {analysis && Object.keys(analysis.by_type).length > 0 ? (
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {Object.entries(analysis.by_type).map(([t, n]) => (
                <li key={t} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0', borderBottom: '1px solid var(--color-border)' }}>
                  <span style={{ textTransform: 'capitalize' }}>{t}</span>
                  <span style={{ color: 'var(--color-muted)' }}>{n}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ color: 'var(--color-muted)' }}>No test data.</p>
          )}
        </div>
        <div style={panelStyle}>
          <h2 style={h2Style}>Coverage by Directory</h2>
          {coverage && Object.keys(coverage.by_directory).length > 0 ? (
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {Object.entries(coverage.by_directory)
                .sort(([, a], [, b]) => a - b)
                .slice(0, 15)
                .map(([d, c]) => (
                  <li key={d} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0', borderBottom: '1px solid var(--color-border)' }}>
                    <span>{d}</span>
                    <span style={{ color: c < 50 ? '#991b1b' : c < 80 ? '#854d0e' : '#166534' }}>{c.toFixed(1)}%</span>
                  </li>
                ))}
            </ul>
          ) : (
            <p style={{ color: 'var(--color-muted)' }}>No coverage data.</p>
          )}
        </div>
      </section>
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
