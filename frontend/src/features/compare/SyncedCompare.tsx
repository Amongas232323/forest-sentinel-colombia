"use client";

import type { FeatureCollection } from "geojson";
import type { Map as MLMap } from "maplibre-gl";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { MapView } from "@/features/map/MapView";
import { geometryBounds, setEvidence, setPolygon, setVisibility, SEVERITY_COLOR } from "@/features/map/layers";
import type { Evidence, GeoJSONGeometry } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { fmtDateShort } from "@/lib/format";

interface Props {
  evidence: Evidence;
  referenceDate: string;
  observationDate: string;
  focus?: GeoJSONGeometry;
  polygons?: FeatureCollection;
  className?: string;
}

/**
 * Dos instancias de MapLibre con las cámaras enlazadas: izquierda = imagen de referencia,
 * derecha = imagen de observación (+ máscara de cambio). El divisor recorta el mapa de arriba,
 * así los dos quedan sincronizados espacialmente mientras uno se mueve o hace zoom.
 */
export function SyncedCompare({ evidence, referenceDate, observationDate, focus, polygons, className }: Props) {
  const [pos, setPos] = useState(50);
  const [maskOpacity, setMaskOpacity] = useState(0.85);
  const [showPolygons, setShowPolygons] = useState(true);
  const maps = useRef<{ a?: MLMap; b?: MLMap }>({});
  const syncing = useRef(false);
  const sliderId = useId();
  const opacityId = useId();
  const stage = useRef<HTMLDivElement>(null);
  const grab = useRef<number | null>(null); // desfase en px entre el puntero y el divisor al momento de agarrarlo
  const [dragging, setDragging] = useState(false);

  // Manipulación directa: el divisor sigue al puntero 1:1, manteniendo el desfase del agarre,
  // y el pointer capture sigue rastreando aunque el puntero se salga del manejador.
  const onHandleDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const rect = stage.current?.getBoundingClientRect();
    if (!rect) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    grab.current = e.clientX - (rect.left + (rect.width * pos) / 100);
    setDragging(true);
  };
  const onHandleMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const rect = stage.current?.getBoundingClientRect();
    if (grab.current === null || !rect) return;
    const next = ((e.clientX - grab.current - rect.left) / rect.width) * 100;
    setPos(Math.round(Math.min(100, Math.max(0, next)) * 10) / 10);
  };
  const onHandleUp = (e: React.PointerEvent<HTMLDivElement>) => {
    grab.current = null;
    setDragging(false);
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  };

  const bounds = focus ? padBounds(geometryBounds(focus), 0.6) : ([[evidence.bounds[0], evidence.bounds[1]], [evidence.bounds[2], evidence.bounds[3]]] as [[number, number], [number, number]]);

  const link = useCallback(() => {
    const { a, b } = maps.current;
    if (!a || !b) return;
    const sync = (from: MLMap, to: MLMap) => () => {
      if (syncing.current) return;
      syncing.current = true;
      to.jumpTo({ center: from.getCenter(), zoom: from.getZoom(), bearing: from.getBearing(), pitch: from.getPitch() });
      syncing.current = false;
    };
    a.on("move", sync(a, b));
    b.on("move", sync(b, a));
  }, []);

  const addVectors = (map: MLMap) => {
    if (polygons) {
      map.addSource("change-polys", { type: "geojson", data: polygons });
      map.addLayer({ id: "change-polys-line", type: "line", source: "change-polys", paint: { "line-color": SEVERITY_COLOR as never, "line-width": 1.6 } });
    }
    if (focus) setPolygon(map, "focus", focus, "#F2F3EA");
  };

  useEffect(() => {
    const b = maps.current.b;
    if (b?.getLayer("ev-b-overlay-layer")) b.setPaintProperty("ev-b-overlay-layer", "raster-opacity", maskOpacity);
  }, [maskOpacity]);

  useEffect(() => {
    for (const m of [maps.current.a, maps.current.b]) if (m) setVisibility(m, ["change-polys-line", "focus-line", "focus-glow"], showPolygons);
  }, [showPolygons]);

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div ref={stage} className="plate relative aspect-[4/3] w-full sm:aspect-[16/10]">
        <MapView
          className="absolute inset-0"
          label={`Imagen satelital de referencia, ${fmtDateShort(referenceDate)}`}
          bounds={bounds}
          onLoad={(map) => {
            maps.current.a = map;
            setEvidence(map, evidence, "reference", false, "ev-a");
            addVectors(map);
            link();
          }}
        />
        <div className="absolute inset-0" style={{ clipPath: `inset(0 0 0 ${pos}%)` }}>
          <MapView
            className="absolute inset-0"
            label={`Imagen satelital posterior, ${fmtDateShort(observationDate)}, con áreas de cambio`}
            bounds={bounds}
            onLoad={(map) => {
              maps.current.b = map;
              setEvidence(map, evidence, "observation", true, "ev-b");
              addVectors(map);
              link();
            }}
          />
        </div>
        <div aria-hidden className="pointer-events-none absolute inset-y-0 w-px bg-field shadow-[0_0_0_1px_rgb(22_33_27/0.55)]" style={{ left: `${pos}%` }} />
        {/* Manejador para puntero (mouse/touch). El teclado y los lectores de pantalla usan el input range de abajo. */}
        <div
          aria-hidden
          onPointerDown={onHandleDown}
          onPointerMove={onHandleMove}
          onPointerUp={onHandleUp}
          onPointerCancel={onHandleUp}
          className="absolute top-1/2 z-10 grid size-11 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize touch-none place-items-center rounded-full"
          style={{ left: `${pos}%` }}
        >
          <span
            className={cn(
              "grid size-9 place-items-center rounded-xs border border-ink bg-field font-mono text-xs text-ink shadow-float [transition:transform_120ms_ease-out]",
              dragging && "scale-110",
            )}
          >
            <svg viewBox="0 0 20 12" className="h-3 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 1 1 6l5 5M14 1l5 5-5 5" />
            </svg>
          </span>
        </div>
        <span className="pointer-events-none absolute top-3 left-3 z-[1] rounded-xs bg-field px-2 py-1 font-mono text-[0.6875rem] text-ink">ANTES · {fmtDateShort(referenceDate)}</span>
        <span className="pointer-events-none absolute top-3 right-14 z-[1] rounded-xs bg-field px-2 py-1 font-mono text-[0.6875rem] text-ink">DESPUÉS · {fmtDateShort(observationDate)}</span>
      </div>

      <div className="grid gap-4 border-y border-rule py-4 sm:grid-cols-[1.4fr_1fr_auto] sm:items-center">
        <label htmlFor={sliderId} className="flex flex-col gap-1.5 text-xs text-ink-2">
          Posición del corte (antes ⟷ después)
          <input id={sliderId} type="range" min={0} max={100} value={pos} onChange={(e) => setPos(Number(e.target.value))} className="accent-[#1F4D36]" aria-valuetext={`${pos}% de la vista muestra la imagen anterior`} />
        </label>
        <label htmlFor={opacityId} className="flex flex-col gap-1.5 text-xs text-ink-2">
          Opacidad de la máscara de cambio
          <input id={opacityId} type="range" min={0} max={1} step={0.05} value={maskOpacity} onChange={(e) => setMaskOpacity(Number(e.target.value))} className="accent-[#8A5508]" />
        </label>
        <label className="flex items-center gap-2 text-xs text-ink">
          <input type="checkbox" checked={showPolygons} onChange={(e) => setShowPolygons(e.target.checked)} className="size-4 accent-[#1F4D36]" />
          Polígonos
        </label>
      </div>
      <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink-2" aria-label="Leyenda">
        <li className="flex items-center gap-2"><span className="size-3 rounded-sm bg-ochre-mark" aria-hidden /> Cambio moderado</li>
        <li className="flex items-center gap-2"><span className="size-3 rounded-sm bg-signal" aria-hidden /> Cambio fuerte</li>
        <li className="flex items-center gap-2"><span className="h-0.5 w-4 bg-field" aria-hidden /> Área de la alerta</li>
        <li className="ml-auto font-mono text-[0.6875rem]">Contiene información modificada de Copernicus Sentinel</li>
      </ul>
    </div>
  );
}

function padBounds([[w, s], [e, n]]: [[number, number], [number, number]], f: number): [[number, number], [number, number]] {
  const dx = Math.max((e - w) * f, 0.004);
  const dy = Math.max((n - s) * f, 0.004);
  return [[w - dx, s - dy], [e + dx, n + dy]];
}
