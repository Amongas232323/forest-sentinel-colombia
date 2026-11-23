"use client";

import { Download, SlidersHorizontal } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingBlock, toast } from "@/components/ui/Feedback";
import { AlertRow } from "@/features/alerts/AlertRow";
import { downloadFile } from "@/lib/api/client";
import { useAlerts, useCreateReport } from "@/lib/api/hooks";
import type { AlertFilters, AlertStatus, Severity } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { SEVERITY, STATUS } from "@/lib/format";

const TERRITORIES = [
  ["", "Todos los territorios"],
  ["guaviare", "Guaviare"],
  ["sierra-nevada-santa-marta", "Sierra Nevada de Santa Marta"],
  ["cundinamarca", "Cundinamarca"],
  ["amazonas", "Amazonas"],
] as const;

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "min-h-9 rounded-xs border px-3 py-1.5 text-sm transition-colors duration-150",
        active ? "border-ink bg-ink text-paper" : "border-rule-strong bg-transparent text-ink hover:bg-paper-2",
      )}
    >
      {children}
    </button>
  );
}

function AlertsView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [showFilters, setShowFilters] = useState(false);

  const filters: AlertFilters = useMemo(
    () => ({
      status: params.getAll("status") as AlertStatus[],
      severity: params.getAll("severity") as Severity[],
      territory: params.get("territory") ?? undefined,
      region_id: params.get("region_id") ?? undefined,
      date_from: params.get("date_from") ?? undefined,
      date_to: params.get("date_to") ?? undefined,
    }),
    [params],
  );
  const page = Number(params.get("page") ?? 1);
  const order = (params.get("order") ?? "recent") as "recent" | "severity" | "area";
  const { data, isLoading, isError, refetch, isFetching } = useAlerts(filters, page, order);
  const createReport = useCreateReport();

  function update(mutator: (p: URLSearchParams) => void) {
    const next = new URLSearchParams(params.toString());
    mutator(next);
    if (!next.has("page_keep")) next.delete("page");
    next.delete("page_keep");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }

  function toggle(key: "status" | "severity", value: string) {
    update((p) => {
      const values = p.getAll(key);
      p.delete(key);
      (values.includes(value) ? values.filter((v) => v !== value) : [...values, value]).forEach((v) => p.append(key, v));
    });
  }

  async function exportCsv() {
    try {
      const report = await createReport.mutateAsync({ format: "csv", title: "Exportación de alertas", filters });
      await downloadFile(report.download_url, "alertas.csv");
      toast.success(`Exportadas ${report.alert_count} alertas.`);
    } catch {
      toast.error("No se pudo exportar el CSV.");
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const activeCount = (filters.status?.length ?? 0) + (filters.severity?.length ?? 0) + (filters.territory ? 1 : 0) + (filters.region_id ? 1 : 0) + (filters.date_from ? 1 : 0) + (filters.date_to ? 1 : 0);

  return (
    <>
      <PageHeader
        eyebrow="Centro de alertas"
        title={<>Hallazgos para <span>revisar.</span></>}
        description="Cada alerta es una señal automática que necesita la mirada de una persona antes de considerarse deforestación."
        actions={
          <Button variant="secondary" icon={<Download className="size-4" />} onClick={exportCsv} loading={createReport.isPending}>
            Exportar CSV
          </Button>
        }
      />
      <div className="grid grid-cols-1 gap-x-10 gap-y-6 px-5 pb-16 sm:px-8 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside aria-label="Filtros" className="lg:sticky lg:top-6 lg:self-start">
          <Button variant="secondary" className="mb-3 w-full lg:hidden" icon={<SlidersHorizontal className="size-4" />} onClick={() => setShowFilters((v) => !v)} aria-expanded={showFilters}>
            Filtros {activeCount ? `(${activeCount})` : ""}
          </Button>
          <div className={cn("flex-col gap-6 border-t border-ink pt-5", showFilters ? "flex" : "hidden lg:flex")}>
            <fieldset>
              <legend className="eyebrow mb-3">Estado</legend>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(STATUS) as AlertStatus[]).map((s) => (
                  <Chip key={s} active={!!filters.status?.includes(s)} onClick={() => toggle("status", s)}>
                    {STATUS[s].label}
                  </Chip>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="eyebrow mb-3">Prioridad</legend>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(SEVERITY) as Severity[]).reverse().map((s) => (
                  <Chip key={s} active={!!filters.severity?.includes(s)} onClick={() => toggle("severity", s)}>
                    {SEVERITY[s].label}
                  </Chip>
                ))}
              </div>
            </fieldset>
            <label className="flex flex-col gap-2">
              <span className="eyebrow">Territorio</span>
              <select value={filters.territory ?? ""} onChange={(e) => update((p) => (e.target.value ? p.set("territory", e.target.value) : p.delete("territory")))} className="select-chevron h-11 appearance-none rounded-xs border border-rule-strong bg-field px-3 pr-10 text-sm text-ink">
                {TERRITORIES.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-2">
                <span className="eyebrow">Desde</span>
                <input type="date" value={filters.date_from ?? ""} onChange={(e) => update((p) => (e.target.value ? p.set("date_from", e.target.value) : p.delete("date_from")))} className="h-11 rounded-xs border border-rule-strong bg-field px-3 text-sm text-ink" />
              </label>
              <label className="flex flex-col gap-2">
                <span className="eyebrow">Hasta</span>
                <input type="date" value={filters.date_to ?? ""} onChange={(e) => update((p) => (e.target.value ? p.set("date_to", e.target.value) : p.delete("date_to")))} className="h-11 rounded-xs border border-rule-strong bg-field px-3 text-sm text-ink" />
              </label>
            </div>
            {activeCount > 0 && (
              <button onClick={() => router.replace(pathname)} className="self-start text-sm text-brand link-underline">
                Quitar filtros
              </button>
            )}
          </div>
        </aside>

        <section aria-label="Resultados" aria-busy={isFetching}>
          <div className="mb-0 flex flex-wrap items-center justify-between gap-3 border-b border-ink pb-3">
            <p className="font-mono text-sm text-ink" aria-live="polite">
              {data ? `${data.total} ${data.total === 1 ? "alerta" : "alertas"}` : "Cargando…"}
            </p>
            <label className="flex items-center gap-2 text-sm text-ink-2">
              Ordenar por
              <select value={order} onChange={(e) => update((p) => p.set("order", e.target.value))} className="select-chevron h-10 appearance-none rounded-xs border border-rule-strong bg-field px-3 pr-10 text-ink">
                <option value="recent">Más recientes</option>
                <option value="severity">Prioridad</option>
                <option value="area">Mayor área</option>
              </select>
            </label>
          </div>
          {isLoading && <LoadingBlock rows={5} />}
          {isError && <ErrorState message="No pudimos cargar las alertas." onRetry={() => refetch()} />}
          {data && data.items.length === 0 && (
            <EmptyState title="Sin alertas con estos filtros" description={activeCount ? "Prueba a quitar algún filtro." : "Cuando un análisis encuentre cambios importantes en una zona vigilada, aparecerán aquí."} />
          )}
          <ul className="flex flex-col">{data?.items.map((a, i) => <AlertRow key={a.id} alert={a} index={i} />)}</ul>
          {data && totalPages > 1 && (
            <nav aria-label="Paginación" className="mt-6 flex items-center justify-center gap-3">
              <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => update((p) => { p.set("page", String(page - 1)); p.set("page_keep", "1"); })}>
                Anterior
              </Button>
              <span className="font-mono text-xs text-ink-2">{page} / {totalPages}</span>
              <Button variant="ghost" size="sm" disabled={page >= totalPages} onClick={() => update((p) => { p.set("page", String(page + 1)); p.set("page_keep", "1"); })}>
                Siguiente
              </Button>
            </nav>
          )}
        </section>
      </div>
    </>
  );
}

export default function AlertsPage() {
  return (
    <Suspense>
      <AlertsView />
    </Suspense>
  );
}
