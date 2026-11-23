"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/AppShell";
import { JobBadge } from "@/components/ui/Badges";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/Feedback";
import { TerritorySilhouette } from "@/features/regions/TerritorySilhouette";
import { useRegions, useTerritories, useTerritoryGeometries } from "@/lib/api/hooks";
import { hasRole, useAuth } from "@/lib/auth/store";
import { fmtKm2, fmtNumber, fmtRelative } from "@/lib/format";

export default function RegionsPage() {
  const user = useAuth((s) => s.user);
  const territories = useTerritories();
  const regions = useRegions();
  const geometries = useTerritoryGeometries();

  return (
    <>
      <PageHeader
        eyebrow="Zonas vigiladas"
        title={<>Dónde estamos <span>mirando.</span></>}
        description="Cada zona pertenece a uno de los cuatro territorios y se analiza de forma periódica o cuando lo pidas."
        actions={hasRole(user, "analyst") ? <ButtonLink href="/app/explorer" variant="secondary">Dibujar zona en el mapa</ButtonLink> : undefined}
      />
      <div className="flex flex-col gap-12 px-5 pb-16 sm:px-8">
        {(territories.isLoading || regions.isLoading) && <LoadingBlock rows={4} />}
        {regions.isError && <ErrorState message="No pudimos cargar las zonas." onRetry={() => regions.refetch()} />}
        {regions.data?.length === 0 && <EmptyState title="Todavía no hay zonas" description="Abre el explorador y dibuja un rectángulo dentro de un territorio para empezar a vigilarlo." />}
        {territories.data?.map((t, n) => {
          const items = regions.data?.filter((r) => r.territory_slug === t.slug) ?? [];
          const shape = geometries.data?.find((g) => g.slug === t.slug);
          return (
            <section key={t.slug} aria-labelledby={`t-${t.slug}`} className="grid grid-cols-1 gap-x-10 gap-y-5 border-t border-ink pt-5 md:grid-cols-[13rem_minmax(0,1fr)]">
              {/* Lámina del atlas: número, nombre, el contorno real del territorio con sus zonas, y sus cifras. */}
              <div className="flex gap-4 md:flex-col">
                <div className="w-24 shrink-0 md:w-full">
                  <p className="font-mono text-xs text-ink-2">{String(n + 1).padStart(2, "0")}</p>
                  {shape && <TerritorySilhouette geometry={shape.geometry} zones={items.map((r) => ({ bbox: r.bbox, alert: r.open_alerts > 0 }))} className="mt-2 h-24 w-full md:h-40" />}
                </div>
                <div>
                  <h2 id={`t-${t.slug}`} className="font-display text-h4 font-medium text-ink md:text-h3">{t.name}</h2>
                  <p className="mt-1 font-mono text-xs text-ink-2">{fmtNumber(t.area_km2)} km² · {t.open_alerts} alertas abiertas</p>
                </div>
              </div>
              {items.length === 0 ? (
                <p className="self-start border-b border-rule pb-4 text-sm text-ink-2">Sin zonas en este territorio.</p>
              ) : (
                <ul className="self-start border-t border-rule">
                  {items.map((r) => (
                    <li key={r.id}>
                      <Link href={`/app/regions/${r.id}`} className="group grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-6 gap-y-3 border-b border-rule py-4 pr-2 transition-colors duration-200 hover:bg-paper-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
                        <div className="min-w-0 pl-1">
                          <h3 className="text-base font-semibold text-ink group-hover:underline group-hover:decoration-1 group-hover:underline-offset-4">{r.name}</h3>
                          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-2">
                            <span>{r.is_active ? `Último análisis ${fmtRelative(r.last_run_at)}` : "Pausada"}</span>
                            {r.last_job_status && <JobBadge status={r.last_job_status} />}
                          </div>
                        </div>
                        <dl className="col-span-2 row-start-2 grid grid-cols-3 gap-x-6 text-xs sm:col-span-1 sm:row-start-auto">
                          <div><dt className="text-ink-2">Área</dt><dd className="mt-0.5 font-mono text-sm text-ink">{fmtKm2(r.area_km2)}</dd></div>
                          <div><dt className="text-ink-2">Alertas</dt><dd className={`mt-0.5 font-mono text-sm ${r.open_alerts ? "font-medium text-ochre" : "text-ink"}`}>{r.open_alerts}</dd></div>
                          <div><dt className="text-ink-2">Cada</dt><dd className="mt-0.5 font-mono text-sm text-ink">{r.cadence_days} días</dd></div>
                        </dl>
                        <ArrowUpRight className="col-start-2 row-start-1 size-4 shrink-0 text-brand opacity-0 transition-[opacity,transform] duration-200 group-hover:translate-x-0.5 group-hover:opacity-100 sm:col-start-3" aria-hidden />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    </>
  );
}
