import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

interface ExecutionEntry {
  execution_id: string;
  domain: string;
  action: string;
  status: string;
  duration_s: number;
  exit_code: number | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

interface ExecutionListResponse {
  executions: ExecutionEntry[];
  count: number;
}

interface ApprovalEntry {
  approval_id: string;
  execution_id: string;
  domain: string;
  action: string;
  description: string;
  risk_level: string;
  status: string;
  requested_at: string;
  expires_at: string;
}

interface ApprovalResponse {
  approvals: ApprovalEntry[];
  count: number;
}

const statusColors: Record<string, string> = {
  succeeded: '#22c55e',
  failed: '#ef4444',
  running: '#3b82f6',
  pending: '#f59e0b',
  queued: '#8b5cf6',
  cancelled: '#6b7280',
  timeout: '#ef4444',
  rejected: '#ef4444',
  approving: '#f59e0b',
  approved: '#22c55e',
  rolled_back: '#6b7280',
};

export default async function ExecutionPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; domain?: string }>;
}) {
  const params = await searchParams;
  const queryParams = new URLSearchParams();
  queryParams.set('limit', '50');
  if (params.status) queryParams.set('status', params.status);
  if (params.domain) queryParams.set('domain', params.domain);

  const [execRes, approvalRes] = await Promise.all([
    fetch(`${API_BASE}/api/v1/execution?${queryParams}`, { cache: 'no-store' }).catch(() => null),
    fetch(`${API_BASE}/api/v1/execution/approvals/pending`, { cache: 'no-store' }).catch(() => null),
  ]);

  let executions: ExecutionEntry[] = [];
  let error: string | null = null;
  let approvals: ApprovalEntry[] = [];

  if (execRes?.ok) {
    const data = (await execRes.json()) as ExecutionListResponse;
    executions = data.executions ?? [];
  } else {
    error = execRes ? `HTTP ${execRes.status}` : 'Connection refused';
  }

  if (approvalRes?.ok) {
    const data = (await approvalRes.json()) as ApprovalResponse;
    approvals = data.approvals ?? [];
  }

  // Group by status
  const running = executions.filter((e) => e.status === 'running');
  const pending = executions.filter((e) => e.status === 'pending' || e.status === 'queued');
  const succeeded = executions.filter((e) => e.status === 'succeeded');
  const failed = executions.filter((e) => e.status === 'failed' || e.status === 'timeout' || e.status === 'rejected');

  return (
    <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: 'var(--color-fg)' }}>
          Execution Center
        </h1>
        <p style={{ color: 'var(--color-muted)', marginTop: '0.25rem', fontSize: '0.875rem' }}>
          Live jobs, approval queue, execution history — secure autonomous execution across 16 domains
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

      {/* KPI cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <KpiCard label="Running" value={running.length} color="#3b82f6" />
        <KpiCard label="Pending" value={pending.length} color="#f59e0b" />
        <KpiCard label="Succeeded" value={succeeded.length} color="#22c55e" />
        <KpiCard label="Failed" value={failed.length} color="#ef4444" />
        <KpiCard label="Approvals" value={approvals.length} color="#8b5cf6" />
      </div>

      {/* Approval Queue */}
      {approvals.length > 0 && (
        <Section title={`Approval Queue (${approvals.length})`}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                <th style={thStyle}>Risk</th>
                <th style={thStyle}>Domain</th>
                <th style={thStyle}>Action</th>
                <th style={thStyle}>Description</th>
                <th style={thStyle}>Requested</th>
                <th style={thStyle}>Expires</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map((a) => {
                const riskColor = a.risk_level === 'critical' ? '#dc2626' : a.risk_level === 'high' ? '#ef4444' : a.risk_level === 'medium' ? '#f59e0b' : '#22c55e';
                return (
                  <tr key={a.approval_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ ...tdStyle, color: riskColor, fontWeight: 600 }}>{a.risk_level}</td>
                    <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{a.domain}</td>
                    <td style={tdStyle}>{a.action}</td>
                    <td style={{ ...tdStyle, maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.description}
                    </td>
                    <td style={{ ...tdStyle, color: 'var(--color-muted)' }}>{a.requested_at?.slice(11, 19)}</td>
                    <td style={{ ...tdStyle, color: 'var(--color-muted)' }}>{a.expires_at?.slice(11, 19)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Section>
      )}

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <Link href="/execution" style={filterBtnStyle(!params.status && !params.domain)}>All</Link>
        {['running', 'pending', 'succeeded', 'failed'].map((s) => (
          <Link key={s} href={`/execution?status=${s}`} style={filterBtnStyle(params.status === s)}>{s}</Link>
        ))}
      </div>

      {/* Execution Table */}
      {executions.length === 0 && !error ? (
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
          <p style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>No executions recorded.</p>
          <p style={{ fontSize: '0.8rem' }}>
            Run <code>aaios exec run --domain terminal --action run_command --param command=echo+hello</code>
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
                <th style={thStyle}>ID</th>
                <th style={thStyle}>Domain</th>
                <th style={thStyle}>Action</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Duration</th>
                <th style={thStyle}>Exit</th>
                <th style={thStyle}>Error</th>
              </tr>
            </thead>
            <tbody>
              {executions.map((e) => {
                const color = statusColors[e.status] || '#6b7280';
                return (
                  <tr key={e.execution_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ ...tdStyle, fontFamily: 'monospace' }}>
                      <Link href={`/execution/${e.execution_id}`} style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>
                        {e.execution_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{e.domain}</td>
                    <td style={{ ...tdStyle, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {e.action}
                    </td>
                    <td style={{ ...tdStyle, color, fontWeight: 600 }}>{e.status}</td>
                    <td style={tdStyle}>{e.duration_s?.toFixed(3) ?? '—'}s</td>
                    <td style={tdStyle}>{e.exit_code ?? '—'}</td>
                    <td style={{ ...tdStyle, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#ef4444' }}>
                      {e.error || '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {executions.length > 0 && (
        <p style={{ marginTop: '1rem', color: 'var(--color-muted)', fontSize: '0.75rem' }}>
          Showing {executions.length} executions
        </p>
      )}
    </main>
  );
}

function KpiCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div
      style={{
        backgroundColor: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: '0.5rem',
        padding: '0.9rem 1.1rem',
      }}
    >
      <div style={{ fontSize: '0.65rem', color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>
        {label}
      </div>
      <div style={{ fontSize: '1.5rem', fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        backgroundColor: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: '0.5rem',
        padding: '1.25rem',
        marginBottom: '1.5rem',
      }}
    >
      <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.75rem' }}>{title}</h3>
      {children}
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.5rem 0.6rem',
  fontWeight: 600,
  color: 'var(--color-muted)',
  fontSize: '0.7rem',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const tdStyle: React.CSSProperties = {
  padding: '0.4rem 0.6rem',
  color: 'var(--color-fg)',
};

const filterBtnStyle = (active: boolean): React.CSSProperties => ({
  padding: '0.3rem 0.7rem',
  borderRadius: '0.375rem',
  border: '1px solid var(--color-border)',
  backgroundColor: active ? 'var(--color-accent)' : 'var(--color-card)',
  color: active ? 'var(--color-accent-fg)' : 'var(--color-fg)',
  fontSize: '0.75rem',
  textDecoration: 'none',
  cursor: 'pointer',
});
