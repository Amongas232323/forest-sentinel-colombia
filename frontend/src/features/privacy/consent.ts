"use client";

import { create } from "zustand";
import { api } from "@/lib/api/client";

/**
 * Consentimiento de cookies / almacenamiento local (Ley 1581 de 2012 — consentimiento previo,
 * expreso e informado). Antes de que el usuario elija solo se usa el almacenamiento "necesario".
 *
 * Inventario (mantenerlo sincronizado con /cookies):
 *  necessary  · fs_refresh (cookie de sesión httpOnly) · fs_consent (esta elección)
 *  functional · fs_ui (capas del mapa, paneles colapsados)
 *  analytics  · por ahora ninguna — la categoría existe para que cualquier herramienta futura quede condicionada.
 */
export const CONSENT_VERSION = "2026-11-12";
const KEY = "fs_consent";

export interface ConsentChoice {
  functional: boolean;
  analytics: boolean;
  version: string;
  subject: string;
  decided_at: string;
}

interface ConsentState {
  choice: ConsentChoice | null;
  ready: boolean;
  panelOpen: boolean;
  load: () => void;
  decide: (functional: boolean, analytics: boolean) => void;
  openPanel: () => void;
  closePanel: () => void;
}

function subjectId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export const useConsent = create<ConsentState>((set, get) => ({
  choice: null,
  ready: false,
  panelOpen: false,
  load: () => {
    try {
      const raw = localStorage.getItem(KEY);
      const parsed = raw ? (JSON.parse(raw) as ConsentChoice) : null;
      set({ choice: parsed && parsed.version === CONSENT_VERSION ? parsed : null, ready: true });
    } catch {
      set({ choice: null, ready: true });
    }
  },
  decide: (functional, analytics) => {
    const choice: ConsentChoice = {
      functional,
      analytics,
      version: CONSENT_VERSION,
      subject: get().choice?.subject ?? subjectId(),
      decided_at: new Date().toISOString(),
    };
    try {
      localStorage.setItem(KEY, JSON.stringify(choice));
      if (!functional) localStorage.removeItem("fs_ui");
    } catch {
      /* almacenamiento bloqueado: la elección igual aplica durante esta sesión */
    }
    set({ choice, panelOpen: false });
    // Prueba del consentimiento guardada en el servidor (id seudónimo del sujeto, IP hasheada).
    void api("/privacy/consent", { method: "POST", auth: false, body: { subject_id: choice.subject, functional, analytics } }).catch(() => undefined);
  },
  openPanel: () => set({ panelOpen: true }),
  closePanel: () => set({ panelOpen: false }),
}));

/** Helper de almacenamiento funcional — si no hay consentimiento no hace nada, sin avisar. */
export const uiStorage = {
  get<T>(key: string, fallback: T): T {
    if (!useConsent.getState().choice?.functional) return fallback;
    try {
      const all = JSON.parse(localStorage.getItem("fs_ui") ?? "{}") as Record<string, T>;
      return all[key] ?? fallback;
    } catch {
      return fallback;
    }
  },
  set<T>(key: string, value: T): void {
    if (!useConsent.getState().choice?.functional) return;
    try {
      const all = JSON.parse(localStorage.getItem("fs_ui") ?? "{}") as Record<string, T>;
      all[key] = value;
      localStorage.setItem("fs_ui", JSON.stringify(all));
    } catch {
      /* lo ignoramos */
    }
  },
};
