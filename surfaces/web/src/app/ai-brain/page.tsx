'use client';

import { useState } from 'react';
import { useBrainData, type BrainNode } from '@/hooks/useBrainData';
import { BrainScene } from '@/components/brain/BrainScene';
import { TelemetryPanel } from '@/components/brain/TelemetryPanel';
import { EventFeed } from '@/components/brain/EventFeed';
import { MissionProgress } from '@/components/brain/MissionProgress';
import { BrainDetailPanel } from '@/components/brain/BrainDetailPanel';

export default function AIBrainPage() {
  const { snapshot, loading, error, connected } = useBrainData({ websocket: true });
  const [selectedNode, setSelectedNode] = useState<BrainNode | null>(null);

  if (loading) {
    return (
      <div style={loadingStyle}>
        <div style={spinnerStyle} />
        <p style={{ color: 'rgba(0, 255, 255, 0.6)', marginTop: '12px' }}>
          Initializing neural interface...
        </p>
      </div>
    );
  }

  if (error && !snapshot) {
    return (
      <div style={errorStyle}>
        <h2 style={{ color: '#ff4444', marginBottom: '8px' }}>Connection Failed</h2>
        <p style={{ color: 'rgba(255, 255, 255, 0.6)' }}>{error}</p>
        <p style={{ color: 'rgba(255, 255, 255, 0.4)', fontSize: '12px', marginTop: '8px' }}>
          Make sure the AAiOS API server is running on port 8000.
        </p>
      </div>
    );
  }

  if (!snapshot) return null;

  const providerCount = snapshot.nodes.filter((n) => n.kind === 'provider').length;
  const activeCount = snapshot.nodes.filter((n) => n.status === 'active' || n.status === 'busy').length;

  return (
    <div style={pageStyle}>
      {/* Top header bar */}
      <header style={headerStyle}>
        <div style={headerLeftStyle}>
          <h1 style={titleStyle}>AI Brain Constellation</h1>
          <span style={subtitleStyle}>
            {providerCount} providers · {activeCount} active ·{' '}
            <span style={{ color: connected ? '#00ff88' : '#ff4444' }}>
              {connected ? '● LIVE' : '● POLLING'}
            </span>
          </span>
        </div>
        <div style={headerRightStyle}>
          <HeaderStat label="Events/s" value={snapshot.event_bus.events_per_sec.toFixed(0)} />
          <HeaderStat label="Active Tasks" value={String(snapshot.missions.active)} />
          <HeaderStat label="Progress" value={`${(snapshot.missions.overall_progress * 100).toFixed(0)}%`} />
        </div>
      </header>

      {/* Main layout: left panel | 3D brain | right panel */}
      <div style={mainLayoutStyle}>
        {/* Left column: Telemetry + Mission */}
        <div style={leftColumnStyle}>
          <TelemetryPanel snapshot={snapshot} />
          <div style={{ marginTop: '12px' }}>
            <MissionProgress snapshot={snapshot} />
          </div>
        </div>

        {/* Center: 3D Brain Scene */}
        <div style={centerColumnStyle}>
          <BrainScene
            nodes={snapshot.nodes}
            links={snapshot.links}
            onNodeClick={setSelectedNode}
            selectedNodeId={selectedNode?.node_id}
          />
        </div>

        {/* Right column: Event Feed */}
        <div style={rightColumnStyle}>
          <EventFeed snapshot={snapshot} />
        </div>
      </div>

      {/* Detail panel overlay */}
      <BrainDetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  );
}

function HeaderStat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '16px', fontWeight: 700, color: '#00ffff', fontFamily: 'monospace' }}>
        {value}
      </div>
      <div style={{ fontSize: '9px', color: 'rgba(255, 255, 255, 0.5)', textTransform: 'uppercase' }}>
        {label}
      </div>
    </div>
  );
}

const pageStyle: React.CSSProperties = {
  minHeight: '100vh',
  background: 'radial-gradient(ellipse at center, #0a0a20 0%, #000005 100%)',
  color: '#ffffff',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
};

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '12px 20px',
  borderBottom: '1px solid rgba(0, 255, 255, 0.15)',
  background: 'rgba(5, 10, 25, 0.6)',
  backdropFilter: 'blur(10px)',
  flexShrink: 0,
};

const headerLeftStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
};

const titleStyle: React.CSSProperties = {
  margin: 0,
  fontSize: '20px',
  fontWeight: 700,
  color: '#ffffff',
  letterSpacing: '0.02em',
};

const subtitleStyle: React.CSSProperties = {
  fontSize: '12px',
  color: 'rgba(255, 255, 255, 0.5)',
  marginTop: '2px',
  fontFamily: 'monospace',
};

const headerRightStyle: React.CSSProperties = {
  display: 'flex',
  gap: '24px',
};

const mainLayoutStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '260px 1fr 280px',
  gap: '12px',
  padding: '12px',
  flex: 1,
  minHeight: 0,
};

const leftColumnStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  overflowY: 'auto',
};

const centerColumnStyle: React.CSSProperties = {
  background: 'rgba(0, 0, 10, 0.3)',
  borderRadius: '8px',
  border: '1px solid rgba(0, 255, 255, 0.1)',
  overflow: 'hidden',
  position: 'relative',
};

const rightColumnStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  minHeight: 0,
};

const loadingStyle: React.CSSProperties = {
  minHeight: '100vh',
  background: '#000005',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  color: '#ffffff',
};

const spinnerStyle: React.CSSProperties = {
  width: '40px',
  height: '40px',
  border: '3px solid rgba(0, 255, 255, 0.2)',
  borderTopColor: '#00ffff',
  borderRadius: '50%',
  animation: 'spin 1s linear infinite',
};

const errorStyle: React.CSSProperties = {
  minHeight: '100vh',
  background: '#000005',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '2rem',
  textAlign: 'center',
};
