import type { AlertStatus, JobStatus, Severity } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { JOB_STATUS, SEVERITY, STATUS } from "@/lib/format";

/**
 * Dos ejes, dos estilos, para que nunca compitan:
 * - La severidad es una etiqueta impresa que va ganando peso con el riesgo (contorno → tinte → ocre sólido → signal sólido).
 * - El estado es texto plano con un marcador cuadrado: dice en qué va la revisión, no qué tan grave es el cambio.
 */
const SEVERITY_LOOK: Record<Severity, string> = {
  low: "border-rule-strong bg-transparent text-ink-2",
  moderate: "border-ochre bg-ochre-tint text-ochre",
  high: "border-ochre bg-ochre text-paper",
  priority: "border-signal bg-signal text-paper",
};

/** Forma + texto + color: la severidad nunca depende solo del color (WCAG 1.4.1). */
const SEVERITY_GLYPH: Record<Severity, string> = { low: "◦", moderate: "◆", high: "▲", priority: "⬣" };

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const s = SEVERITY[severity];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-xs border px-2 py-0.5 text-xs font-semibold", SEVERITY_LOOK[severity], className)}>
      <span aria-hidden className="font-mono text-[0.8em]">
        {SEVERITY_GLYPH[severity]}
      </span>
      {s.label}
    </span>
  );
}

const marks = {
  water: "bg-water",
  brand: "bg-brand",
  signal: "bg-signal",
  muted: "bg-ink-3",
};

const STATUS_MARK: Record<AlertStatus, keyof typeof marks> = {
  new: "water",
  pending_review: "water",
  in_review: "brand",
  confirmed: "signal",
  dismissed: "muted",
  closed: "muted",
};

export function StatusBadge({ status, className }: { status: AlertStatus; className?: string }) {
  return (
    <span title={STATUS[status].hint} className={cn("inline-flex items-center gap-1.5 text-xs font-medium text-ink-2", className)}>
      <span aria-hidden className={cn("size-2 shrink-0", marks[STATUS_MARK[status]], status === "in_review" && "motion-safe:animate-pulse")} />
      {STATUS[status].label}
    </span>
  );
}

const JOB_MARK: Record<JobStatus, keyof typeof marks> = { queued: "muted", running: "brand", succeeded: "brand", failed: "signal", cancelled: "muted" };

export function JobBadge({ status }: { status: JobStatus }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", status === "failed" ? "text-signal" : "text-ink-2")}>
      {status === "running" ? (
        <span aria-hidden className="size-2 animate-spin rounded-full border border-brand border-t-transparent" />
      ) : (
        <span aria-hidden className={cn("size-2 shrink-0", marks[JOB_MARK[status]])} />
      )}
      {JOB_STATUS[status]}
    </span>
  );
}

export function DetectorBadge({ kind, label }: { kind: "rule-based" | "deep-learning"; label: string }) {
  return (
    <span
      title={kind === "rule-based" ? "Análisis espectral con reglas documentadas. No es un modelo de inteligencia artificial." : "Modelo de segmentación entrenado (Siamese U-Net)."}
      className={cn("inline-flex items-center gap-1.5 rounded-xs border px-2 py-0.5 font-mono text-[0.6875rem]", kind === "rule-based" ? "border-rule-strong text-ink-2" : "border-brand text-brand")}
    >
      {kind === "rule-based" ? "REGLAS ESPECTRALES" : "MODELO IA"} · {label}
    </span>
  );
}
