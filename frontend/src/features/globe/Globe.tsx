"use client";

import dynamic from "next/dynamic";
import { useMemo, useRef } from "react";
import { useTerritoryGeometries } from "@/lib/api/hooks";
import type { GeoJSONGeometry } from "@/lib/api/types";
import { useGraphicsTier, useInView } from "@/lib/device";
import { cn } from "@/lib/cn";
import type { GlobeMarker, GlobePin } from "./GlobeScene";

// three.js solo se descarga cuando de verdad se renderiza un globo.
const GlobeScene = dynamic(() => import("./GlobeScene"), { ssr: false, loading: () => <GlobePlaceholder /> });

export const TERRITORY_NAMES: Record<string, string> = {
  guaviare: "Guaviare",
  "sierra-nevada-santa-marta": "Sierra Nevada de Santa Marta",
  cundinamarca: "Cundinamarca",
  amazonas: "Amazonas",
};

const TONE_CLASS = { glow: "text-brand", amber: "text-ochre", alert: "text-signal" };

function GlobePlaceholder() {
  return (
    <div className="grid size-full place-items-center" aria-hidden>
      <div className="relative aspect-square w-[min(70%,520px)] rounded-full bg-[radial-gradient(circle_at_35%_30%,#397B50_0%,#183D2C_35%,#0a0f0c_72%)] shadow-[0_0_120px_-20px_rgb(145_199_122/0.45)]">
        <div className="absolute inset-0 rounded-full border border-rule" />
      </div>
    </div>
  );
}

/** Respaldo estático en 2D (sin WebGL): igual informa y sigue la identidad de la marca. */
function GlobeFallback() {
  return (
    <div className="relative grid size-full place-items-center" role="img" aria-label="Ilustración del planeta Tierra con Colombia resaltada">
      <div
        className="relative aspect-square w-[min(72%,520px)] overflow-hidden rounded-full shadow-[0_0_120px_-20px_rgb(145_199_122/0.45)]"
        style={{ backgroundImage: "url(/textures/earth-night-2k.jpg)", backgroundSize: "200% 100%", backgroundPosition: "29% 50%" }}
      >
        <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_30%_30%,transparent_40%,rgb(10_15_12/0.85)_75%)]" />
        <span className="absolute top-[48%] left-[52%] size-3 rounded-full bg-brand shadow-[0_0_20px_#91C77A]" />
      </div>
    </div>
  );
}

function centroid(geometry: GeoJSONGeometry): { lat: number; lon: number } {
  const polys = (geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates) as number[][][][];
  let sx = 0, sy = 0, n = 0;
  for (const poly of polys) for (const [lon, lat] of (poly[0] ?? []) as [number, number][]) { sx += lon; sy += lat; n++; }
  return { lat: sy / Math.max(n, 1), lon: sx / Math.max(n, 1) };
}

export function Globe({ markers = [], className, showLabels = true }: { markers?: GlobeMarker[]; className?: string; showLabels?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const overlay = useRef<HTMLDivElement>(null);
  const tier = useGraphicsTier();
  const visible = useInView(ref);
  const { data } = useTerritoryGeometries();
  const territories = useMemo(() => (data ?? []).map((t) => ({ ...t, name: TERRITORY_NAMES[t.slug] ?? t.slug })), [data]);

  const labels = useMemo(() => (showLabels ? territories.map((t) => ({ id: t.slug, name: t.name, ...centroid(t.geometry) })) : []), [territories, showLabels]);
  const pins: GlobePin[] = useMemo(
    () => [...labels.map((l) => ({ id: l.id, lat: l.lat, lon: l.lon, kind: "label" as const })), ...markers.map((m) => ({ id: `m-${m.id}`, lat: m.lat, lon: m.lon, kind: "marker" as const }))],
    [labels, markers],
  );

  return (
    <div ref={ref} className={cn("relative size-full", className)}>
      {tier === null ? (
        <GlobePlaceholder />
      ) : tier === "none" ? (
        <GlobeFallback />
      ) : (
        <>
          <GlobeScene territories={territories} pins={pins} overlay={overlay} tier={tier} paused={!visible} />
          <div ref={overlay} className="pointer-events-none absolute inset-0 overflow-hidden">
            {labels.map((l) => (
              <span
                key={l.id}
                data-pin={l.id}
                aria-hidden
                className="absolute top-0 left-0 whitespace-nowrap font-mono text-[0.6875rem] tracking-[0.2em] text-brand uppercase opacity-0 transition-colors data-[active=true]:text-ink"
                style={{ textShadow: "0 0 10px #0a0f0c, 0 0 2px #0a0f0c" }}
              >
                ● {l.name}
              </span>
            ))}
            {markers.map((m) => (
              <button
                key={m.id}
                type="button"
                data-pin={`m-${m.id}`}
                onClick={m.onSelect}
                aria-label={m.label}
                className={cn("pointer-events-auto absolute top-0 left-0 grid size-7 place-items-center rounded-full opacity-0", TONE_CLASS[m.tone])}
              >
                <span className="absolute inset-0 rounded-full border border-current motion-safe:animate-pulse-ring" />
                <span className="size-2 rounded-full bg-current shadow-[0_0_10px_currentColor]" />
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
