import { Vector3 } from "three";
import type { GeoJSONGeometry } from "@/lib/api/types";

/** Lat/lon → punto sobre una esfera que coincide con las UVs equirectangulares de THREE.SphereGeometry. */
export function latLonToVector3(lat: number, lon: number, radius = 1): Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((lon + 180) * Math.PI) / 180;
  return new Vector3(-radius * Math.sin(phi) * Math.cos(theta), radius * Math.cos(phi), radius * Math.sin(phi) * Math.sin(theta));
}

/** Euler (orden XYZ) que pone (lat, lon) mirando a la cámara en +Z con el norte hacia arriba. */
export function facingRotation(lat: number, lon: number): { x: number; y: number } {
  const v = latLonToVector3(lat, lon);
  return { x: (lat * Math.PI) / 180, y: -Math.atan2(v.x, v.z) };
}

/** Anillos exteriores de un (Multi)Polygon como puntos sobre la esfera, reducidos a ``maxPoints``. */
export function geometryRings(geometry: GeoJSONGeometry, radius: number, maxPoints = 600): Vector3[][] {
  const polygons = (geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates) as number[][][][];
  return polygons.map((poly) => {
    const ring = poly[0] ?? [];
    const step = Math.max(1, Math.ceil(ring.length / maxPoints));
    const pts: Vector3[] = [];
    for (let i = 0; i < ring.length; i += step) {
      const [lon, lat] = ring[i] as [number, number];
      pts.push(latLonToVector3(lat, lon, radius));
    }
    if (pts.length > 1) pts.push(pts[0]!.clone());
    return pts;
  });
}

export function shortestAngle(from: number, to: number): number {
  let d = (to - from) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return from + d;
}
