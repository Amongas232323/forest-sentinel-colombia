"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { PageHeader } from "@/components/layout/AppShell";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from "@/components/ui/Feedback";
import { AlertRow } from "@/features/alerts/AlertRow";
import { JobItem, Kpi, MonthlyBars, SectionTitle } from "@/features/dashboard/widgets";
import { AtlasOverview, type ZoneMarker } from "@/features/dashboard/AtlasOverview";
import { useAlerts, useJobs, useOverview, useTerritoryGeometries } from "@/lib/api/hooks";
import type { Severity } from "@/lib/api/types";
import { hasRole, useAuth } from "@/lib/auth/store";
import { fmtDate, fmtNumber, SEVERITY } from "@/lib/format";

const OPEN = ["new", "pending_review", "in_review"] as const;

export default function DashboardPage() {
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const overview = useOverview();
  const recent = useAlerts({ status: [...OPEN] }, 1, "severity", 30);
  const jobs = useJobs(undefined, 1);
  const territories = useTerritoryGeometries();

  // A escala de país las alertas de una misma zona se montan unas sobre otras: mostramos un marcador por zona.
  const markers: ZoneMarker[] = useMemo(() => {
    const byRegion = new Map<string, { name: string; lat: number; lon: number; n: number; worst: Severity }>();
    for (const a of recent.data?.items ?? []) {
      const cur = byRegion.get(a.region_id);
      if (!cur) byRegion.set(a.region_id, { name: a.region_name, lat: a.centroid[1], lon: a.centroid[0], n: 1, worst: a.severity });
      else {
        cur.n += 1;
        if (SEVERITY[a.severity].order > SEVERITY[cur.worst].order) cur.worst = a.severity;
      }
    }
    return [...byRegion.entries()].map(([id, r]) => ({
      id,
      lat: r.lat,
      lon: r.lon,
      label: `${r.name}: ${r.n} ${r.n === 1 ? "alerta abierta" : "alertas abiertas"}, máxima prioridad ${SEVERITY[r.worst].label}`,
      severity: r.worst,
      count: r.n,
      onSelect: () => router.push(`/app/alerts?region_id=${id}`),
    }));
  }, [recent.data, router]);

  const o = overview.data;
  const noRegions = o && o.region_count === 0;

  return (
    <>
      <PageHeader
        eyebrow={`● ${fmtDate(new Date().toISOString(), { weekday: "long", day: "numeric", month: "long" })}`}
        title={
          <>
            Hola, {user?.full_name.split(" ")[0]}. <span className="text-ink-2">Esto es lo que cambió.</span>
          </>
        }
        description={o ? (o.alerts_pending ? `Hay ${o.alerts_pending} ${o.alerts_pending === 1 ? "hallazgo que espera" : "hallazgos que esperan"} revisión humana.` : "No hay hallazgos pendientes de revisión.") : undefined}
        actions={hasRole(user, "analyst") ? <ButtonLink href="/app/regions" variant="secondary">Analizar una zona</ButtonLink> : undefined}
      />

      <div className="grid grid-cols-1 gap-x-8 gap-y-12 px-5 pb-16 sm:px-8 xl:grid-cols-12">
        {/* Globo */}
        <section aria-label="Mapa global de alertas" className="plate relative min-h-[380px] xl:col-span-7 xl:min-h-[560px]">
          <AtlasOverview markers={markers} territories={territories.data} />
          <div className="pointer-events-none absolute inset-x-3 top-3 flex flex-wrap gap-1.5">
            {(o?.by_territory ?? []).map((t) => (
              <Link
                key={t.slug}
                href={`/app/alerts?territory=${t.slug}`}
                className="pointer-events-auto rounded-xs border border-ink bg-field px-2.5 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-paper-3"
              >
                {t.name} <span className="ml-1 font-mono text-ochre">{t.open_alerts}</span>
              </Link>
            ))}
          </div>
          <p className="pointer-events-none absolute bottom-2 left-3 bg-field/90 px-1.5 py-0.5 text-xs text-ink-2">Cada punto es una zona con alertas abiertas</p>
        </section>

        {/* KPIs */}
        <section aria-label="Indicadores" className="grid grid-cols-2 self-start border-t border-ink xl:col-span-5">
          {overview.isLoading &&
            Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="m-2 h-28" />)}
          {overview.isError && (
            <div className="col-span-2">
              <ErrorState message="No pudimos cargar los indicadores." onRetry={() => overview.refetch()} />
            </div>
          )}
          {o && (
            <>
              <Kpi lead label="Por revisar" value={o.alerts_pending} explain="Alertas nuevas o en revisión. Nadie las ha confirmado aún." tone={o.alerts_pending ? "amber" : "default"} href="/app/alerts?status=new&status=pending_review&status=in_review" />
              <Kpi label="Superficie vigilada" value={o.monitored_area_km2} unit="km²" explain={`Suma de las ${o.active_region_count} zonas activas dentro de los cuatro territorios.`} href="/app/regions" />
              <Kpi label="Área con cambios" value={o.changed_area_ha} digits={1} unit="ha" explain="Superficie de las alertas no descartadas." tone={o.changed_area_ha ? "amber" : "default"} />
              <Kpi label="Confirmados" value={o.alerts_confirmed} explain="Hallazgos verificados por una persona como cambio real." tone={o.alerts_confirmed ? "alert" : "default"} href="/app/alerts?status=confirmed" />
              <Kpi label="Imágenes procesadas" value={o.images_processed} explain="Escenas Sentinel-2 distintas usadas en los análisis." />
              <Kpi label="Análisis en curso" value={o.jobs_running} explain={o.last_update ? `Último análisis terminado el ${fmtDate(o.last_update)}.` : "Todavía no hay análisis terminados."} href="/app/jobs" />
            </>
          )}
        </section>

        {noRegions && (
          <div className="xl:col-span-12">
            <EmptyState
              title="Aún no hay zonas vigiladas"
              description="Crea una zona dentro de uno de los cuatro territorios y lanza el primer análisis. Las cifras de este tablero aparecerán con los resultados reales."
              action={<ButtonLink href="/app/explorer">Abrir el explorador</ButtonLink>}
            />
          </div>
        )}

        {/* Alertas recientes */}
        <section aria-labelledby="recent-title" className="xl:col-span-7">
          <SectionTitle
            action={
              <Link href="/app/alerts" className="flex items-center gap-1 text-sm text-brand link-underline">
                Ver todas <ArrowRight className="size-4" />
              </Link>
            }
          >
            <span id="recent-title">Prioridades de revisión</span>
          </SectionTitle>
          {recent.isLoading && <LoadingBlock rows={4} />}
          {recent.data && recent.data.items.length === 0 && (
            <EmptyState title="Nada pendiente" description="Cuando un análisis detecte un cambio importante aparecerá aquí, ordenado por prioridad." />
          )}
          <ul className="flex flex-col border-t border-ink">
            {recent.data?.items.slice(0, 5).map((a, i) => <AlertRow key={a.id} alert={a} index={i} />)}
          </ul>
        </section>

        {/* Actividad + tendencia */}
        <div className="flex flex-col gap-6 xl:col-span-5">
          <section aria-labelledby="activity-title">
            <SectionTitle action={<Link href="/app/jobs" className="text-sm text-brand link-underline">Historial</Link>}>
              <span id="activity-title">Actividad del sistema</span>
            </SectionTitle>
            {jobs.isLoading && <LoadingBlock rows={2} />}
            {jobs.data?.items.length === 0 && <p className="border-t border-rule py-4 text-sm text-ink-2">Todavía no se ha ejecutado ningún análisis.</p>}
            <ul className="flex flex-col border-t border-ink">{jobs.data?.items.slice(0, 3).map((j) => <JobItem key={j.id} job={j} />)}</ul>
          </section>
          {o && o.monthly_changed_ha.length > 0 && (
            <section aria-labelledby="trend-title">
              <SectionTitle>
                <span id="trend-title">Cambio detectado por mes</span>
              </SectionTitle>
              <MonthlyBars data={o.monthly_changed_ha} />
              <p className="mt-2 font-mono text-xs text-ink-2">Total: {fmtNumber(o.monthly_changed_ha.reduce((s, d) => s + d.changed_ha, 0), 1)} ha</p>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
