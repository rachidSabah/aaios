import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface Experience {
  experience_id: string;
  timestamp: string;
  task_id: string;
  agent_id: string;
  agent_type: string;
  provider: string | null;
  model: string | null;
  capabilities_used: string[];
  goal: string;
  outcome: string;
  success: boolean;
  execution_time_s: number;
  cost_usd: number;
  reflection_score: number;
  qa_score: number;
  failure_reason: string | null;
  recovery_action: string | null;
  confidence: number;
  retries: number;
}

interface ExperienceListResponse {
  experiences: Experience[];
  count: number;
  total: number;
}

export default async function ExperiencePage({
  searchParams,
}: {
  searchParams: Promise<{ agent?: string; outcome?: string; capability?: string }>;
}) {
  const params = await searchParams;
  const queryParams = new URLSearchParams();
  queryParams.set('limit', '100');
  if (params.agent) queryParams.set('agent_id', params.agent);
  if (params.outcome) queryParams.set('outcome', params.outcome);
  if (params.capability) queryParams.set('capability', params.capability);

  let experiences: Experience[] = [];
  let total = 0;
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/experience?${queryParams}`, {
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as ExperienceListResponse;
    experiences = data.experiences ?? [];
    total = data.total ?? 0;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1
          style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            margin: 0,
            color: 'var(--color-fg)',
          }}
        >
          Experience Explorer
        </h1>
        <p
          style={{
            color: 'var(--color-muted)',
            marginTop: '0.25rem',
            fontSize: '0.875rem',
          }}
        >
          Every execution recorded — search, filter, and learn from past results
        </p>
      </header>

      {error && (
        <div
          style={{
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: '0.5rem',
            padding: '1rem 1.5rem',
            marginBottom: '1.5rem',
            color: '#ef4444',
            fontSize: '0.875rem',
          }}
        >
          Could not reach API server: {error}. Start it with <code>aaios dev</code>.
        </div>
      )}

      <div
        style={{
          display: 'flex',
          gap: '1rem',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
        }}
      >
        <Link
          href="/experience"
          style={{
            padding: '0.4rem 0.8rem',
            borderRadius: '0.375rem',
            border: '1px solid var(--color-border)',
            backgroundColor: !params.agent && !params.outcome ? 'var(--color-accent)' : 'var(--color-card)',
            color: !params.agent && !params.outcome ? 'var(--color-accent-fg)' : 'var(--color-fg)',
            fontSize: '0.8rem',
            textDecoration: 'none',
          }}
        >
          All ({total})
        </Link>
        {['success', 'failure'].map((outcome) => (
          <Link
            key={outcome}
            href={`/experience?outcome=${outcome}`}
            style={{
              padding: '0.4rem 0.8rem',
              borderRadius: '0.375rem',
              border: '1px solid var(--color-border)',
              backgroundColor: params.outcome === outcome ? 'var(--color-accent)' : 'var(--color-card)',
              color: params.outcome === outcome ? 'var(--color-accent-fg)' : 'var(--color-fg)',
              fontSize: '0.8rem',
              textDecoration: 'none',
            }}
          >
            {outcome === 'success' ? '✓' : '✗'} {outcome}
          </Link>
        ))}
        <Link
          href="/learning"
          style={{
            marginLeft: 'auto',
            padding: '0.4rem 0.8rem',
            borderRadius: '0.375rem',
            backgroundColor: 'var(--color-accent)',
            color: 'var(--color-accent-fg)',
            fontSize: '0.8rem',
            textDecoration: 'none',
          }}
        >
          Learning Analytics →
        </Link>
      </div>

      {experiences.length === 0 && !error ? (
        <div
          style={{
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: '0.5rem',
            padding: '3rem 1.5rem',
            textAlign: 'center',
            color: 'var(--color-muted)',
          }}
        >
          <p style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>
            No experiences recorded yet.
          </p>
          <p style={{ fontSize: '0.8rem' }}>
            Run tasks with <code>aaios run</code> to generate experience records.
          </p>
        </div>
      ) : (
        <div
          style={{
            backgroundColor: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: '0.5rem',
            overflow: 'hidden',
          }}
        >
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.8rem',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid var(--color-border)' }}>
                <th style={thStyle}>Time</th>
                <th style={thStyle}>Agent</th>
                <th style={thStyle}>Goal</th>
                <th style={thStyle}>Capabilities</th>
                <th style={thStyle}>Outcome</th>
                <th style={thStyle}>Quality</th>
                <th style={thStyle}>Time</th>
                <th style={thStyle}>Cost</th>
              </tr>
            </thead>
            <tbody>
              {experiences.map((exp) => {
                const outcomeColor = exp.outcome === 'success' ? '#22c55e' : '#ef4444';
                return (
                  <tr
                    key={exp.experience_id}
                    style={{ borderBottom: '1px solid var(--color-border)' }}
                  >
                    <td style={tdStyle}>{exp.timestamp.slice(0, 19).replace('T', ' ')}</td>
                    <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{exp.agent_id}</td>
                    <td style={{ ...tdStyle, maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {exp.goal || '—'}
                    </td>
                    <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: '0.7rem' }}>
                      {exp.capabilities_used.join(', ') || '—'}
                    </td>
                    <td style={{ ...tdStyle, color: outcomeColor, fontWeight: 600 }}>
                      {exp.outcome}
                    </td>
                    <td style={tdStyle}>
                      <span title={`reflection=${exp.reflection_score.toFixed(2)} qa=${exp.qa_score.toFixed(2)}`}>
                        {((exp.reflection_score + exp.qa_score) / 2).toFixed(2)}
                      </span>
                    </td>
                    <td style={tdStyle}>{exp.execution_time_s.toFixed(2)}s</td>
                    <td style={tdStyle}>${exp.cost_usd.toFixed(4)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {experiences.length > 0 && (
        <p style={{ marginTop: '1rem', color: 'var(--color-muted)', fontSize: '0.75rem' }}>
          Showing {experiences.length} of {total} experiences
        </p>
      )}
    </main>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.6rem 0.75rem',
  fontWeight: 600,
  color: 'var(--color-muted)',
  fontSize: '0.7rem',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const tdStyle: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  color: 'var(--color-fg)',
};
