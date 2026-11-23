"use client";

import { useEffect, useState } from "react";

export type GraphicsTier = "none" | "low" | "high";

/** Detecta si hay soporte de WebGL y un nivel aproximado de rendimiento (memoria, núcleos, viewport). */
export function detectGraphicsTier(): GraphicsTier {
  if (typeof window === "undefined") return "none";
  try {
    const canvas = document.createElement("canvas");
    const gl = (canvas.getContext("webgl2") ?? canvas.getContext("webgl")) as WebGLRenderingContext | null;
    if (!gl) return "none";
    const nav = navigator as Navigator & { deviceMemory?: number };
    const memory = nav.deviceMemory ?? 4;
    const cores = navigator.hardwareConcurrency ?? 4;
    const small = window.matchMedia("(max-width: 768px)").matches;
    if (memory <= 2 || cores <= 2) return "low";
    return small || memory < 8 ? "low" : "high";
  } catch {
    return "none";
  }
}

export function useGraphicsTier(): GraphicsTier | null {
  const [tier, setTier] = useState<GraphicsTier | null>(null);
  useEffect(() => setTier(detectGraphicsTier()), []);
  return tier;
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const on = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

/** True mientras el elemento está (casi) en pantalla — lo usamos para pausar los loops de WebGL. */
export function useInView<T extends Element>(ref: React.RefObject<T | null>, rootMargin = "200px"): boolean {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setVisible(!!entry?.isIntersecting), { rootMargin });
    io.observe(el);
    return () => io.disconnect();
  }, [ref, rootMargin]);
  return visible;
}
