'use client';

import { useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';
import { BrainMesh } from './BrainMesh';
import { NeuralConnections } from './NeuralConnections';
import type { BrainNode, NeuralLink } from '@/hooks/useBrainData';

interface BrainSceneProps {
  nodes: BrainNode[];
  links: NeuralLink[];
  onNodeClick?: (node: BrainNode) => void;
  selectedNodeId?: string;
}

export function BrainScene({ nodes, links, onNodeClick, selectedNodeId }: BrainSceneProps) {
  const [autoRotate, setAutoRotate] = useState(true);

  // Compute brain positions in a circle around the central Mission Control
  const { nodePositions, layoutNodes } = useMemo(() => {
    const positions = new Map<string, [number, number, number]>();
    const layout: { node: BrainNode; position: [number, number, number]; scale: number }[] = [];

    // Central Mission Control brain
    const mcNode = nodes.find((n) => n.kind === 'mission_control');
    if (mcNode) {
      positions.set(mcNode.node_id, [0, 0, 0]);
      layout.push({ node: mcNode, position: [0, 0, 0], scale: 2.0 });
    }

    // Provider brains in a circle
    const providerNodes = nodes.filter((n) => n.kind === 'provider');
    const radius = Math.max(4, providerNodes.length * 0.8);
    providerNodes.forEach((node, i) => {
      const angle = (i / Math.max(1, providerNodes.length)) * Math.PI * 2;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      const y = Math.sin(i * 0.5) * 0.5; // slight vertical variation
      const pos: [number, number, number] = [x, y, z];
      positions.set(node.node_id, pos);
      layout.push({ node, position: pos, scale: 1.2 });
    });

    return { nodePositions: positions, layoutNodes: layout };
  }, [nodes]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas
        camera={{ position: [0, 3, 12], fov: 50 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
        onPointerMissed={() => setAutoRotate(true)}
      >
        {/* Background stars */}
        <Stars radius={50} depth={20} count={2000} factor={4} saturation={0} fade speed={1} />

        {/* Lighting */}
        <ambientLight intensity={0.3} />
        <pointLight position={[10, 10, 10]} intensity={0.8} color="#00ffff" />
        <pointLight position={[-10, -5, -10]} intensity={0.5} color="#aa00ff" />
        <pointLight position={[0, 10, 0]} intensity={0.3} color="#ffffff" />

        {/* Render all brains */}
        {layoutNodes.map(({ node, position, scale }) => (
          <BrainMesh
            key={node.node_id}
            position={position}
            scale={scale}
            status={node.status}
            activity={node.activity}
            isSelected={selectedNodeId === node.node_id}
            onClick={() => {
              setAutoRotate(false);
              onNodeClick?.(node);
            }}
          />
        ))}

        {/* Neural connections */}
        <NeuralConnections links={links} nodePositions={nodePositions} />

        {/* Camera controls */}
        <OrbitControls
          enablePan
          enableZoom
          enableRotate
          autoRotate={autoRotate}
          autoRotateSpeed={0.5}
          minDistance={5}
          maxDistance={30}
          maxPolarAngle={Math.PI * 0.8}
          minPolarAngle={Math.PI * 0.2}
        />
      </Canvas>

      {/* HUD overlay — camera hint */}
      <div
        style={{
          position: 'absolute',
          bottom: '10px',
          left: '10px',
          color: 'rgba(0, 255, 255, 0.5)',
          fontSize: '11px',
          fontFamily: 'monospace',
          pointerEvents: 'none',
        }}
      >
        ◉ Drag to rotate · Scroll to zoom · Click a brain for details
      </div>
    </div>
  );
}
