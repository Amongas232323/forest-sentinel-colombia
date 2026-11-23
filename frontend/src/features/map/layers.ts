import type { FeatureCollection } from "geojson";
import type { GeoJSONSource, Map as MLMap } from "maplibre-gl";
import type { Evidence, GeoJSONGeometry, Region, TerritoryGeometry } from "@/lib/api/types";

export const SEVERITY_COLOR = ["match", ["get", "severity"], "priority", "#A82820", "high", "#8A5508", "moderate", "#C98A1C", "#55753A"] as const;

function upsertSource(map: MLMap, id: string, data: FeatureCollection) {
  const src = map.getSource(id) as GeoJSONSource | undefined;
  if (src) src.setData(data);
  else map.addSource(id, { type: "geojson", data });
}

export function setTerritories(map: MLMap, territories: TerritoryGeometry[]) {
  upsertSource(map, "territories", {
    type: "FeatureCollection",
    features: territories.map((t) => ({ type: "Feature", properties: { slug: t.slug }, geometry: t.geometry })),
  });
  if (!map.getLayer("territories-fill")) {
    map.addLayer({ id: "territories-fill", type: "fill", source: "territories", paint: { "fill-color": "#1F4D36", "fill-opacity": 0.05 } });
    map.addLayer({ id: "territories-line", type: "line", source: "territories", paint: { "line-color": "#16211B", "line-width": 1.4, "line-opacity": 0.9 } });
  }
}

export function setRegions(map: MLMap, regions: Region[]) {
  upsertSource(map, "regions", {
    type: "FeatureCollection",
    features: regions.map((r) => ({ type: "Feature", id: r.id, properties: { id: r.id, name: r.name, open: r.open_alerts, active: r.is_active }, geometry: r.geometry })),
  });
  if (!map.getLayer("regions-fill")) {
    map.addLayer({ id: "regions-fill", type: "fill", source: "regions", paint: { "fill-color": "#1F4D36", "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.24, 0.1] } });
    map.addLayer({ id: "regions-line", type: "line", source: "regions", paint: { "line-color": "#1F4D36", "line-width": 1.4, "line-dasharray": [2, 1.5], "line-opacity": ["case", ["get", "active"], 0.85, 0.35] } });
    map.addLayer({
      id: "regions-label",
      type: "symbol",
      source: "regions",
      layout: { "text-field": ["get", "name"], "text-font": ["Noto Sans Bold"], "text-size": 11, "text-letter-spacing": 0.06, "text-transform": "uppercase" },
      paint: { "text-color": "#16211B", "text-halo-color": "#F4F2EB", "text-halo-width": 1.5 },
    });
  }
}

export function setAlerts(map: MLMap, fc: FeatureCollection) {
  upsertSource(map, "alerts", fc);
  if (!map.getLayer("alerts-fill")) {
    map.addLayer({ id: "alerts-fill", type: "fill", source: "alerts", paint: { "fill-color": SEVERITY_COLOR as never, "fill-opacity": 0.45 } });
    map.addLayer({ id: "alerts-line", type: "line", source: "alerts", paint: { "line-color": SEVERITY_COLOR as never, "line-width": 1.5 } });
    // Los puntos hacen que las alertas pequeñas se sigan viendo con zoom bajo.
    map.addLayer({
      id: "alerts-point",
      type: "circle",
      source: "alerts",
      maxzoom: 12,
      paint: { "circle-color": SEVERITY_COLOR as never, "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 3, 11, 6], "circle-stroke-color": "#FBFAF6", "circle-stroke-width": 1.2 },
    });
  }
}

export function setEvidence(map: MLMap, evidence: Evidence, which: "reference" | "observation", withOverlay: boolean, idPrefix = "ev") {
  const url = which === "reference" ? evidence.reference_url : evidence.observation_url;
  const coords = evidence.corners as [[number, number], [number, number], [number, number], [number, number]];
  const img = `${idPrefix}-img`;
  if (map.getSource(img)) {
    map.removeLayer(`${img}-layer`);
    map.removeSource(img);
  }
  map.addSource(img, { type: "image", url, coordinates: coords });
  const before = map.getLayer("regions-fill") ? "regions-fill" : undefined;
  map.addLayer({ id: `${img}-layer`, type: "raster", source: img, paint: { "raster-fade-duration": 0 } }, before);
  if (withOverlay) {
    const ov = `${idPrefix}-overlay`;
    if (!map.getSource(ov)) {
      map.addSource(ov, { type: "image", url: evidence.overlay_url, coordinates: coords });
      map.addLayer({ id: `${ov}-layer`, type: "raster", source: ov, paint: { "raster-resampling": "nearest", "raster-opacity": 0.85 } }, before);
    }
  }
}

export function setPolygon(map: MLMap, id: string, geometry: GeoJSONGeometry, color = "#A82820") {
  upsertSource(map, id, { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry }] });
  if (!map.getLayer(`${id}-line`)) {
    map.addLayer({ id: `${id}-glow`, type: "line", source: id, paint: { "line-color": color, "line-width": 8, "line-blur": 6, "line-opacity": 0.5 } });
    map.addLayer({ id: `${id}-line`, type: "line", source: id, paint: { "line-color": color, "line-width": 2 } });
  }
}

export function setVisibility(map: MLMap, layerIds: string[], visible: boolean) {
  for (const id of layerIds) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
}

export function geometryBounds(geometry: GeoJSONGeometry): [[number, number], [number, number]] {
  const polys = (geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates) as number[][][][];
  let w = 180, s = 90, e = -180, n = -90;
  for (const poly of polys) for (const ring of poly) for (const [x, y] of ring as [number, number][]) {
    w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y);
  }
  return [[w, s], [e, n]];
}
