"use client";

import type { FeatureCollection } from "geojson";
import type { GeoJSONSource } from "maplibre-gl";
import { useEffect, useRef } from "react";
import { MapView, type MLMap } from "@/features/map/MapView";
import { SEVERITY_COLOR, setTerritories } from "@/features/map/layers";
import type { Severity, TerritoryGeometry } from "@/lib/api/types";

export interface ZoneMarker {
  id: string;
  lat: number;
  lon: number;
  label: string;
  severity: Severity;
  count: number;
  onSelect: () => void;
}

function toCollection(markers: ZoneMarker[]): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: markers.map((m) => ({ type: "Feature", properties: { id: m.id, severity: m.severity, count: m.count, label: m.label }, geometry: { type: "Point", coordinates: [m.lon, m.lat] } })),
  };
}

/**
 * Hoja del atlas de Colombia para el centro de operaciones: los cuatro territorios en tinta sobre el
 * mapa base de papel, un punto con anillo por cada zona con alertas abiertas, con tamaño según cuántas tiene.
 */
export function AtlasOverview({ markers, territories }: { markers: ZoneMarker[]; territories?: TerritoryGeometry[] }) {
  const mapRef = useRef<MLMap | null>(null);
  const markersRef = useRef(markers);
  markersRef.current = markers;

  function sync(map: MLMap) {
    if (territories) setTerritories(map, territories);
    const data = toCollection(markersRef.current);
    const src = map.getSource("zones") as GeoJSONSource | undefined;
    if (src) {
      src.setData(data);
      return;
    }
    map.addSource("zones", { type: "geojson", data });
    map.addLayer({
      id: "zones-halo",
      type: "circle",
      source: "zones",
      paint: { "circle-color": "#FBFAF6", "circle-radius": ["interpolate", ["linear"], ["get", "count"], 1, 9, 40, 18], "circle-stroke-color": "#16211B", "circle-stroke-width": 1 },
    });
    map.addLayer({
      id: "zones-dot",
      type: "circle",
      source: "zones",
      paint: { "circle-color": SEVERITY_COLOR as never, "circle-radius": ["interpolate", ["linear"], ["get", "count"], 1, 5, 40, 12] },
    });
    map.on("click", "zones-halo", (e) => {
      const id = e.features?.[0]?.properties?.id as string | undefined;
      markersRef.current.find((m) => m.id === id)?.onSelect();
    });
    map.on("mouseenter", "zones-halo", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "zones-halo", () => (map.getCanvas().style.cursor = ""));
  }

  useEffect(() => {
    if (mapRef.current?.isStyleLoaded()) sync(mapRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markers, territories]);

  return (
    <>
    <MapView
      className="absolute inset-0"
      label="Mapa de Colombia con los cuatro territorios y las zonas con alertas abiertas"
      options={{ cooperativeGestures: true }}
      onLoad={(map) => {
        mapRef.current = map;
        sync(map);
        return () => {
          mapRef.current = null;
        };
      }}
    />
    {/* Acceso por teclado y lector de pantalla a los mismos puntos: ocultos hasta que reciben foco. */}
    <ul aria-label="Zonas con alertas abiertas" className="sr-only focus-within:not-sr-only focus-within:absolute focus-within:right-3 focus-within:bottom-10 focus-within:left-3 focus-within:z-10 focus-within:flex focus-within:flex-col focus-within:gap-1 focus-within:border focus-within:border-ink focus-within:bg-field focus-within:p-2">
      {markers.map((m) => (
        <li key={m.id}>
          <button type="button" onClick={m.onSelect} className="min-h-11 w-full px-2 text-left text-sm text-ink hover:bg-paper-2">
            {m.label}
          </button>
        </li>
      ))}
    </ul>
    </>
  );
}
