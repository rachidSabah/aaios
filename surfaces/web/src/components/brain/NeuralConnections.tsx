'use client';

import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { NeuralLink } from '@/hooks/useBrainData';

interface NeuralConnectionsProps {
  links: NeuralLink[];
  nodePositions: Map<string, [number, number, number]>;
}

export function NeuralConnections({ links, nodePositions }: NeuralConnectionsProps) {
  return (
    <group>
      {links.map((link) => (
        <NeuralLinkMesh
          key={link.link_id}
          link={link}
          source={nodePositions.get(link.source)}
          target={nodePositions.get(link.target)}
        />
      ))}
    </group>
  );
}

interface NeuralLinkMeshProps {
  link: NeuralLink;
  source?: [number, number, number];
  target?: [number, number, number];
}

function NeuralLinkMesh({ link, source, target }: NeuralLinkMeshProps) {
  const lineRef = useRef<THREE.Line>(null);
  const packetRef = useRef<THREE.Mesh>(null);

  const { points } = useMemo(() => {
    if (!source || !target) {
      return { points: null };
    }
    const s = new THREE.Vector3(...source);
    const e = new THREE.Vector3(...target);
    // Create a curved path (arc upward)
    const mid = s.clone().lerp(e, 0.5);
    mid.y += s.distanceTo(e) * 0.15;
    const curve = new THREE.QuadraticBezierCurve3(s, mid, e);
    const curvePoints = curve.getPoints(32);
    const geo = new THREE.BufferGeometry().setFromPoints(curvePoints);
    return { points: geo };
  }, [source, target]);

  // Color based on link kind
  const color = useMemo(() => {
    const colors: Record<string, string> = {
      event: '#00ffff',
      task: '#ff8800',
      pipeline: '#00ff88',
      memory: '#aa00ff',
      mcp: '#ffff00',
      plugin: '#ff00aa',
    };
    return colors[link.kind] || '#4488ff';
  }, [link.kind]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (packetRef.current && source && target) {
      // Animate packet along the curve
      const speed = link.active ? 0.5 + (link.messages_per_min / 5000) : 0;
      const progress = (t * speed) % 1;
      const s = new THREE.Vector3(...source);
      const e = new THREE.Vector3(...target);
      const mid = s.clone().lerp(e, 0.5);
      mid.y += s.distanceTo(e) * 0.15;
      const curve = new THREE.QuadraticBezierCurve3(s, mid, e);
      const pos = curve.getPoint(progress);
      packetRef.current.position.copy(pos);
      // Scale packet by bandwidth
      const sz = 0.04 + link.bandwidth * 0.06;
      packetRef.current.scale.setScalar(sz);
      // Visibility
      packetRef.current.visible = link.active && link.messages_per_min > 0;
    }
  });

  if (!points || !source || !target) return null;

  const opacity = link.active ? 0.2 + link.bandwidth * 0.3 : 0.05;

  return (
    <group>
      {/* The neural link line */}
      <line ref={lineRef as any}>
        <primitive object={points} attach="geometry" />
        <lineBasicMaterial
          color={color}
          transparent
          opacity={opacity}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </line>

      {/* Traveling data packet */}
      <mesh ref={packetRef}>
        <sphereGeometry args={[1, 8, 8]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.9}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}
