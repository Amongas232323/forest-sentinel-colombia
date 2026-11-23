"use client";

import { Line, useTexture } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Suspense, useMemo, useRef } from "react";
import { AdditiveBlending, BackSide, BufferAttribute, BufferGeometry, Group, MathUtils, ShaderMaterial, SRGBColorSpace, type Texture, Vector3 } from "three";
import type { GeoJSONGeometry } from "@/lib/api/types";
import type { GraphicsTier } from "@/lib/device";
import { facingRotation, geometryRings, latLonToVector3, shortestAngle } from "./geo";
import { atmosphereFragment, atmosphereVertex, dustFragment, dustVertex, earthFragment, earthVertex } from "./shaders";
import { useGlobe } from "./store";

export interface GlobeMarker {
  id: string;
  lat: number;
  lon: number;
  label: string;
  tone: "glow" | "amber" | "alert";
  onSelect?: () => void;
}

export interface GlobeSceneProps {
  territories: { slug: string; name: string; geometry: GeoJSONGeometry }[];
  pins: GlobePin[];
  overlay: React.RefObject<HTMLDivElement | null>;
  tier: Exclude<GraphicsTier, "none">;
  paused?: boolean;
}

const SUN = new Vector3(-0.6, 0.35, 1).normalize();

function Earth({ tier }: { tier: GlobeSceneProps["tier"] }) {
  const res = tier === "high" ? "4k" : "2k";
  const [day, night] = useTexture([`/textures/earth-day-${res}.jpg`, `/textures/earth-night-${res}.jpg`]) as [Texture, Texture];
  day.colorSpace = SRGBColorSpace;
  night.colorSpace = SRGBColorSpace;
  day.anisotropy = 4;
  const material = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: earthVertex,
        fragmentShader: earthFragment,
        uniforms: { uDay: { value: day }, uNight: { value: night }, uSun: { value: SUN }, uTime: { value: 0 } },
      }),
    [day, night],
  );
  return (
    <mesh material={material}>
      <sphereGeometry args={[1, tier === "high" ? 128 : 64, tier === "high" ? 96 : 48]} />
    </mesh>
  );
}

function Atmosphere() {
  const material = useMemo(
    () => new ShaderMaterial({ vertexShader: atmosphereVertex, fragmentShader: atmosphereFragment, side: BackSide, transparent: true, blending: AdditiveBlending, depthWrite: false }),
    [],
  );
  return (
    <mesh material={material} scale={1.16}>
      <sphereGeometry args={[1, 64, 48]} />
    </mesh>
  );
}

function Dust({ count }: { count: number }) {
  const { gl } = useThree();
  const geometry = useMemo(() => {
    const g = new BufferGeometry();
    const pos = new Float32Array(count * 3);
    const scale = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      // Capa entre 1.4 y 6 radios: partículas atmosféricas, tipo polen.
      const r = 1.4 + Math.random() * 4.6;
      const t = Math.random() * Math.PI * 2;
      const p = Math.acos(2 * Math.random() - 1);
      pos.set([r * Math.sin(p) * Math.cos(t), r * Math.cos(p), r * Math.sin(p) * Math.sin(t)], i * 3);
      scale[i] = 0.4 + Math.random() * 1.6;
    }
    g.setAttribute("position", new BufferAttribute(pos, 3));
    g.setAttribute("aScale", new BufferAttribute(scale, 1));
    return g;
  }, [count]);
  const material = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: dustVertex,
        fragmentShader: dustFragment,
        transparent: true,
        depthWrite: false,
        blending: AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uPixelRatio: { value: Math.min(gl.getPixelRatio(), 2) } },
      }),
    [gl],
  );
  useFrame((_, dt) => {
    material.uniforms.uTime!.value += dt;
  });
  return <points geometry={geometry} material={material} />;
}

/** Órbita heliosíncrona estilo Sentinel-2 (~98.6° de inclinación). */
function Orbit() {
  const ring = useRef<Group>(null);
  const sat = useRef<Group>(null);
  const points = useMemo(() => Array.from({ length: 181 }, (_, i) => {
    const a = (i / 180) * Math.PI * 2;
    return new Vector3(Math.cos(a) * 1.32, 0, Math.sin(a) * 1.32);
  }), []);
  useFrame((state) => {
    const vis = useGlobe.getState().orbit;
    if (ring.current) {
      ring.current.visible = vis > 0.01;
      ring.current.scale.setScalar(MathUtils.lerp(0.9, 1, vis));
    }
    if (sat.current) {
      const a = state.clock.elapsedTime * 0.35;
      sat.current.position.set(Math.cos(a) * 1.32, 0, Math.sin(a) * 1.32);
      sat.current.rotation.y = -a;
    }
  });
  return (
    <group ref={ring} rotation={[MathUtils.degToRad(98.6 - 90), 0, MathUtils.degToRad(12)]}>
      <Line points={points} color="#91C77A" lineWidth={1} transparent opacity={0.35} dashed dashSize={0.02} gapSize={0.03} />
      <group ref={sat}>
        <mesh>
          <boxGeometry args={[0.018, 0.012, 0.03]} />
          <meshBasicMaterial color="#F2F3EA" />
        </mesh>
        <mesh position={[0.035, 0, 0]}>
          <boxGeometry args={[0.04, 0.002, 0.018]} />
          <meshBasicMaterial color="#91C77A" />
        </mesh>
        <mesh position={[-0.035, 0, 0]}>
          <boxGeometry args={[0.04, 0.002, 0.018]} />
          <meshBasicMaterial color="#91C77A" />
        </mesh>
      </group>
    </group>
  );
}

