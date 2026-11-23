import type { GeoJSONGeometry } from "@/lib/api/types";
import { cn } from "@/lib/cn";

type Ring = [number, number][];

function outerRings(geometry: GeoJSONGeometry): Ring[] {
  const polys = (geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates) as number[][][][];
  return polys.map((p) => (p[0] ?? []) as Ring);
}

/**
 * El contorno real del territorio dibujado como figura del atlas: proyección equirectangular
 * corregida por cos(latitud) para que las formas mantengan sus proporciones, con cajas de zona opcionales.
 */
export function TerritorySilhouette({
  geometry,
  zones = [],
  className,
  label,
}: {
  geometry: GeoJSONGeometry;
  zones?: { bbox: number[]; alert?: boolean }[];
  className?: string;
  label?: string;
}) {
  const rings = outerRings(geometry);
  const pts = rings.flat();
  if (!pts.length) return null;
  const lons = pts.map((p) => p[0]);
  const lats = pts.map((p) => p[1]);
  const [minX, maxX, minY, maxY] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
  const k = Math.cos((((minY + maxY) / 2) * Math.PI) / 180);
  const w = (maxX - minX) * k || 1;
  const h = maxY - minY || 1;
  const size = 100;
  const scale = size / Math.max(w, h);
  const vw = w * scale;
  const vh = h * scale;
  const px = (lon: number) => (lon - minX) * k * scale;
  const py = (lat: number) => (maxY - lat) * scale;
  const step = (r: Ring) => Math.max(1, Math.ceil(r.length / 400));
  const d = rings
    .map((r) => r.filter((_, i) => i % step(r) === 0).map((p, i) => `${i ? "L" : "M"}${px(p[0]).toFixed(2)} ${py(p[1]).toFixed(2)}`).join("") + "Z")
    .join("");

  return (
    <svg viewBox={`-4 -4 ${vw + 8} ${vh + 8}`} className={cn("block", className)} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <path d={d} fill="var(--color-paper-3)" stroke="var(--color-ink)" strokeWidth={0.9} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      {zones.map((z, i) => {
        const [x0 = 0, y0 = 0, x1 = 0, y1 = 0] = z.bbox;
        return (
        <rect
          key={i}
          x={px(x0)}
          y={py(y1)}
          width={Math.max(1.5, (x1 - x0) * k * scale)}
          height={Math.max(1.5, (y1 - y0) * scale)}
          fill={z.alert ? "var(--color-ochre-mark)" : "var(--color-brand)"}
          fillOpacity={0.85}
          stroke="var(--color-ink)"
          strokeWidth={0.8}
          vectorEffect="non-scaling-stroke"
        />
        );
      })}
    </svg>
  );
}
