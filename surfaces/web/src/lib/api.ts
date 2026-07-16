const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

export interface HealthStatus {
  status: string;
  version?: string;
  timestamp?: string;
  error?: string;
}

export async function checkApiHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/healthz`, { cache: 'no-store' });
  if (!res.ok) {
    return { status: 'error', error: `HTTP ${res.status}` };
  }
  return (await res.json()) as HealthStatus;
}

export { API_BASE };
