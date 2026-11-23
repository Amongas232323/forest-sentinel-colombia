"use client";

import { ArrowLeft, Copy, Info, Mountain, SplitSquareHorizontal } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { use, useMemo, useState } from "react";
import { DetectorBadge, SeverityBadge, StatusBadge } from "@/components/ui/Badges";
import { ErrorState, LoadingBlock, toast } from "@/components/ui/Feedback";
import { ReviewPanel } from "@/features/alerts/ReviewPanel";
import { SyncedCompare } from "@/features/compare/SyncedCompare";
import { useAlert, useResultPolygons } from "@/lib/api/hooks";
import type { AlertEvent } from "@/lib/api/types";
import { hasRole, useAuth } from "@/lib/auth/store";
import { cn } from "@/lib/cn";
import { STATUS, fmtCoord, fmtDate, fmtDateTime, fmtNumber, fmtPct } from "@/lib/format";

const TerrainScene = dynamic(() => import("@/features/terrain/TerrainScene"), { ssr: false });

const EVENT_TEXT: Record<AlertEvent["type"], string> = {
  created: "Alerta creada automáticamente",
  redetected: "Detectada de nuevo",
  status_changed: "Cambio de estado",
  comment: "Observación",
  notified: "Notificación enviada",
};

export default function AlertDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const user = useAuth((s) => s.user);
  const { data: alert, isLoading, isError, refetch } = useAlert(id);
  const polygons = useResultPolygons(alert?.result_id ?? null);
  const [view, setView] = useState<"compare" | "terrain">("compare");

  // El relieve tiene que cubrir exactamente la imagen de evidencia para que el drapeado quede georreferenciado.
  const terrainBounds = useMemo(() => (alert?.evidence ? (alert.evidence.bounds as [number, number, number, number]) : null), [alert]);

  if (isLoading) return <div className="p-8"><LoadingBlock rows={6} /></div>;
  if (isError || !alert) return <div className="p-8"><ErrorState message="No encontramos esta alerta." onRetry={() => refetch()} /></div>;

  const [lon, lat] = alert.centroid;
  const ev = alert.evidence;

  return (
    <article className="px-5 pt-6 pb-16 sm:px-8 lg:pt-8">
      <Link href="/app/alerts" className="inline-flex items-center gap-2 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" /> Centro de alertas
      </Link>

      {/* Primero en lenguaje sencillo */}
      <header className="mt-6 grid grid-cols-1 gap-x-10 gap-y-6 border-b border-ink pb-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-end">
        <div className="max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={alert.severity} />
            <StatusBadge status={alert.status} />
            <span className="font-mono text-xs text-ink-2">{alert.code}</span>
          </div>
          <h1 className="mt-4 font-display display-tight text-[clamp(2rem,3.6vw,3.052rem)] leading-[1.04] font-medium text-ink">{alert.explanation.headline}</h1>
          <p className="mt-4 max-w-[62ch] text-lead text-ink">{alert.explanation.summary}</p>
          <p className="mt-3 inline-block border-y border-ink py-1.5 font-display text-h4 font-medium text-ink">{alert.explanation.area_text}</p>
          <p className="mt-3 text-sm text-ink-2">
            {alert.region_name} · {alert.territory_name} · <span className="font-mono">{fmtCoord(lon, lat)}</span>
          </p>
        </div>
        <div className="border-l-2 border-ochre bg-ochre-tint/50 py-3 pr-3 pl-4 text-sm text-ink">
          <p className="flex items-start gap-2"><Info className="mt-0.5 size-4 shrink-0 text-ochre" aria-hidden /> {alert.explanation.caveat}</p>
        </div>
      </header>

      <div className="mt-8 grid grid-cols-1 gap-x-10 gap-y-8 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex flex-col gap-6">
          {/* Evidencia */}
          <section aria-labelledby="evidence-title">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 id="evidence-title" className="font-display text-h4 font-medium text-ink">Evidencia satelital</h2>
              {ev && (
                <div role="tablist" aria-label="Tipo de vista" className="flex border border-ink">
                  {([["compare", "Comparar fechas", SplitSquareHorizontal], ["terrain", "Terreno 3D", Mountain]] as const).map(([k, label, Icon]) => (
                    <button key={k} role="tab" aria-selected={view === k} onClick={() => setView(k)} className={cn("flex min-h-10 items-center gap-2 px-4 py-2 text-sm transition-colors", view === k ? "bg-ink text-paper" : "text-ink hover:bg-paper-3")}>
                      <Icon className="size-4" aria-hidden /> {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {!ev && <p className="border-y border-rule py-5 text-sm text-ink-2">Este análisis no generó imágenes de evidencia.</p>}
            {ev && view === "compare" && (
              <SyncedCompare evidence={ev} referenceDate={alert.reference_date} observationDate={alert.observation_date} focus={alert.geometry} polygons={polygons.data} />
            )}
            {ev && view === "terrain" && terrainBounds && (
              <div className="plate aspect-[4/3] sm:aspect-[16/10]">
                <TerrainScene bounds={terrainBounds} imageUrl={ev.observation_url} overlayUrl={ev.overlay_url} marker={alert.centroid} />
              </div>
            )}
            {ev && view === "terrain" && (
              <p className="mt-2 text-xs text-ink-2">Imagen Sentinel-2 posterior proyectada sobre la elevación real de toda la zona analizada. La baliza roja marca el hallazgo; arrastra para girar y usa la rueda para acercarte.</p>
            )}
          </section>

          {/* Detalles técnicos */}
          <details className="group border-y border-ink py-4">
            <summary className="flex cursor-pointer list-none items-center justify-between font-semibold text-ink">
              Detalles técnicos
              <span className="font-mono text-xs text-ink-2 group-open:rotate-180 transition-transform">▾</span>
            </summary>
            <dl className="mt-4 grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
              {[
                ["Método", <DetectorBadge key="d" kind={alert.detector_kind} label={alert.detector} />],
                ["Intensidad de la señal", `${fmtNumber(alert.confidence, 2)} (escala 0–1, no calibrada como probabilidad)`],
                ["Caída media de NDVI (verdor)", alert.mean_ndvi_drop !== null ? fmtNumber(alert.mean_ndvi_drop, 3) : "—"],
                ["Caída media de NBR (estructura / quema)", alert.mean_nbr_drop !== null ? fmtNumber(alert.mean_nbr_drop, 3) : "—"],
                ["Calidad de imagen (píxeles sin nubes)", fmtPct(alert.image_quality)],
                ["Fuente", alert.source],
                ["Imagen de referencia", fmtDateTime(alert.reference_date)],
                ["Imagen de observación", fmtDateTime(alert.observation_date)],
                ["Primera detección", fmtDateTime(alert.first_detected_at)],
                ["Detecciones", `${alert.detection_count}`],
              ].map(([k, v]) => (
                <div key={k as string}>
                  <dt className="eyebrow">{k}</dt>
                  <dd className="mt-1 text-ink">{v}</dd>
                </div>
              ))}
              <div className="sm:col-span-2">
                <dt className="eyebrow">Coordenadas del centroide</dt>
                <dd className="mt-1 flex items-center gap-2 font-mono text-ink">
                  {lat.toFixed(6)}, {lon.toFixed(6)}
                  <button
                    onClick={() => navigator.clipboard.writeText(`${lat.toFixed(6)}, ${lon.toFixed(6)}`).then(() => toast.success("Coordenadas copiadas."))}
                    className="grid size-11 place-items-center rounded-xs text-ink-2 hover:bg-paper-3 hover:text-ink"
                    aria-label="Copiar coordenadas"
                  >
                    <Copy className="size-4" />
                  </button>
                </dd>
              </div>
            </dl>
            <p className="mt-4 text-xs text-ink-2">{alert.explanation.confidence_text}</p>
            <Link href={`/app/compare?result=${alert.result_id}`} className="mt-3 inline-block text-sm text-brand link-underline">
              Ver el análisis completo de la zona
            </Link>
          </details>
        </div>

        <aside className="flex flex-col gap-6">
          <ReviewPanel alert={alert} canReview={hasRole(user, "analyst")} />
          <section aria-labelledby="history-title" className="border-t border-ink pt-4">
            <h2 id="history-title" className="font-display text-h4 font-medium text-ink">Historial</h2>
            <ol className="mt-4 flex flex-col gap-0">
              {alert.events.map((e, i) => (
                <li key={e.id} className="relative flex gap-3 pb-5">
                  {i < alert.events.length - 1 && <span aria-hidden className="absolute top-4 left-[5px] h-full w-px bg-rule-strong" />}
                  <span aria-hidden className={cn("mt-1.5 size-[11px] shrink-0 border-2", e.type === "status_changed" ? "border-ink bg-ink" : "border-ink bg-paper")} />
                  <div className="min-w-0">
                    <p className="text-sm text-ink">
                      {EVENT_TEXT[e.type]}
                      {e.to_status && <> → <strong>{STATUS[e.to_status].label}</strong></>}
                    </p>
                    <p className="font-mono text-xs text-ink-2">
                      {fmtDate(e.created_at, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                      {e.actor_name ? ` · ${e.actor_name}` : " · Sistema"}
                    </p>
                    {e.comment && <p className="mt-1.5 border-l-2 border-rule-strong pl-3 font-display text-base whitespace-pre-wrap text-ink italic">{e.comment}</p>}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </article>
  );
}
