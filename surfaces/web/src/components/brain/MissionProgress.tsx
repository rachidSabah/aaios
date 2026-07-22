'use client';

import type { BrainSnapshot } from '@/hooks/useBrainData';

interface MissionProgressProps {
  snapshot: BrainSnapshot;
}

export function MissionProgress({ snapshot }: MissionProgressProps) {
  const { missions, tasks, nodes } = snapshot;

  const runningTasks = tasks.filter((t) => t.status === 'running').length;
  const completedTasks = tasks.filter((t) => t.status === 'completed').length;
  const waitingTasks = tasks.filter((t) => t.status === 'waiting' || t.status === 'queued').length;
  const failedTasks = tasks.filter((t) => t.status === 'failed').length;

  // Task distribution per provider
  const providerNodes = nodes.filter((n) => n.kind === 'provider');
  const maxTasks = Math.max(1, ...providerNodes.map((n) => n.running_tasks));

  return (
    <div style={panelStyle}>
      <h3 style={titleStyle}>MISSION PROGRESS</h3>

      {/* Overall progress bar */}
      <div style={{ marginBottom: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={labelStyle}>Overall Progress</span>
          <span style={{ ...valueStyle, color: '#00ffff' }}>
            {(missions.overall_progress * 100).toFixed(0)}%
          </span>
        </div>
        <div style={barBgStyle}>
          <div
            style={{
              ...barFgStyle,
              width: `${missions.overall_progress * 100}%`,
              background: 'linear-gradient(90deg, #00ffff, #0088ff)',
            }}
          />
        </div>
      </div>

      {/* Task status grid */}
      <div style={taskGridStyle}>
        <TaskStat label="Running" count={runningTasks} color="#00ffff" />
        <TaskStat label="Completed" count={completedTasks} color="#00ff88" />
        <TaskStat label="Waiting" count={waitingTasks} color="#ffaa00" />
        <TaskStat label="Failed" count={failedTasks} color="#ff4444" />
      </div>

      {/* Task distribution bar chart */}
      <div style={{ marginTop: '12px' }}>
        <div style={{ ...labelStyle, marginBottom: '6px' }}>Task Distribution</div>
        {providerNodes.length === 0 ? (
          <div style={emptyStyle}>No providers connected</div>
        ) : (
          providerNodes.map((node) => (
            <div key={node.node_id} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span style={{ ...labelStyle, width: '80px', fontSize: '10px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {node.name}
              </span>
              <div style={{ flex: 1, ...barBgStyle, height: '14px' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${(node.running_tasks / maxTasks) * 100}%`,
                    background: statusColor(node.status),
                    borderRadius: '3px',
                    transition: 'width 0.5s ease',
                  }}
                />
              </div>
              <span style={{ ...valueStyle, width: '20px', textAlign: 'right' }}>
                {node.running_tasks}
              </span>
            </div>
          ))
        )}
      </div>

      {/* Mission summary */}
      <div style={{ marginTop: '12px', ...sectionStyle }}>
        <div style={rowStyle}>
          <span style={labelStyle}>Total Missions</span>
          <span style={valueStyle}>{missions.total}</span>
        </div>
        <div style={rowStyle}>
          <span style={labelStyle}>Active</span>
          <span style={{ ...valueStyle, color: '#00ffff' }}>{missions.active}</span>
        </div>
        <div style={rowStyle}>
          <span style={labelStyle}>Completed</span>
          <span style={{ ...valueStyle, color: '#00ff88' }}>{missions.completed}</span>
        </div>
        <div style={rowStyle}>
          <span style={labelStyle}>Failed</span>
          <span style={{ ...valueStyle, color: '#ff4444' }}>{missions.failed}</span>
        </div>
      </div>
    </div>
  );
}

function TaskStat({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div style={{ textAlign: 'center', ...sectionStyle }}>
      <div style={{ fontSize: '20px', fontWeight: 700, color }}>{count}</div>
      <div style={{ fontSize: '9px', color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase' }}>{label}</div>
    </div>
  );
}

function statusColor(status: string): string {
  const colors: Record<string, string> = {
    active: '#00ffff',
    busy: '#ff8800',
    idle: '#4488ff',
    offline: '#666666',
    error: '#ff4444',
  };
  return colors[status] || '#4488ff';
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

const taskGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(4, 1fr)',
  gap: '6px',
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

const barBgStyle: React.CSSProperties = {
  background: 'rgba(255, 255, 255, 0.1)',
  borderRadius: '3px',
  height: '8px',
  overflow: 'hidden',
};

const barFgStyle: React.CSSProperties = {
  height: '100%',
  borderRadius: '3px',
  transition: 'width 0.5s ease',
};

const emptyStyle: React.CSSProperties = {
  color: 'rgba(255, 255, 255, 0.3)',
  fontStyle: 'italic',
  padding: '8px 0',
  fontSize: '11px',
};
