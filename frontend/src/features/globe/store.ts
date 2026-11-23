import { create } from "zustand";

/**
 * Objetivos de cámara/escena que escriben las líneas de tiempo del scroll o la UI, y que se leen en cada frame
 * dentro del loop de WebGL con getState() — sin re-render de React por frame.
 */
export interface GlobeTargets {
  lat: number;
  lon: number;
  distance: number; // distancia de la cámara en radios del globo
  territories: number; // 0..1 aparición del contorno
  orbit: number; // 0..1 visibilidad de la órbita del satélite
  spin: number; // velocidad de rotación automática en reposo (rad/s)
  highlight: string | null; // slug del territorio
}

export const COLOMBIA = { lat: 4.2, lon: -73.5 };

export const useGlobe = create<GlobeTargets & { set: (p: Partial<GlobeTargets>) => void }>((set) => ({
  lat: 12,
  lon: -40,
  distance: 3.4,
  territories: 0,
  orbit: 0,
  spin: 0.04,
  highlight: null,
  set: (p) => set(p),
}));
