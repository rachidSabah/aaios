'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

export interface BrainNode {
  node_id: string;
  name: string;
  provider: string;
  kind: 'provider' | 'mission_control';
  status: 'active' | 'busy' | 'idle' | 'offline' | 'error';
  health: 'healthy' | 'degraded' | 'down' | 'unknown';
  version: string;
  current_model: string;
  latency_ms: number;
  cpu_pct: number;
  ram_pct: number;
  gpu_pct: number;
  net_pct: number;
  tokens_per_sec: number;
  mission_count: number;
  running_tasks: number;
  queue_length: number;
  activity: string;
  capabilities: string[];
  models: string[];
  success_rate: number;
  consecutive_failures: number;
  last_error: string;
}

export interface NeuralLink {
  link_id: string;
  source: string;
  target: string;
  kind: string;
  messages_per_min: number;
  latency_ms: number;
  bandwidth: number;
  active: boolean;
  error_count: number;
}

export interface TaskPacket {
  packet_id: string;
  task_id: string;
  mission_id: string;
  title: string;
  status: string;
  progress: number;
  assigned_to: string;
  started_at: string;
  duration_s: number;
}

export interface BrainSnapshot {
  snapshot_id: string;
  timestamp: string;
  nodes: BrainNode[];
  links: NeuralLink[];
  tasks: TaskPacket[];
  telemetry: {
    cpu_pct: number;
    ram_pct: number;
    gpu_pct: number;
    net_pct: number;
    available: boolean;
  };
  event_bus: {
    available: boolean;
    subscriber_count?: number;
    topics?: string[];
    events_per_sec: number;
  };
  connections: {
    websocket: boolean;
    event_bus: boolean;
    database: boolean;
    mcp_servers: number;
    plugins_active: number;
  };
  missions: {
    available: boolean;
    total: number;
    active: number;
    completed: number;
    failed: number;
    waiting: number;
    overall_progress: number;
  };
  live_events: Array<{
    timestamp: string;
    topic: string;
    message: string;
    level: string;
  }>;
  uptime_s: number;
}

interface UseBrainDataOptions {
  websocket?: boolean;
  pollInterval?: number;
}

export function useBrainData(options: UseBrainDataOptions = {}) {
  const { websocket = true, pollInterval = 5000 } = options;
  const [snapshot, setSnapshot] = useState<BrainSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const fetchSnapshot = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/brain/snapshot`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as BrainSnapshot;
      setSnapshot(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchSnapshot();
  }, [fetchSnapshot]);

  // WebSocket connection
  useEffect(() => {
    if (!websocket) {
      // Fall back to polling
      pollRef.current = setInterval(fetchSnapshot, pollInterval);
      return () => {
        if (pollRef.current) clearInterval(pollRef.current);
      };
    }

    let reconnectTimer: NodeJS.Timeout | null = null;

    const connect = () => {
      const wsUrl = API_BASE.replace('http', 'ws') + '/ws/brain';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as BrainSnapshot;
          setSnapshot(data);
          setLoading(false);
        } catch {
          // ignore parse errors
        }
      };

      ws.onerror = () => {
        setConnected(false);
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconnect after 3 seconds
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [websocket, pollInterval, fetchSnapshot]);

  return { snapshot, loading, error, connected, refetch: fetchSnapshot };
}
