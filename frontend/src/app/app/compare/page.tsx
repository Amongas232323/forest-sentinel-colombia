"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { PageHeader } from "@/components/layout/AppShell";
import { DetectorBadge } from "@/components/ui/Badges";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/Feedback";
import { SyncedCompare } from "@/features/compare/SyncedCompare";
import { useJobs, useResult, useResultPolygons } from "@/lib/api/hooks";
import { fmtDate, fmtDateShort, fmtHa, fmtPct } from "@/lib/format";

function Picker() {
  const jobs = useJobs(undefined, 1);
  const done = jobs.data?.items.filter((j) => j.result_id) ?? [];
  if (jobs.isLoading) return <LoadingBlock rows={3} />;
  if (!done.length) return <EmptyState title="Aún no hay análisis terminados" description="Lanza un análisis desde una zona vigilada para comparar sus imágenes aquí." />;
  return (
    <ul className="grid gap-3 md:grid-cols-2">
      {done.map((j) => (
        <li key={j.id}>
          <Link href={`/app/compare?result=${j.result_id}`} className="panel block p-5 hover:border-rule-strong">
            <p className="font-semibold text-ink">{j.region_name}</p>
            <p className="mt-1 text-sm text-ink-2">{fmtDateShort(j.reference_start)} – {fmtDateShort(j.reference_end)} → {fmtDateShort(j.observation_start)} – {fmtDateShort(j.observation_end)}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function CompareView() {
  const resultId = useSearchParams().get("result");
  const result = useResult(resultId);
  const polygons = useResultPolygons(resultId);

  if (!resultId) return <Picker />;
  if (result.isLoading) return <LoadingBlock rows={4} />;
  if (result.isError || !result.data) return <ErrorState message="No encontramos este resultado." />;
  const r = result.data;

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div>
        {r.evidence ? (
          <SyncedCompare evidence={r.evidence} referenceDate={r.reference_last} observationDate={r.observation_last} polygons={polygons.data} />
        ) : (
          <p className="panel p-5 text-sm text-ink-2">Este análisis no generó imágenes (sin escenas disponibles).</p>
        )}
      </div>
      <aside className="flex flex-col gap-4">
        <div className="panel p-5">
          <p className="eyebrow mb-3">Resumen</p>
          <p className="font-display display-tight text-4xl text-ink">{fmtHa(r.changed_area_ha)}</p>
          <p className="text-sm text-ink-2">con cambio detectado, de {fmtHa(r.analysed_area_ha)} analizadas · {r.polygon_count} áreas</p>
          <div className="mt-4"><DetectorBadge kind={r.model.kind} label={`${r.model.detector_id}@${r.model.version}`} /></div>
        </div>
        <div className={`panel p-5 ${r.quality_ok ? "" : "border-ochre"}`}>
          <p className="eyebrow mb-3">Calidad de las imágenes</p>
          <p className="text-sm text-ink">{r.quality_ok ? "Suficiente para generar alertas." : "Insuficiente: no se generaron alertas."}</p>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div><dt className="text-ink-2">Antes, sin nubes</dt><dd className="font-mono text-ink">{fmtPct(r.reference_valid_fraction)}</dd></div>
            <div><dt className="text-ink-2">Después, sin nubes</dt><dd className="font-mono text-ink">{fmtPct(r.observation_valid_fraction)}</dd></div>
          </dl>
          {r.quality_notes.map((n) => <p key={n} className="mt-2 text-xs text-ochre">▲ {n}</p>)}
        </div>
        <div className="panel p-5">
          <p className="eyebrow mb-3">Imágenes usadas</p>
          <p className="mb-2 text-xs text-ink-2">Antes: {fmtDate(r.reference_first)} – {fmtDate(r.reference_last)} · Después: {fmtDate(r.observation_first)} – {fmtDate(r.observation_last)}</p>
          <ul className="flex flex-col gap-1.5">
            {r.scenes.map((s) => (
              <li key={s.scene_id} className="flex justify-between gap-2 font-mono text-[0.66rem]">
                <span className="truncate text-ink" title={s.scene_id}>{s.scene_id}</span>
                <span className="shrink-0 text-ink-2">{Math.round(s.cloud_cover ?? 0)} % nubes</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[0.6875rem] text-ink-2">Sentinel-2 L2A · Copernicus · Earth Search (AWS Open Data)</p>
        </div>
      </aside>
    </div>
  );
}

export default function ComparePage() {
  return (
    <>
      <PageHeader eyebrow="Comparador satelital" title={<>El mismo lugar, <span>dos momentos.</span></>} description="Arrastra el corte para ver el antes y el después. Los mapas se mueven juntos para que compares exactamente el mismo punto." />
      <div className="px-5 pb-12 sm:px-8">
        <Suspense>
          <CompareView />
        </Suspense>
      </div>
    </>
  );
}
