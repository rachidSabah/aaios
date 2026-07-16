const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface OverviewData {
  engine_stats: {
    projects: number;
    sessions: number;
    plans: number;
    tasks: number;
    pipelines: number;
    templates: number;
    memory_entries: number;
    workspaces: number;
    findings: number;
  };
  research_agents: number;
  evidence_graph: {
    nodes: number;
    edges: number;
    claims: number;
    facts: number;
    sources: number;
  };
}

interface AgentInfo {
  agent_type: string;
  display_name: string;
  description: string;
  default_reliability: string;
}

export default async function ResearchPage() {
  let overview: OverviewData | null = null;
  let agents: AgentInfo[] = [];
  let error: string | null = null;
  try {
    const [oRes, aRes] = await Promise.all([
      fetch(`${API_BASE}/api/v1/research/overview`, { cache: 'no-store' }),
      fetch(`${API_BASE}/api/v1/research/agents`, { cache: 'no-store' }),
    ]);
    if (oRes.ok) overview = (await oRes.json()) as OverviewData;
    if (aRes.ok) {
      const aData = await aRes.json() as { agents: AgentInfo[] };
      agents = aData.agents ?? [];
    }
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Research & Reasoning Platform
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          Enterprise research engine, 10 specialized agents, multi-model reasoning, evidence graph, fact verification, knowledge synthesis
        </p>
      </header>

      {error && (
        <div style={errorStyle}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {overview && (
        <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
          <MetricCard label="Projects" value={overview.engine_stats.projects} />
          <MetricCard label="Sessions" value={overview.engine_stats.sessions} />
          <MetricCard label="Plans" value={overview.engine_stats.plans} />
          <MetricCard label="Tasks" value={overview.engine_stats.tasks} />
          <MetricCard label="Pipelines" value={overview.engine_stats.pipelines} />
          <MetricCard label="Templates" value={overview.engine_stats.templates} />
          <MetricCard label="Memory" value={overview.engine_stats.memory_entries} />
          <MetricCard label="Findings" value={overview.engine_stats.findings} />
          <MetricCard label="Research Agents" value={overview.research_agents} />
          <MetricCard label="Graph Nodes" value={overview.evidence_graph.nodes} />
          <MetricCard label="Graph Edges" value={overview.evidence_graph.edges} />
          <MetricCard label="Claims" value={overview.evidence_graph.claims} />
          <MetricCard label="Facts" value={overview.evidence_graph.facts} />
          <MetricCard label="Sources" value={overview.evidence_graph.sources} />
        </section>
      )}

      <section style={panelStyle}>
        <h2 style={h2Style}>Specialized Research Agents ({agents.length})</h2>
        {agents.length === 0 ? (
          <p style={{ color: 'var(--color-muted)' }}>No agents loaded.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem' }}>
            {agents.map(a => (
              <article key={a.agent_type} style={cardStyle}>
                <h3 style={{ margin: '0 0 0.25rem 0', fontSize: '0.95rem', fontWeight: 600 }}>{a.display_name}</h3>
                <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.8rem', color: 'var(--color-muted)' }}>{a.description}</p>
                <span style={{ ...badgeStyle, ...reliabilityColor(a.default_reliability) }}>
                  {a.default_reliability.replace(/_/g, ' ')}
                </span>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function reliabilityColor(reliability: string): React.CSSProperties {
  if (reliability.includes('tier_1')) return { background: '#f0fdf4', color: '#166534' };
  if (reliability.includes('tier_2')) return { background: '#eff6ff', color: '#1e40af' };
  if (reliability.includes('tier_3')) return { background: '#fefce8', color: '#854d0e' };
  return { background: '#f1f5f9', color: '#475569' };
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

const cardStyle: React.CSSProperties = {
  padding: '0.75rem',
  background: 'var(--color-card)',
  border: '1px solid var(--color-border)',
  borderRadius: '6px',
};

const badgeStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '0.125rem 0.5rem',
  borderRadius: '4px',
  fontSize: '0.7rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const h2Style: React.CSSProperties = {
  fontSize: '1.1rem',
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
