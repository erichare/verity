"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

// Deterministic value noise (no Math.random — stable across renders).
function hash(x: number, y: number): number {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return s - Math.floor(s);
}

function valueNoise(x: number, y: number): number {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const xf = x - xi;
  const yf = y - yi;
  const u = xf * xf * (3 - 2 * xf);
  const v = yf * yf * (3 - 2 * yf);
  const tl = hash(xi, yi);
  const tr = hash(xi + 1, yi);
  const bl = hash(xi, yi + 1);
  const br = hash(xi + 1, yi + 1);
  return THREE.MathUtils.lerp(
    THREE.MathUtils.lerp(tl, tr, u),
    THREE.MathUtils.lerp(bl, br, u),
    v,
  );
}

// A striated micro-surface: parallel grooves (running along y) with individualizing
// breaks + grain — the texture a bullet land or striated toolmark leaves behind.
function striationHeight(x: number, y: number): number {
  let h = 0;
  h += 0.1 * Math.sin(x * 9.0 + Math.sin(y * 0.6) * 0.8); // primary striae (slightly wavy)
  h += 0.05 * Math.sin(x * 21.0 + 1.7); // finer striae
  h += 0.03 * Math.sin(x * 41.0 + valueNoise(x * 2, y * 2) * 3.0); // micro striae
  h += 0.06 * Math.sin(x * 2.2 + 0.4) * Math.cos(y * 1.4); // broad form
  h += 0.045 * (valueNoise(x * 3.0, y * 3.0) - 0.5); // grain
  h += 0.05 * Math.exp(-((x - 0.6) ** 2 + (y + 0.4) ** 2) * 6.0); // individualizing bump
  h -= 0.045 * Math.exp(-((x + 0.9) ** 2 + (y - 0.7) ** 2) * 8.0); // individualizing pit
  return h;
}

function Surface({ isDark }: { isDark: boolean }) {
  const meshRef = useRef<THREE.Mesh>(null);

  const geo = useMemo(() => {
    const g = new THREE.PlaneGeometry(7, 7, 240, 240);
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      pos.setZ(i, striationHeight(pos.getX(i), pos.getY(i)));
    }
    pos.needsUpdate = true;
    g.computeVertexNormals();
    return g;
  }, []);

  useFrame((_, delta) => {
    if (meshRef.current) meshRef.current.rotation.z += delta * 0.045;
  });

  return (
    <mesh ref={meshRef} geometry={geo} rotation={[-Math.PI / 2.5, 0, 0]}>
      <meshStandardMaterial
        color={isDark ? "#0e1a2b" : "#c9c3b4"}
        metalness={0.72}
        roughness={isDark ? 0.34 : 0.5}
        envMapIntensity={0.5}
      />
    </mesh>
  );
}

function Scene({ isDark }: { isDark: boolean }) {
  // Fog color must equal the page canvas (Evidence tokens) or the hero edges seam.
  const bg = isDark ? "#0c1420" : "#f4f1ea";
  return (
    <>
      <fog attach="fog" args={[bg, 4.2, 9.5]} />
      <ambientLight intensity={isDark ? 0.22 : 0.6} />
      {/* Dark mode: archival brass + steel rake light. Light mode: warm paper key
          + cool fill, so the navy "Verity" wordmark reads cleanly over it. */}
      <directionalLight
        position={[-3, 2.6, 2]}
        intensity={isDark ? 2.6 : 2.1}
        color={isDark ? "#c9a063" : "#fbf8f1"}
      />
      <directionalLight
        position={[3.6, 1.1, -1.8]}
        intensity={isDark ? 2.0 : 0.85}
        color={isDark ? "#6e97c4" : "#d8d2c4"}
      />
      <Surface isDark={isDark} />
    </>
  );
}

export default function HeroSurface() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  // Light-first: before mount (and when light) use the paper materials, matching
  // the new default theme and avoiding a dark flash on first paint.
  const isDark = mounted && resolvedTheme === "dark";

  return (
    <Canvas
      className="!absolute inset-0"
      camera={{ position: [0, 2.0, 3.5], fov: 40 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
    >
      <Scene isDark={isDark} />
    </Canvas>
  );
}
