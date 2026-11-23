"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { create } from "zustand";
import { cn } from "@/lib/cn";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton", className)} />;
}

export function LoadingBlock({ label = "Cargando…", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={cn("h-16", i % 2 ? "w-11/12" : "w-full")} />
      ))}
    </div>
  );
}

/**
 * Lámina de curvas de nivel: una pequeña hoja topográfica con un cuadro de levantamiento vacío,
 * que se lee como "aquí todavía no se ha observado nada". Dibujada en tinta sobre papel como el resto del atlas.
 */
export function OrbitIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 120" className={cn("h-24 w-32 text-ink", className)} aria-hidden fill="none" stroke="currentColor">
      <rect x="0.5" y="0.5" width="159" height="119" strokeOpacity=".9" />
      <g strokeOpacity=".35" strokeWidth=".8">
        <path d="M-4 92c22-10 34-2 52-12s30-26 52-22 38 18 64 6" />
        <path d="M-4 78c20-8 32-4 46-14s28-28 52-24 40 14 70 2" />
        <path d="M-4 64c18-6 30-8 40-18s30-26 54-22 40 10 74-2" />
        <path d="M10 40c10-8 22-12 34-10s18 10 30 8 20-14 34-14 26 8 40 2" />
        <path d="M30 26c8-6 16-8 24-6s14 6 22 4 14-8 24-8" />
      </g>
      <g strokeOpacity=".5" strokeWidth=".6">
        <path d="M40 0v4M80 0v4M120 0v4M40 116v4M80 116v4M120 116v4M0 40h4M0 80h4M156 40h4M156 80h4" />
      </g>
      <rect x="66" y="48" width="28" height="24" strokeDasharray="3 2.5" strokeWidth="1.2" />
      <path d="M80 56v8M76 60h8" strokeWidth="1" />
    </svg>
  );
}

export function EmptyState({ title, description, action, className }: { title: string; description: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className={cn("flex flex-col items-center gap-4 border-y border-rule px-8 py-12 text-center", className)}
    >
      <OrbitIllustration />
      <h3 className="font-display text-h4 text-ink">{title}</h3>
      <div className="max-w-md text-sm leading-relaxed text-ink-2">{description}</div>
      {action}
    </motion.div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 border-l-2 border-signal bg-signal-tint/60 p-5">
      <p className="eyebrow !text-signal">Algo salió mal</p>
      <p className="text-sm text-ink">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="text-sm font-semibold text-brand link-underline">
          Intentar de nuevo
        </button>
      )}
    </div>
  );
}

/** Indicador animado de "procesando satélite" con progreso. */
export function ProcessingIndicator({ progress, label }: { progress: number; label: string }) {
  const pct = Math.round(progress * 100);
  return (
    <div className="flex flex-col gap-2" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label={label}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-ink-2">{label}</span>
        <span className="font-mono text-brand">{pct}%</span>
      </div>
      <div className="relative h-1 overflow-hidden bg-paper-3">
        {/* scaleX en vez de width: solo trabaja el compositor, nada de layout en cada frame. */}
        <motion.div className="absolute inset-0 origin-left bg-brand" initial={false} animate={{ scaleX: Math.max(pct, 3) / 100 }} />
              </div>
    </div>
  );
}

// ── Toasts ────────────────────────────────────────────────────────────────────

interface Toast {
  id: number;
  tone: "success" | "error" | "info";
  message: string;
}

interface ToastState {
  toasts: Toast[];
  push: (tone: Toast["tone"], message: string) => void;
  dismiss: (id: number) => void;
}

export const useToasts = create<ToastState>((set) => ({
  toasts: [],
  push: (tone, message) => {
    const id = Date.now() + Math.random();
    set((s) => ({ toasts: [...s.toasts, { id, tone, message }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 5200);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export const toast = {
  success: (m: string) => useToasts.getState().push("success", m),
  error: (m: string) => useToasts.getState().push("error", m),
  info: (m: string) => useToasts.getState().push("info", m),
};

export function Toaster() {
  const { toasts, dismiss } = useToasts();
  return (
    <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-[90] flex flex-col items-center gap-2 px-4 sm:bottom-6 sm:right-6 sm:left-auto sm:items-end">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.96 }}
            className={cn(
              "pointer-events-auto flex max-w-sm items-start gap-3 rounded-xs border border-ink bg-field px-4 py-3 text-sm shadow-float",
              t.tone === "error" && "border-l-4 border-l-signal",
              t.tone === "success" && "border-l-4 border-l-brand",
            )}
            role={t.tone === "error" ? "alert" : "status"}
          >
            <span aria-hidden className={cn("mt-1.5 size-2 shrink-0", t.tone === "error" ? "bg-signal" : t.tone === "success" ? "bg-brand" : "bg-ink-3")} />
            <span className="flex-1 text-ink">{t.message}</span>
            <button onClick={() => dismiss(t.id)} className="text-ink-2 hover:text-ink" aria-label="Cerrar aviso">
              ×
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
