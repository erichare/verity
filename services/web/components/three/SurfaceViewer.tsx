"use client";

import { Environment, Lightformer, OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import type { AttributionRegion } from "@/lib/types";

const PLANE = 2; // surface spans [-1, 1] in local X/Y
const HEIGHT_SCALE = 0.62;
const MAX_SEG = 160; // cap geometry density for big grids

// Subsample a grid so neither dimension exceeds MAX_SEG (keeps the mesh light).
function downsample(grid: number[][]): number[][] {
  const rows = grid.length;
  const cols = grid[0]?.length ?? 0;
  const stride = Math.max(1, Math.ceil(Math.max(rows, cols) / MAX_SEG));
  if (stride === 1) return grid;
  const out: number[][] = [];
  for (let y = 0; y < rows; y += stride) {
    const row: number[] = [];
    for (let x = 0; x < cols; x += stride) row.push(grid[y][x] ?? 0);
    out.push(row);
  }
  return out;
}

// A heightmap surface: the grid's own heights are the relief. For the raw bullet scan that
// includes the gross form (the measured curvature); after form removal it's flat roughness.
function Heightmap({
  grid,
  color,
  metalness,
  roughness,
  envMapIntensity,
}: {
  grid: number[][];
  color: string;
  metalness: number;
  roughness: number;
  envMapIntensity: number;
}) {
  const geo = useMemo(() => {
    const rows = grid.length;
    const cols = grid[0]?.length ?? 1;
    const g = new THREE.PlaneGeometry(PLANE, PLANE, cols - 1, rows - 1);
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const row = Math.floor(i / cols);
      const col = i % cols;
      pos.setZ(i, (grid[row]?.[col] ?? 0) * HEIGHT_SCALE);
    }
    pos.needsUpdate = true;
    g.computeVertexNormals();
    return g;
  }, [grid]);

  useEffect(() => () => geo.dispose(), [geo]);

  return (
    <mesh geometry={geo}>
      <meshStandardMaterial
        color={color}
        metalness={metalness}
        roughness={roughness}
        envMapIntensity={envMapIntensity}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

function RegionMarkers({ regions, accent }: { regions: AttributionRegion[]; accent: string }) {
  const top = HEIGHT_SCALE + 0.06;
  return (
    <>
      {regions.map((r, i) => {
        const lx = -1 + (r.x_frac + r.w_frac / 2) * PLANE;
        const ly = 1 - (r.y_frac + r.h_frac / 2) * PLANE; // frac-y is top-down
        return (
          <mesh key={i} position={[lx, ly, top]}>
            <planeGeometry args={[r.w_frac * PLANE, r.h_frac * PLANE]} />
            <meshBasicMaterial
              color={accent}
              transparent
              opacity={0.3}
              side={THREE.DoubleSide}
              depthWrite={false}
            />
          </mesh>
        );
      })}
    </>
  );
}

// A small procedural studio (rendered into an env map, not shown directly): a couple of
// bright strips against a dark surround give the satin-bronze surface a travelling sheen
// and a tight specular line, without washing out its body — no external HDRI to fetch.
function StudioEnv({ isDark }: { isDark: boolean }) {
  const warm = isDark ? "#e9c98f" : "#fff3da";
  const cool = isDark ? "#7e9fc6" : "#dbe6f4";
  return (
    <Environment key={isDark ? "d" : "l"} frames={1} resolution={256} environmentIntensity={isDark ? 0.4 : 0.32}>
      {/* Dark surround → reflections read as a sheen, not a wash. */}
      <color attach="background" args={["#0a0e16"]} />
      {/* Soft key sweeping from upper-left. */}
      <Lightformer form="rect" intensity={2.6} position={[-3, 5, 3]} scale={[7, 5, 1]} color="#fff7e8" />
      {/* A long, narrow strip → a tight specular line that travels across the striae. */}
      <Lightformer form="rect" intensity={2.4} rotation={[0, Math.PI / 2, 0]} position={[-5, 1, 0]} scale={[8, 1.1, 1]} color={warm} />
      {/* Cool counter-rim from the right. */}
      <Lightformer form="rect" intensity={1.6} rotation={[0, -Math.PI / 2, 0]} position={[5, 0.5, 0]} scale={[6, 3, 1]} color={cool} />
    </Environment>
  );
}

function Scene({
  grid,
  regions,
  autoRotate,
  isDark,
}: {
  grid: number[][];
  regions?: AttributionRegion[];
  autoRotate: boolean;
  isDark: boolean;
}) {
  const accent = isDark ? "#c9a063" : "#a9803e";
  // Warm machined bronze that reads as a metal bullet jacket in both themes.
  const metal = isDark ? "#c19a64" : "#a8854f";
  return (
    <>
      <ambientLight intensity={isDark ? 0.35 : 0.5} />
      {/* Strong key from upper-left → a bright-top / dark-flank falloff that reveals the form,
          plus a specular glint that sweeps across the striae as the surface turns. */}
      <directionalLight
        position={[-3, 4, 2.5]}
        intensity={isDark ? 2.3 : 2.5}
        color={isDark ? "#f3e4c2" : "#fffaf0"}
      />
      <directionalLight position={[3, 1.5, -2]} intensity={isDark ? 0.7 : 0.55} color={isDark ? "#7e9fc6" : "#c4cedd"} />
      <StudioEnv isDark={isDark} />
      <group rotation={[-Math.PI / 2, 0, 0]}>
        <Heightmap
          grid={grid}
          color={metal}
          metalness={0.42}
          roughness={isDark ? 0.48 : 0.46}
          envMapIntensity={isDark ? 0.7 : 0.55}
        />
        {regions?.length ? <RegionMarkers regions={regions} accent={accent} /> : null}
      </group>
      <OrbitControls
        enablePan={false}
        autoRotate={autoRotate}
        autoRotateSpeed={0.7}
        minDistance={1.8}
        maxDistance={5}
        enableDamping
        dampingFactor={0.08}
      />
    </>
  );
}

export default function SurfaceViewer({
  grid,
  regions,
  className,
  autoRotate = true,
}: {
  grid: number[][];
  regions?: AttributionRegion[];
  className?: string;
  /** Auto-rotate the camera. Turn off via the Studio "Animate" toggle. */
  autoRotate?: boolean;
}) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = !mounted || resolvedTheme === "dark";

  const small = useMemo(() => downsample(grid), [grid]);

  return (
    <div className={className}>
      <Canvas camera={{ position: [0, 1.85, 2.95], fov: 38 }} dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
        <Scene grid={small} regions={regions} autoRotate={autoRotate} isDark={isDark} />
      </Canvas>
    </div>
  );
}
