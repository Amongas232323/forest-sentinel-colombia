"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/Feedback";
import { JobItem } from "@/features/dashboard/widgets";
import { useJobs } from "@/lib/api/hooks";

export default function JobsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useJobs(undefined, page);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <>
      <PageHeader eyebrow="Historial de procesamiento" title={<>Cada análisis, <span>trazable.</span></>} description="Qué zona se analizó, con qué fechas, cuándo y con qué resultado. Los análisis en curso se actualizan solos." />
      <div className="px-5 pb-12 sm:px-8">
        {isLoading && <LoadingBlock rows={4} />}
        {isError && <ErrorState message="No pudimos cargar el historial." onRetry={() => refetch()} />}
        {data?.items.length === 0 && <EmptyState title="Sin análisis todavía" description="Los análisis aparecen aquí cuando alguien los lanza desde una zona o cuando el sistema los programa automáticamente." />}
        <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">{data?.items.map((j) => <JobItem key={j.id} job={j} />)}</ul>
        {pages > 1 && (
          <nav aria-label="Paginación" className="mt-6 flex items-center justify-center gap-3">
            <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</Button>
            <span className="font-mono text-xs text-ink-2">{page} / {pages}</span>
            <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Siguiente</Button>
          </nav>
        )}
      </div>
    </>
  );
}
