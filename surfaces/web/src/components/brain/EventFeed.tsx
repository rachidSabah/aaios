'use client';

import type { BrainSnapshot } from '@/hooks/useBrainData';

interface EventFeedProps {
  snapshot: BrainSnapshot;
}

export function EventFeed({ snapshot }: EventFeedProps) {
  const events = snapshot.live_events.slice(0, 20).reverse();

  return (
    <div style={panelStyle}>
      <h3 style={titleStyle}>LIVE EVENTS</h3>
      <div style={feedStyle}>
        {events.length === 0 ? (
          <div style={emptyStyle}>No events — event bus may be idle</div>
        ) : (
          events.map((event, i) => {
            const time = new Date(event.timestamp).toLocaleTimeString();
            const levelColor =
              event.level === 'error' ? '#ff4444' :
              event.level === 'warning' ? '#ffaa00' :
              event.level === 'success' ? '#00ff88' :
              'rgba(0, 255, 255, 0.7)';
            return (
              <div key={i} style={eventStyle}>
                <span style={timeStyle}>{time}</span>
                <span style={{ ...topicStyle, color: levelColor }}>[{event.topic}]</span>
                <span style={messageStyle}>{event.message}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  background: 'rgba(5, 10, 25, 0.85)',
  border: '1px solid rgba(0, 255, 255, 0.2)',
  borderRadius: '8px',
  padding: '12px',
  backdropFilter: 'blur(10px)',
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
};

const titleStyle: React.CSSProperties = {
  margin: '0 0 8px 0',
  fontSize: '11px',
  fontWeight: 600,
  color: 'rgba(0, 255, 255, 0.8)',
  textTransform: 'uppercase',
  letterSpacing: '0.1em',
  flexShrink: 0,
};

const feedStyle: React.CSSProperties = {
  overflowY: 'auto',
  flex: 1,
  fontSize: '11px',
  fontFamily: 'monospace',
};

const eventStyle: React.CSSProperties = {
  padding: '3px 0',
  borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
  display: 'flex',
  gap: '6px',
  alignItems: 'baseline',
};

const timeStyle: React.CSSProperties = {
  color: 'rgba(255, 255, 255, 0.4)',
  flexShrink: 0,
};

const topicStyle: React.CSSProperties = {
  fontWeight: 600,
  flexShrink: 0,
};

const messageStyle: React.CSSProperties = {
  color: 'rgba(255, 255, 255, 0.7)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const emptyStyle: React.CSSProperties = {
  color: 'rgba(255, 255, 255, 0.3)',
  fontStyle: 'italic',
  padding: '10px 0',
};
