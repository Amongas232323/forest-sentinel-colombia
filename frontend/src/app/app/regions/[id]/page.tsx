"use client";

import { ArrowLeft, Pause, Play, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useRef } from "react";
import type { Map as MLMap } from "maplibre-gl";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingBlock, toast } from "@/components/ui/Feedback";
import { AlertRow } from "@/features/alerts/AlertRow";
import { JobItem, SectionTitle } from "@/features/dashboard/widgets";
import { MapView } from "@/features/map/MapView";
import { geometryBounds, setAlerts, setRegions } from "@/features/map/layers";
import { AnalyzeForm } from "@/features/regions/AnalyzeForm";
import { useAlerts, useAlertsGeo, useDeleteRegion, useJobs, useRegion, useUpdateRegion } from "@/lib/api/hooks";
import { hasRole, useAuth } from "@/lib/auth/store";
import { fmtKm2, fmtRelative } from "@/lib/format";

export default function RegionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const region = useRegion(id);
  const jobs = useJobs(id);
  const alerts = useAlerts({ region_id: id, status: ["new", "pending_review", "in_review", "confirmed"] }, 1, "severity", 10);
  const geo = useAlertsGeo({ region_id: id });
  const update = useUpdateRegion(id);
  const remove = useDeleteRegion();
  const mapRef = useRef<MLMap | null>(null);

  useEffect(() => {
    const map = mapRef.current;
    if (map && geo.data) setAlerts(map, geo.data);
  }, [geo.data]);

  if (region.isLoading) return <div className="p-8"><LoadingBlock rows={5} /></div>;
  if (region.isError || !region.data) return <div className="p-8"><ErrorState message="No encontramos esta zona." /></div>;
  const r = region.data;
  const running = jobs.data?.items.some((j) => j.status === "queued" || j.status === "running");

  async function toggleActive() {
    await update.mutateAsync({ is_active: !r.is_active });
    toast.success(r.is_active ? "Zona pausada." : "Zona activada.");
  }

  async function destroy() {
    if (!window.confirm(`¿Eliminar la zona «${r.name}»? Se borrarán sus análisis y alertas. Esta acción no se puede deshacer.`)) return;
    await remove.mutateAsync(r.id);
    toast.success("Zona eliminada.");
    router.replace("/app/regions");
  }

  return (
    <div className="px-5 pt-6 pb-16 sm:px-8 lg:pt-8">
      <Link href="/app/regions" className="inline-flex items-center gap-2 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" /> Zonas vigiladas
      </Link>
      <header className="mt-5 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="eyebrow mb-2">{r.territory_name}</p>
          <h1 className="font-display display-tight text-[clamp(2.2rem,4vw,3.4rem)] leading-[1.02] text-ink">{r.name}</h1>
          <p className="mt-2 text-sm text-ink-2">
            {fmtKm2(r.area_km2)} · análisis automático cada {r.cadence_days} días · último {fmtRelative(r.last_run_at)}
            {!r.is_active && <strong className="ml-2 text-ochre">· Pausada</strong>}
          </p>
          {r.description && <p className="mt-2 max-w-2xl text-sm text-ink-2">{r.description}</p>}
        </div>
        <div className="flex gap-2">
          {hasRole(user, "analyst") && (
            <Button variant="secondary" size="sm" icon={r.is_active ? <Pause className="size-4" /> : <Play className="size-4" />} onClick={toggleActive} loading={update.isPending}>
              {r.is_active ? "Pausar" : "Activar"}
            </Button>
          )}
          {hasRole(user, "admin") && (
            <Button variant="danger" size="sm" icon={<Trash2 className="size-4" />} onClick={destroy} loading={remove.isPending}>
              Eliminar
            </Button>
          )}
        </div>
      </header>

      <div className="mt-8 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="flex flex-col gap-8">
          <MapView
            className="aspect-[16/10] rounded-[var(--radius-panel)] border border-rule"
            label={`Mapa de la zona ${r.name}`}
            bounds={geometryBounds(r.geometry)}
            onLoad={(map) => {
              mapRef.current = map;
              setRegions(map, [r]);
              if (geo.data) setAlerts(map, geo.data);
            }}
          />
          <section aria-labelledby="region-alerts">
            <SectionTitle><span id="region-alerts">Alertas abiertas</span></SectionTitle>
            {alerts.data?.items.length === 0 && <p className="panel p-5 text-sm text-ink-2">No hay alertas abiertas en esta zona.</p>}
            <ul className="flex flex-col gap-3">{alerts.data?.items.map((a, i) => <AlertRow key={a.id} alert={a} index={i} />)}</ul>
          </section>
        </div>
        <aside className="flex flex-col gap-6">
          {hasRole(user, "analyst") && <AnalyzeForm regionId={r.id} disabled={!r.is_active || running} />}
          <section aria-labelledby="region-jobs">
            <SectionTitle><span id="region-jobs">Análisis de esta zona</span></SectionTitle>
            {jobs.data?.items.length === 0 && <p className="panel p-5 text-sm text-ink-2">Todavía no se ha analizado esta zona.</p>}
            <ul className="flex flex-col gap-3">{jobs.data?.items.map((j) => <JobItem key={j.id} job={j} />)}</ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
