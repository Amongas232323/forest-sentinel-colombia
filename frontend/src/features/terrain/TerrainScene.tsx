"use client";

import { OrbitControls, useTexture } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useState } from "react";
import { NearestFilter, PlaneGeometry, SRGBColorSpace, type Texture } from "three";
import { fetchHeightGrid, type HeightGrid } from "./dem";

interface Props {
  /** Tienen que ser los límites exactos de `imageUrl` para que el drapeado quede georreferenciado. */
  bounds: [number, number, number, number];
  imageUrl: string;
  overlayUrl?: string;
  /** [lon, lat] del hallazgo, se muestra como una baliza. */
  marker?: [number, number];
  exaggeration?: number;
}

const SIZE = 10; // unidades de escena para el lado más largo

function buildGeometry(grid: HeightGrid, exaggeration: number): PlaneGeometry {
  const longest = Math.max(grid.spanX, grid.spanY);
  const w = (grid.spanX / longest) * SIZE;
  const h = (grid.spanY / longest) * SIZE;
  const geo = new PlaneGeometry(w, h, grid.width - 1, grid.height - 1);
  const metresToUnits = SIZE / longest;
  const pos = geo.attributes.position!;
  for (let i = 0; i < pos.count; i++) pos.setZ(i, (grid.data[i]! - grid.min) * metresToUnits * exaggeration);
  geo.computeVertexNormals();
  return geo;
}

function Beacon({ grid, bounds, marker, exaggeration }: { grid: HeightGrid; bounds: Props["bounds"]; marker: [number, number]; exaggeration: number }) {
  const [w, s, e, n] = bounds;
  const longest = Math.max(grid.spanX, grid.spanY);
  const W = (grid.spanX / longest) * SIZE;
  const H = (grid.spanY / longest) * SIZE;
  const u = (marker[0] - w) / (e - w);
  const v = (n - marker[1]) / (n - s);
  const col = Math.min(grid.width - 1, Math.max(0, Math.round(u * (grid.width - 1))));
  const row = Math.min(grid.height - 1, Math.max(0, Math.round(v * (grid.height - 1))));
  const ground = (grid.data[row * grid.width + col]! - grid.min) * (SIZE / longest) * exaggeration;
  return (
    <group position={[(u - 0.5) * W, (0.5 - v) * H, ground]}>
      <mesh position={[0, 0, 0.6]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.012, 0.012, 1.2, 8]} />
        <meshBasicMaterial color="#F2F3EA" transparent opacity={0.85} />
      </mesh>
      <mesh position={[0, 0, 0.02]}>
        <ringGeometry args={[0.14, 0.18, 48]} />
        <meshBasicMaterial color="#A82820" transparent opacity={0.9} />
      </mesh>
      <mesh position={[0, 0, 1.22]}>
        <sphereGeometry args={[0.05, 16, 16]} />
        <meshBasicMaterial color="#A82820" />
      </mesh>
    </group>
  );
}

function Surface({ grid, imageUrl, overlayUrl, exaggeration }: { grid: HeightGrid; imageUrl: string; overlayUrl?: string; exaggeration: number }) {
  const urls = overlayUrl ? [imageUrl, overlayUrl] : [imageUrl];
  const textures = useTexture(urls) as Texture[];
  const [image, overlay] = textures;
  image!.colorSpace = SRGBColorSpace;
  if (overlay) {
    overlay.colorSpace = SRGBColorSpace;
    overlay.magFilter = NearestFilter;
  }
  const geometry = useMemo(() => buildGeometry(grid, exaggeration), [grid, exaggeration]);
  return (
    <group>
      <mesh geometry={geometry} receiveShadow>
        <meshStandardMaterial map={image} roughness={0.95} metalness={0} />
      </mesh>
      {overlay && (
        <mesh geometry={geometry} position={[0, 0, 0.004]}>
          <meshBasicMaterial map={overlay} transparent depthWrite={false} polygonOffset polygonOffsetFactor={-2} />
        </mesh>
      )}
    </group>
  );
}

export default function TerrainScene({ bounds, imageUrl, overlayUrl, marker, exaggeration = 2 }: Props) {
  const [grid, setGrid] = useState<HeightGrid | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let alive = true;
    fetchHeightGrid(bounds)
      .then((g) => alive && setGrid(g))
      .catch(() => alive && setError(true));
    return () => {
      alive = false;
    };
  }, [bounds]);

  if (error) return <p className="grid size-full place-items-center p-6 text-center text-sm text-ink-2">No pudimos descargar los datos de elevación. El resto de la evidencia sigue disponible.</p>;
  if (!grid)
    return (
      <div className="grid size-full place-items-center" role="status">
        <p className="font-mono text-xs tracking-[0.2em] text-ink-2 motion-safe:animate-pulse">DESCARGANDO ELEVACIÓN…</p>
      </div>
    );
  return (
    <div className="relative size-full">
      <Canvas camera={{ position: [0, 7, 9], fov: 40 }} dpr={[1, 1.6]} gl={{ antialias: true }}>
        <color attach="background" args={["#ece9df"]} />
        <fog attach="fog" args={["#ece9df", 14, 26]} />
        <ambientLight intensity={0.55} />
        <directionalLight position={[-6, 10, 4]} intensity={1.6} color="#fff4e0" />
        <Suspense fallback={null}>
          <group rotation={[-Math.PI / 2, 0, 0]}>
            <Surface grid={grid} imageUrl={imageUrl} overlayUrl={overlayUrl} exaggeration={exaggeration} />
            {marker && <Beacon grid={grid} bounds={bounds} marker={marker} exaggeration={exaggeration} />}
          </group>
        </Suspense>
        <OrbitControls enableDamping maxPolarAngle={Math.PI / 2.15} minDistance={4} maxDistance={20} />
      </Canvas>
      <p className="pointer-events-none absolute bottom-3 left-3 rounded-xs bg-field px-2 py-1 font-mono text-[0.6875rem] text-ink-2">
        Relieve real ×{exaggeration} · {Math.round(grid.min)}–{Math.round(grid.max)} m s. n. m. · AWS Terrain Tiles
      </p>
    </div>
  );
}
