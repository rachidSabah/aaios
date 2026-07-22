'use client';

import type { BrainSnapshot } from '@/hooks/useBrainData';

interface TelemetryPanelProps {
  snapshot: BrainSnapshot;
}

export function TelemetryPanel({ snapshot }: TelemetryPanelProps) {
  const { telemetry, event_bus, connections, uptime_s } = snapshot;

  const formatUptime = (s: number) => {
    const days = Math.floor(s / 86400);
    const hours = Math.floor((s % 86400) / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = Math.floor(s % 60);
    if (days > 0) return `${days}d ${hours}h ${mins}m`;
    if (hours > 0) return `${hours}h ${mins}m ${secs}s`;
    return `${mins}m ${secs}s`;
  };

  return (
    <div style={panelStyle}>
      <h3 style={titleStyle}>SYSTEM TELEMETRY</h3>

      {/* Resource gauges */}
      <div style={gaugeGridStyle}>
        <Gauge label="CPU" value={telemetry.cpu_pct} color="#00ffff" />
        <Gauge label="RAM" value={telemetry.ram_pct} color="#00ff88" />
        <Gauge label="GPU" value={telemetry.gpu_pct} color="#ff8800" />
        <Gauge label="NET" value={telemetry.net_pct} color="#aa00ff" />
      </div>

      {/* Event bus stats */}
      <div style={{ marginTop: '12px', ...sectionStyle }}>
        <div style={rowStyle}>
          <span style={labelStyle}>Event Bus</span>
          <span style={{ ...valueStyle, color: event_bus.available ? '#00ff88' : '#ff4444' }}>
            {event_bus.available ? `${event_bus.subscriber_count || 0} subs` : 'offline'}
          </span>
        </div>
        <div style={rowStyle}>
          <span style={labelStyle}>Events/sec</span>
          <span style={valueStyle}>{event_bus.events_per_sec.toFixed(0)}</span>
        </div>
      </div>

      {/* Connection infrastructure */}
      <div style={{ marginTop: '12px', ...sectionStyle }}>
        <div style={rowStyle}>
          <span style={labelStyle}>WebSocket</span>
          <ConnDot active={connections.websocket} />
        </div>
        <div style={rowStyle}>
          <span style={labelStyle}>EventBus</span>
          <ConnDot active={connections.event_bus} />
        </div>
        <div style={rowStyle}>
          <span style={labelStyle}>Database</span>
          <ConnDot active={connections.database} />
        </div>
        <div style={rowStyle}>
          <span style={labelStyle}>MCP Servers</span>
          <span style={valueStyle}>{connections.mcp_servers}/5</span>
        </div>
        <div style={rowStyle}>
          <span style={labelStyle}>Plugins</span>
          <span style={valueStyle}>{connections.plugins_active} active</span>
        </div>
      </div>

      {/* Uptime */}
      <div style={{ marginTop: '12px', ...sectionStyle }}>
        <div style={rowStyle}>
          <span style={labelStyle}>Uptime</span>
          <span style={valueStyle}>{formatUptime(uptime_s)}</span>
        </div>
      </div>
    </div>
  );
}

function Gauge({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ position: 'relative', width: '60px', height: '60px', margin: '0 auto' }}>
        <svg width="60" height="60" viewBox="0 0 60 60">
          <circle cx="30" cy="30" r="25" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="4" />
          <circle
            cx="30"
            cy="30"
            r="25"
            fill="none"
            stroke={color}
            strokeWidth="4"
            strokeDasharray={`${(pct / 100) * 157} 157`}
            strokeDashoffset="0"
            transform="rotate(-90 30 30)"
            style={{ transition: 'stroke-dasharray 0.5s ease', filter: `drop-shadow(0 0 4px ${color})` }}
          />
        </svg>
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            fontSize: '12px',
            fontWeight: 700,
            color,
          }}
        >
          {pct.toFixed(0)}%
        </div>
      </div>
      <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.6)', marginTop: '4px' }}>{label}</div>
    </div>
  );
}

function ConnDot({ active }: { active: boolean }) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        background: active ? '#00ff88' : '#ff4444',
        boxShadow: active ? '0 0 6px #00ff88' : '0 0 6px #ff4444',
      }}
    />
  );
}

const panelStyle: React.CSSProperties = {
  background: 'rgba(5, 10, 25, 0.85)',
  border: '1px solid rgba(0, 255, 255, 0.2)',
  borderRadius: '8px',
  padding: '12px',
  backdropFilter: 'blur(10px)',
};

const titleStyle: React.CSSProperties = {
  margin: '0 0 10px 0',
  fontSize: '11px',
  fontWeight: 600,
  color: 'rgba(0, 255, 255, 0.8)',
  textTransform: 'uppercase',
  letterSpacing: '0.1em',
};

const gaugeGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(4, 1fr)',
  gap: '8px',
};

const sectionStyle: React.CSSProperties = {
  background: 'rgba(0, 0, 0, 0.3)',
  borderRadius: '6px',
  padding: '8px',
};

const rowStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '2px 0',
};

const labelStyle: React.CSSProperties = {
  fontSize: '11px',
  color: 'rgba(255, 255, 255, 0.6)',
};

const valueStyle: React.CSSProperties = {
  fontSize: '12px',
  fontWeight: 600,
  color: 'rgba(255, 255, 255, 0.9)',
  fontFamily: 'monospace',
};
