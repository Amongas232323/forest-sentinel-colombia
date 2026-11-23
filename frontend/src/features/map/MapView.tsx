"use client";

import type { Map as MLMap, MapOptions } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { COLOMBIA_BOUNDS, forestStyle } from "./style";

export type { MLMap };

export interface MapViewProps {
  className?: string;
  bounds?: [[number, number], [number, number]];
  onLoad?: (map: MLMap) => void | (() => void);
  options?: Partial<MapOptions>;
  label: string;
  interactive?: boolean;
}

/**
 * Wrapper delgado de MapLibre: carga la librería de forma perezosa, maneja el ciclo de vida de la instancia,
 * y les da a las páginas un hook imperativo `onLoad` para agregar sus capas propias.
 */
export function MapView({ className, bounds = COLOMBIA_BOUNDS, onLoad, options, label, interactive = true }: MapViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const onLoadRef = useRef(onLoad);
  onLoadRef.current = onLoad;

  useEffect(() => {
    let map: MLMap | null = null;
    let cleanup: void | (() => void);
    let cancelled = false;
    void import("maplibre-gl").then((maplibregl) => {
      if (cancelled || !container.current) return;
      // El worker lo copia scripts/copy-maplibre-worker.mjs a public/vendor/ (Next no lo empaqueta).
      maplibregl.setWorkerUrl("/vendor/maplibre-gl-worker.mjs");
      try {
        map = new maplibregl.Map({
          container: container.current,
          style: forestStyle,
          bounds,
          fitBoundsOptions: { padding: 40 },
          attributionControl: { compact: true },
          interactive,
          maxPitch: 75,
          ...options,
        });
      } catch {
        setError("Tu navegador no pudo iniciar el mapa (WebGL no disponible).");
        return;
      }
      if (interactive) {
        map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
        map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
      }
      map.on("load", () => {
        if (map) cleanup = onLoadRef.current?.(map);
      });
      map.on("error", (e) => {
        // Sin conexión es normal que fallen los tiles; dejamos el mapa usable igual.
        if ((e.error as { status?: number } | undefined)?.status !== 404) console.warn("map", e.error?.message);
      });
    });
    return () => {
      cancelled = true;
      if (typeof cleanup === "function") cleanup();
      map?.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    // Quien lo use puede posicionar el mapa en absolute; solo ponemos `relative` por defecto en otro caso
    // (si van las dos clases juntas el contenedor colapsa a 0 px de alto).
    <div className={cn("overflow-hidden bg-paper", !/\b(absolute|fixed)\b/.test(className ?? "") && "relative", className)}>
      {/* Estilo inline a propósito: MapLibre agrega `.maplibregl-map { position: relative }`
             (CSS sin layer), que pisaría la utilidad `absolute` de Tailwind que sí está en un layer. */}
      <div ref={container} style={{ position: "absolute", inset: 0 }} role="region" aria-label={label} />
      {error && <p className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-ink-2">{error}</p>}
    </div>
  );
}