function TerritoryOutlines({ territories }: Pick<GlobeSceneProps, "territories">) {
  const group = useRef<Group>(null);
  const rings = useMemo(() => territories.map((t) => ({ slug: t.slug, rings: geometryRings(t.geometry, 1.003) })), [territories]);
  useFrame(() => {
    if (group.current) group.current.visible = useGlobe.getState().territories > 0.01;
  });
  return (
    <group ref={group}>
      {rings.map((r) => (
        <group key={r.slug}>{r.rings.map((pts, j) => (pts.length > 2 ? <Line key={j} points={pts} color="#91C77A" lineWidth={1.4} transparent opacity={0.9} /> : null))}</group>
      ))}
    </group>
  );
}

export interface GlobePin {
  id: string;
  lat: number;
  lon: number;
  /** los pines de etiqueta se desvanecen con la aparición del territorio; los de marcador siempre están visibles */
  kind: "label" | "marker";
}

/**
 * Proyecta los pines al espacio de pantalla en cada frame y mueve los nodos DOM que renderiza
 * <Globe> (data-pin=id) en una capa superpuesta. Se ocultan cuando quedan al otro lado del planeta.
 */
function Projector({ pins, overlay }: { pins: GlobePin[]; overlay: React.RefObject<HTMLDivElement | null> }) {
  const anchor = useRef<Group>(null);
  const tmp = useMemo(() => new Vector3(), []);
  const camDir = useMemo(() => new Vector3(), []);
  const points = useMemo(() => pins.map((p) => ({ ...p, v: latLonToVector3(p.lat, p.lon, 1.01) })), [pins]);
  useFrame(({ camera, size }) => {
    const root = overlay.current;
    const g = anchor.current;
    if (!root || !g) return;
    g.updateWorldMatrix(true, false);
    camera.updateMatrixWorld();
    camDir.copy(camera.position).normalize();
    const reveal = useGlobe.getState().territories;
    const highlight = useGlobe.getState().highlight;
    for (const p of points) {
      const el = root.querySelector<HTMLElement>(`[data-pin="${CSS.escape(p.id)}"]`);
      if (!el) continue;
      tmp.copy(p.v).applyMatrix4(g.matrixWorld);
      const facing = tmp.clone().normalize().dot(camDir);
      tmp.project(camera);
      const x = ((tmp.x + 1) / 2) * size.width;
      const y = ((1 - tmp.y) / 2) * size.height;
      const vis = Math.max(0, Math.min(1, (facing - 0.2) * 4)) * (p.kind === "label" ? reveal : 1);
      // Las etiquetas se anclan en su punto inicial; los marcadores en su centro.
      const shift = p.kind === "label" ? "translate(-4px, -50%)" : "translate(-50%, -50%)";
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) ${shift}`;
      el.style.opacity = vis.toFixed(3);
      el.style.visibility = vis < 0.02 ? "hidden" : "visible";
      el.dataset.active = String(highlight === p.id);
    }
  });
  return <group ref={anchor} />;
}

function Rig({ children }: { children: React.ReactNode }) {
  const group = useRef<Group>(null);
  const { camera } = useThree();
  const state = useRef({ x: 0, y: 0, spin: 0, dist: 3.4 });
  useFrame((_, dt) => {
    const t = useGlobe.getState();
    const target = facingRotation(t.lat, t.lon);
    const s = state.current;
    const k = 1 - Math.pow(0.0015, dt); // amortiguación independiente del frame rate
    // El giro en reposo es un offset que se deshace cuando se detiene, así los objetivos de foco quedan exactos.
    if (t.spin > 0) s.spin += t.spin * dt;
    else s.spin = MathUtils.lerp(s.spin, shortestAngle(s.spin, 0), k);
    s.x = MathUtils.lerp(s.x, target.x, k);
    s.y = MathUtils.lerp(s.y, shortestAngle(s.y, target.y + s.spin), k);
    s.dist = MathUtils.lerp(s.dist, t.distance, k);
    if (group.current) group.current.rotation.set(s.x, s.y, 0, "XYZ");
    camera.position.set(0, 0, s.dist);
    camera.lookAt(0, 0, 0);
  });
  return <group ref={group}>{children}</group>;
}

export default function GlobeScene({ territories, pins, overlay, tier, paused }: GlobeSceneProps) {
  return (
    <Canvas
      frameloop={paused ? "never" : "always"}
      dpr={tier === "high" ? [1, 1.8] : [1, 1.25]}
      camera={{ fov: 32, near: 0.1, far: 50, position: [0, 0, 3.4] }}
      gl={{ antialias: tier === "high", powerPreference: "high-performance", alpha: true }}
      aria-hidden
    >
      <Suspense fallback={null}>
        <Rig>
          <Earth tier={tier} />
          <TerritoryOutlines territories={territories} />
          <Projector pins={pins} overlay={overlay} />
        </Rig>
        <Atmosphere />
        <Orbit />
        <Dust count={tier === "high" ? 1800 : 500} />
      </Suspense>
    </Canvas>
  );
}
