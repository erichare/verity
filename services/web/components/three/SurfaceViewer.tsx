"use client";

import { OrbitControls } from "@react-three/drei";
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

function Heightmap({ grid, isDark }: { grid: number[][]; isDark: boolean }) {
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

  return (
    <mesh geometry={geo}>
      <meshStandardMaterial
        color={isDark ? "#1b2540" : "#9fb0cc"}
        metalness={0.55}
        roughness={0.45}
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
              opacity={0.28}
              side={THREE.DoubleSide}
              depthWrite={false}
            />
          </mesh>
        );
      })}
    </>
  );
}

function Scene({
  grid,
  regions,
  isDark,
}: {
  grid: number[][];
  regions?: AttributionRegion[];
  isDark: boolean;
}) {
  const accent = isDark ? "#c9a063" : "#a9803e";
  return (
    <>
      <ambientLight intensity={isDark ? 0.35 : 0.6} />
      <directionalLight position={[-2, 3, 2]} intensity={isDark ? 2.2 : 1.6} color={isDark ? "#c9a063" : "#f0ece2"} />
      <directionalLight position={[3, 2, -1]} intensity={isDark ? 1.4 : 0.7} color={isDark ? "#6e97c4" : "#cfc9ba"} />
      <group rotation={[-Math.PI / 2, 0, 0]}>
        <Heightmap grid={grid} isDark={isDark} />
        {regions?.length ? <RegionMarkers regions={regions} accent={accent} /> : null}
      </group>
      <OrbitControls
        enablePan={false}
        autoRotate
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
}: {
  grid: number[][];
  regions?: AttributionRegion[];
  className?: string;
}) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = !mounted || resolvedTheme === "dark";

  const small = useMemo(() => downsample(grid), [grid]);

  return (
    <div className={className}>
      <Canvas camera={{ position: [0, 1.9, 2.5], fov: 38 }} dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
        <Scene grid={small} regions={regions} isDark={isDark} />
      </Canvas>
    </div>
  );
}
