import type { AlertStatus, ChangeSignal, JobStatus, Severity } from "@/lib/api/types";

const LOCALE = "es-CO";
const TZ = "America/Bogota";

export const fmtNumber = (n: number, digits = 0) =>
  new Intl.NumberFormat(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(n);

export const fmtDate = (iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "long", year: "numeric" }) =>
  iso ? new Intl.DateTimeFormat(LOCALE, { timeZone: TZ, ...opts }).format(new Date(iso)) : "—";

export const fmtDateShort = (iso: string | null | undefined) => fmtDate(iso, { day: "2-digit", month: "short", year: "numeric" });

export const fmtDateTime = (iso: string | null | undefined) =>
  fmtDate(iso, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return "nunca";
  const diff = (new Date(iso).getTime() - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60],
  ];
  for (const [unit, s] of units) if (Math.abs(diff) >= s) return rtf.format(Math.round(diff / s), unit);
  return "hace un momento";
}

export const fmtHa = (ha: number) => (ha >= 100 ? `${fmtNumber(ha, 0)} ha` : `${fmtNumber(ha, 1)} ha`);
export const fmtKm2 = (km2: number) => `${fmtNumber(km2, km2 < 100 ? 1 : 0)} km²`;
export const fmtPct = (f: number) => `${fmtNumber(f * 100, 0)} %`;

export function fmtCoord(lon: number, lat: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "O";
  return `${Math.abs(lat).toFixed(4)}° ${ns} · ${Math.abs(lon).toFixed(4)}° ${ew}`;
}

export const SEVERITY: Record<Severity, { label: string; tone: "glow" | "amber" | "alert"; order: number }> = {
  low: { label: "Cambio bajo", tone: "glow", order: 0 },
  moderate: { label: "Cambio moderado", tone: "amber", order: 1 },
  high: { label: "Cambio importante", tone: "amber", order: 2 },
  priority: { label: "Hallazgo prioritario", tone: "alert", order: 3 },
};

export const STATUS: Record<AlertStatus, { label: string; hint: string }> = {
  new: { label: "Nueva", hint: "Detectada automáticamente, nadie la ha revisado." },
  pending_review: { label: "Pendiente de revisión", hint: "En cola para que un analista la revise." },
  in_review: { label: "En revisión", hint: "Un analista está verificando la evidencia." },
  confirmed: { label: "Hallazgo confirmado", hint: "Verificada por una persona como cambio real." },
  dismissed: { label: "Descartada", hint: "Revisada y considerada falsa alarma." },
  closed: { label: "Cerrada", hint: "Caso terminado." },
};

export const STATUS_ACTIONS: Record<AlertStatus, string> = {
  new: "Volver a nueva",
  pending_review: "Enviar a revisión",
  in_review: "Empezar revisión",
  confirmed: "Confirmar hallazgo",
  dismissed: "Descartar",
  closed: "Cerrar caso",
};

export const SIGNAL: Record<ChangeSignal, { label: string; short: string }> = {
  vegetation_loss: { label: "Posible pérdida de vegetación", short: "Pérdida de vegetación" },
  possible_burn: { label: "Posible área quemada", short: "Posible quema" },
  possible_flooding: { label: "Posible inundación", short: "Agua / inundación" },
};

export const JOB_STATUS: Record<JobStatus, string> = {
  queued: "En cola",
  running: "Procesando",
  succeeded: "Completado",
  failed: "Falló",
  cancelled: "Cancelado",
};

export const JOB_STAGE: Record<string, string> = {
  queued: "Esperando turno",
  starting: "Preparando",
  grid: "Definiendo la cuadrícula de análisis",
  search: "Buscando imágenes satelitales",
  tiles: "Leyendo imágenes y comparando fechas",
  vectorize: "Dibujando las áreas de cambio",
  quicklooks: "Generando evidencia visual",
  done: "Listo",
};

export const ROLE: Record<string, string> = { admin: "Administración", analyst: "Analista", observer: "Observador" };

export function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}
