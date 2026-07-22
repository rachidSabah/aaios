'use client';

import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface BrainMeshProps {
  position: [number, number, number];
  scale?: number;
  status: string;
  activity: string;
  isSelected?: boolean;
  onClick?: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  active: '#00ffff',    // cyan
  busy: '#ff8800',      // orange
  idle: '#4488ff',      // blue
  offline: '#666666',   // gray
  error: '#ff0044',     // red
};

const ACTIVITY_COLORS: Record<string, string> = {
  thinking: '#aa00ff',   // violet
  planning: '#0088ff',   // blue
  coding: '#00ff88',     // green
  debugging: '#ff4400',  // dark orange
  searching: '#ffff00',  // yellow
  idle: '#4488ff',       // blue
  offline: '#666666',    // gray
};

export function BrainMesh({
  position,
  scale = 1,
  status,
  activity,
  isSelected = false,
  onClick,
}: BrainMeshProps) {
  const groupRef = useRef<THREE.Group>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const shellRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const particleRef = useRef<THREE.Points>(null);

  const baseColor = useMemo(() => {
    const activityColor = ACTIVITY_COLORS[activity] || ACTIVITY_COLORS.idle;
    const statusColor = STATUS_COLORS[status] || STATUS_COLORS.idle;
    return activity !== 'idle' ? activityColor : statusColor;
  }, [status, activity]);

  const color = useMemo(() => new THREE.Color(baseColor), [baseColor]);

  // Generate neuron positions for the particle shell
  const particleGeometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const count = 200;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 1.15 + Math.random() * 0.1;
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return geo;
  }, []);

  // Generate internal synapse lines
  const synapseGeometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const lineCount = 30;
    const positions = new Float32Array(lineCount * 6);
    for (let i = 0; i < lineCount; i++) {
      const theta1 = Math.random() * Math.PI * 2;
      const phi1 = Math.acos(2 * Math.random() - 1);
      const r1 = 0.8 * Math.random();
      const theta2 = Math.random() * Math.PI * 2;
      const phi2 = Math.acos(2 * Math.random() - 1);
      const r2 = 0.8 * Math.random();
      positions[i * 6] = r1 * Math.sin(phi1) * Math.cos(theta1);
      positions[i * 6 + 1] = r1 * Math.sin(phi1) * Math.sin(theta1);
      positions[i * 6 + 2] = r1 * Math.cos(phi1);
      positions[i * 6 + 3] = r2 * Math.sin(phi2) * Math.cos(theta2);
      positions[i * 6 + 4] = r2 * Math.sin(phi2) * Math.sin(theta2);
      positions[i * 6 + 5] = r2 * Math.cos(phi2);
    }
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    return geo;
  }, []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (groupRef.current) {
      // Breathing effect
      const breath = 1 + Math.sin(t * 0.8) * 0.03;
      groupRef.current.scale.setScalar(scale * breath);
      // Slow rotation
      groupRef.current.rotation.y = t * 0.15;
    }
    if (coreRef.current) {
      const mat = coreRef.current.material as THREE.MeshPhongMaterial;
      // Pulsing emissive intensity based on activity
      const pulseSpeed = activity === 'thinking' ? 3.0 : activity === 'coding' ? 5.0 : activity === 'idle' ? 0.5 : 2.0;
      mat.emissiveIntensity = 0.4 + Math.sin(t * pulseSpeed) * 0.2;
    }
    if (glowRef.current) {
      const mat = glowRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.15 + Math.sin(t * 1.5) * 0.05;
    }
    if (shellRef.current) {
      shellRef.current.rotation.y = -t * 0.1;
      shellRef.current.rotation.x = t * 0.05;
    }
    if (particleRef.current) {
      particleRef.current.rotation.y = t * 0.2;
      particleRef.current.rotation.z = t * 0.1;
    }
  });

  const isOffline = status === 'offline';

  return (
    <group
      ref={groupRef}
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        document.body.style.cursor = 'pointer';
      }}
      onPointerOut={() => {
        document.body.style.cursor = 'auto';
      }}
    >
      {/* Outer glow sphere */}
      <mesh ref={glowRef} scale={1.4}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.15}
          side={THREE.BackSide}
          depthWrite={false}
        />
      </mesh>

      {/* Wireframe shell — rotating particle sphere */}
      <mesh ref={shellRef} scale={1.2}>
        <icosahedronGeometry args={[1, 1]} />
        <meshBasicMaterial
          color={color}
          wireframe
          transparent
          opacity={isOffline ? 0.05 : 0.2}
        />
      </mesh>

      {/* Inner core — glass-like brain */}
      <mesh ref={coreRef}>
        <icosahedronGeometry args={[1, 4]} />
        <meshPhongMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.5}
          transparent
          opacity={isOffline ? 0.15 : 0.7}
          shininess={100}
          specular={new THREE.Color('#ffffff')}
          flatShading
        />
      </mesh>

      {/* Internal synapses */}
      <lineSegments geometry={synapseGeometry}>
        <lineBasicMaterial
          color={color}
          transparent
          opacity={isOffline ? 0.05 : 0.3}
        />
      </lineSegments>

      {/* Particle shell — neurons */}
      <points ref={particleRef} geometry={particleGeometry}>
        <pointsMaterial
          color={color}
          size={0.03}
          transparent
          opacity={isOffline ? 0.1 : 0.6}
          sizeAttenuation
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>

      {/* Selection ring */}
      {isSelected && (
        <mesh rotation={[Math.PI / 2, 0, 0]} scale={1.5}>
          <ringGeometry args={[0.95, 1.05, 32]} />
          <meshBasicMaterial
            color="#ffffff"
            transparent
            opacity={0.8}
            side={THREE.DoubleSide}
          />
        </mesh>
      )}
    </group>
  );
}
