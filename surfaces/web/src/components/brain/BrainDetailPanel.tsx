'use client';

import type { BrainNode } from '@/hooks/useBrainData';

interface BrainDetailPanelProps {
  node: BrainNode | null;
  onClose: () => void;
}

export function BrainDetailPanel({ node, onClose }: BrainDetailPanelProps) {
  if (!node) return null;

  const statusColor =
    node.status === 'active' ? '#00ffff' :
    node.status === 'busy' ? '#ff8800' :
    node.status === 'error' ? '#ff4444' :
    node.status === 'offline' ? '#666666' : '#4488ff';

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={panelStyle} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={headerStyle}>
          <div>
            <h2 style={nameStyle}>{node.name}</h2>
            <div style={subStyle}>
              {node.kind === 'mission_control' ? 'Central Orchestrator' : `${node.provider} · ${node.kind}`}
            </div>
          </div>
          <button style={closeBtnStyle} onClick={onClose}>✕</button>
        </div>

        {/* Status badge */}
        <div style={{ ...badgeStyle, color: statusColor, borderColor: statusColor }}>
          ● {node.status.toUpperCase()} · {node.health.toUpperCase()}
          {node.activity !== 'idle' && ` · ${node.activity.toUpperCase()}`}
        </div>

        {/* Metrics grid */}
        <div style={metricsGridStyle}>
          <Metric label="CPU" value={`${node.cpu_pct.toFixed(1)}%`} />
          <Metric label="RAM" value={`${node.ram_pct.toFixed(1)}%`} />
          <Metric label="GPU" value={`${node.gpu_pct.toFixed(1)}%`} />
          <Metric label="NET" value={`${node.net_pct.toFixed(1)}%`} />
          <Metric label="Latency" value={`${node.latency_ms.toFixed(0)}ms`} />
          <Metric label="Tokens/s" value={node.tokens_per_sec.toFixed(0)} />
          <Metric label="Missions" value={String(node.mission_count)} />
          <Metric label="Running Tasks" value={String(node.running_tasks)} />
          <Metric label="Queue" value={String(node.queue_length)} />
          <Metric label="Success Rate" value={`${(node.success_rate * 100).toFixed(1)}%`} />
          <Metric label="Failures" value={String(node.consecutive_failures)} />
          <Metric label="Models" value={String(node.models.length)} />
        </div>

        {/* Current model */}
        {node.current_model && (
          <div style={sectionStyle}>
            <div style={sectionTitleStyle}>Current Model</div>
            <div style={modelStyle}>{node.current_model}</div>
          </div>
        )}

        {/* Available models */}
        {node.models.length > 0 && (
          <div style={sectionStyle}>
            <div style={sectionTitleStyle}>Available Models ({node.models.length})</div>
            <div style={modelListStyle}>
              {node.models.map((m) => (
                <span key={m} style={modelChipStyle}>{m}</span>
              ))}
            </div>
          </div>
        )}

        {/* Capabilities */}
        {node.capabilities.length > 0 && (
          <div style={sectionStyle}>
            <div style={sectionTitleStyle}>Capabilities ({node.capabilities.length})</div>
            <div style={capListStyle}>
              {node.capabilities.map((c) => (
                <span key={c} style={capChipStyle}>{c}</span>
              ))}
            </div>
          </div>
        )}

        {/* Last error */}
        {node.last_error && (
          <div style={{ ...sectionStyle, borderColor: 'rgba(255, 68, 68, 0.3)' }}>
            <div style={{ ...sectionTitleStyle, color: '#ff4444' }}>Last Error</div>
            <div style={{ fontSize: '11px', color: '#ff8888', fontFamily: 'monospace' }}>
              {node.last_error}
            </div>
          </div>
        )}

        {/* Version */}
        {node.version && (
          <div style={sectionStyle}>
            <div style={sectionTitleStyle}>Version</div>
            <div style={{ fontSize: '12px', fontFamily: 'monospace', color: 'rgba(255,255,255,0.7)' }}>
              {node.version}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={metricStyle}>
      <div style={metricLabelStyle}>{label}</div>
      <div style={metricValueStyle}>{value}</div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  top: 0, left: 0, right: 0, bottom: 0,
  background: 'rgba(0, 0, 0, 0.7)',
  backdropFilter: 'blur(4px)',
  zIndex: 1000,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '2rem',
};

const panelStyle: React.CSSProperties = {
  background: 'rgba(5, 10, 25, 0.95)',
  border: '1px solid rgba(0, 255, 255, 0.3)',
  borderRadius: '12px',
  padding: '24px',
  maxWidth: '600px',
  width: '100%',
  maxHeight: '80vh',
  overflowY: 'auto',
  boxShadow: '0 0 40px rgba(0, 255, 255, 0.15)',
};

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  marginBottom: '12px',
};

const nameStyle: React.CSSProperties = {
  margin: 0,
  fontSize: '24px',
  fontWeight: 700,
  color: '#ffffff',
};

const subStyle: React.CSSProperties = {
  fontSize: '12px',
  color: 'rgba(255, 255, 255, 0.5)',
  marginTop: '2px',
};

const closeBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'rgba(255, 255, 255, 0.5)',
  fontSize: '20px',
  cursor: 'pointer',
  padding: '0 4px',
};

const badgeStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '4px 12px',
  borderRadius: '4px',
  border: '1px solid',
  fontSize: '11px',
  fontWeight: 600,
  letterSpacing: '0.05em',
  marginBottom: '16px',
};

const metricsGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(4, 1fr)',
  gap: '8px',
  marginBottom: '16px',
};

const metricStyle: React.CSSProperties = {
  background: 'rgba(0, 0, 0, 0.3)',
  borderRadius: '6px',
  padding: '8px',
  textAlign: 'center',
};

const metricLabelStyle: React.CSSProperties = {
  fontSize: '9px',
  color: 'rgba(255, 255, 255, 0.5)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const metricValueStyle: React.CSSProperties = {
  fontSize: '14px',
  fontWeight: 700,
  color: '#00ffff',
  fontFamily: 'monospace',
  marginTop: '2px',
};

const sectionStyle: React.CSSProperties = {
  background: 'rgba(0, 0, 0, 0.3)',
  borderRadius: '6px',
  padding: '12px',
  marginBottom: '8px',
  border: '1px solid rgba(255, 255, 255, 0.05)',
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: '11px',
  fontWeight: 600,
  color: 'rgba(0, 255, 255, 0.7)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: '8px',
};

const modelStyle: React.CSSProperties = {
  fontSize: '14px',
  fontFamily: 'monospace',
  color: '#00ff88',
};

const modelListStyle: React.CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '4px',
};

const modelChipStyle: React.CSSProperties = {
  fontSize: '10px',
  fontFamily: 'monospace',
  padding: '2px 6px',
  borderRadius: '3px',
  background: 'rgba(0, 255, 136, 0.1)',
  border: '1px solid rgba(0, 255, 136, 0.3)',
  color: 'rgba(0, 255, 136, 0.8)',
};

const capListStyle: React.CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '4px',
};

const capChipStyle: React.CSSProperties = {
  fontSize: '10px',
  padding: '2px 6px',
  borderRadius: '3px',
  background: 'rgba(0, 255, 255, 0.1)',
  border: '1px solid rgba(0, 255, 255, 0.3)',
  color: 'rgba(0, 255, 255, 0.8)',
};
