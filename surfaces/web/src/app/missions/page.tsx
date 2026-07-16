import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface Mission {
  mission_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  budget: { total_usd: number; spent_usd: number; utilization_pct: number };
  wbs_nodes: unknown[];
  decisions: unknown[];
  artifacts: unknown[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  owner: string | null;
  tags: string[];
  metrics: { completion_pct: number };
}

interface MissionListResponse {
  missions: Mission[];
  count: number;
}

export default async function MissionsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const params = await searchParams;
  const queryParams = new URLSearchParams();
  queryParams.set('limit', '100');
  if (params.status) queryParams.set('status', params.status);

  let missions: Mission[] = [];
  let error: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/missions?${queryParams}`, {
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as MissionListResponse;
    missions = data.missions ?? [];
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const statusColors: Record<string, string> = {
    created: '#6b7280',
    planning: '#3b82f6',
    ready: '#8b5cf6',
    executing: '#22c55e',
    paused: '#f59e0b',
    completed: '#10b981',
    failed: '#ef4444',
    cancelled: '#6b7280',
  };

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
          Mission Center
        </h1>
        <p
          style={{
            color: 'var(--color-muted)',
            marginTop: '0.25rem',
            fontSize: '0.875rem',
          }}
        >
          Autonomous mission execution — create, monitor, and manage long-running objectives
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

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <Link
          href="/missions"
          style={{
            padding: '0.4rem 0.8rem',
            borderRadius: '0.375rem',
            border: '1px solid var(--color-border)',
            backgroundColor: !params.status ? 'var(--color-accent)' : 'var(--color-card)',
            color: !params.status ? 'var(--color-accent-fg)' : 'var(--color-fg)',
            fontSize: '0.8rem',
            textDecoration: 'none',
          }}
        >
          All ({missions.length})
        </Link>
        {['executing', 'paused', 'completed', 'failed', 'cancelled'].map((s) => (
          <Link
            key={s}
            href={`/missions?status=${s}`}
            style={{
              padding: '0.4rem 0.8rem',
              borderRadius: '0.375rem',
              border: '1px solid var(--color-border)',
              backgroundColor: params.status === s ? 'var(--color-accent)' : 'var(--color-card)',
              color: params.status === s ? 'var(--color-accent-fg)' : 'var(--color-fg)',
              fontSize: '0.8rem',
              textDecoration: 'none',
            }}
          >
            {s}
          </Link>
        ))}
      </div>

      {missions.length === 0 && !error ? (
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
            No missions yet.
          </p>
          <p style={{ fontSize: '0.8rem' }}>
            Create a mission with <code>aaios mission create --title "My Mission"</code>
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
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--color-border)' }}>
                <th style={thStyle}>Title</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Priority</th>
                <th style={thStyle}>Progress</th>
                <th style={thStyle}>WBS</th>
                <th style={thStyle}>Budget</th>
                <th style={thStyle}>Created</th>
              </tr>
            </thead>
            <tbody>
              {missions.map((m) => {
                const statusColor = statusColors[m.status] || '#6b7280';
                return (
                  <tr
                    key={m.mission_id}
                    style={{ borderBottom: '1px solid var(--color-border)' }}
                  >
                    <td style={tdStyle}>
                      <Link
                        href={`/missions/${m.mission_id}`}
                        style={{ color: 'var(--color-accent)', textDecoration: 'none' }}
                      >
                        {m.title}
                      </Link>
                    </td>
                    <td style={{ ...tdStyle, color: statusColor, fontWeight: 600 }}>
                      {m.status}
                    </td>
                    <td style={{ ...tdStyle, color: 'var(--color-muted)' }}>
                      {m.priority}
                    </td>
                    <td style={tdStyle}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div
                          style={{
                            width: '60px',
                            height: '6px',
                            backgroundColor: 'var(--color-bg)',
                            borderRadius: '3px',
                            overflow: 'hidden',
                          }}
                        >
                          <div
                            style={{
                              height: '100%',
                              width: `${m.metrics?.completion_pct || 0}%`,
                              backgroundColor: 'var(--color-accent)',
                            }}
                          />
                        </div>
                        <span style={{ fontSize: '0.7rem', color: 'var(--color-muted)' }}>
                          {m.metrics?.completion_pct?.toFixed(0) || 0}%
                        </span>
                      </div>
                    </td>
                    <td style={tdStyle}>{m.wbs_nodes?.length || 0}</td>
                    <td style={tdStyle}>
                      ${m.budget?.spent_usd?.toFixed(2) || '0.00'}/${m.budget?.total_usd?.toFixed(2) || '0.00'}
                    </td>
                    <td style={{ ...tdStyle, color: 'var(--color-muted)' }}>
                      {m.created_at?.slice(0, 10) || '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
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
