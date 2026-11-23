"use client";

import { animate, useInView, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { JobBadge } from "@/components/ui/Badges";
import { ProcessingIndicator } from "@/components/ui/Feedback";
import type { Job, Overview } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { JOB_STAGE, fmtDateShort, fmtNumber, fmtRelative } from "@/lib/format";

function CountUp({ value, digits = 0 }: { value: number; digits?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(reduced ? value : 0);
  useEffect(() => {
    if (!inView) return;
    if (reduced) return setShown(value);
    const controls = animate(0, value, { duration: 1.4, ease: [0.22, 1, 0.36, 1], onUpdate: setShown });
    return () => controls.stop();
  }, [inView, value, reduced]);
  return <span ref={ref}>{fmtNumber(shown, digits)}</span>;
}

export function Kpi({ label, value, unit, digits = 0, explain, tone = "default", href, lead = false }: { label: string; value: number; unit?: string; digits?: number; explain: string; tone?: "default" | "amber" | "alert"; href?: string; lead?: boolean }) {
  const body = (
    <>
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "mt-2 font-display display-tight leading-none font-medium",
          lead ? "text-[clamp(3.052rem,6vw,4.768rem)]" : "text-h3",
          tone === "amber" ? "text-ochre" : tone === "alert" ? "text-signal" : "text-ink",
        )}
      >
        <CountUp value={value} digits={digits} />
        {unit && <span className="ml-1 font-sans text-base font-normal text-ink-2">{unit}</span>}
      </p>
      <p className="mt-2 text-xs leading-relaxed text-ink-2">{explain}</p>
    </>
  );
  // Celdas tipo libro contable: líneas finas entre cifras, sin cajas. La cifra principal ocupa toda la fila.
  const cls = cn("block border-b border-rule py-4 transition-colors duration-200", lead ? "col-span-2 pr-4" : "even:pr-4 odd:border-l odd:border-rule odd:pl-4");
  return href ? (
    <Link href={href} className={cn(cls, "group hover:bg-paper-2")}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-4">
      <h2 className="font-display text-h4 font-medium text-ink">{children}</h2>
      {action}
    </div>
  );
}

/** Área cambiada por mes — barras simples con una tabla alternativa accesible. */
export function MonthlyBars({ data }: { data: Overview["monthly_changed_ha"] }) {
  const max = Math.max(...data.map((d) => d.changed_ha), 1);
  const last = data.slice(-12);
  return (
    <figure>
      <div className="flex h-40 items-stretch gap-1.5 border-b border-ink" aria-hidden>
        {last.map((d) => (
          <div key={d.month} className="group relative flex h-full max-w-14 flex-1 flex-col">
            <div className="relative flex-1">
              <div className="absolute inset-x-0 bottom-0 bg-ink transition-colors duration-200 group-hover:bg-brand" style={{ height: `${Math.max(2, (d.changed_ha / max) * 100)}%` }} />
              <span className="pointer-events-none absolute -top-1 left-1/2 -translate-x-1/2 -translate-y-full bg-ink px-1.5 py-0.5 font-mono text-[0.6875rem] whitespace-nowrap text-paper opacity-0 group-hover:opacity-100">{fmtNumber(d.changed_ha, 1)} ha</span>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1.5" aria-hidden>
        {last.map((d) => (
          <span key={d.month} className="max-w-14 flex-1 text-center font-mono text-[0.6875rem] text-ink-2">{d.month.slice(5)}</span>
        ))}
      </div>
      {/* Las tablas ignoran width:1px, por eso el contenedor visualmente oculto es un div. */}
      <div className="sr-only">
      <table>
        <caption>Área con cambios detectados por mes de observación</caption>
        <thead><tr><th>Mes</th><th>Hectáreas</th></tr></thead>
        <tbody>{last.map((d) => <tr key={d.month}><td>{d.month}</td><td>{fmtNumber(d.changed_ha, 1)}</td></tr>)}</tbody>
      </table>
      </div>
      <figcaption className="mt-3 text-xs text-ink-2">Hectáreas con cambio detectado según el mes de la imagen más reciente (solo análisis con calidad suficiente).</figcaption>
    </figure>
  );
}

export function JobItem({ job }: { job: Job }) {
  const running = job.status === "running" || job.status === "queued";
  return (
    <li className="flex flex-col gap-2 border-b border-rule py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold text-ink">{job.region_name}</p>
        <JobBadge status={job.status} />
      </div>
      <p className="text-xs text-ink-2">
        {fmtDateShort(job.reference_start)} – {fmtDateShort(job.reference_end)} <span aria-hidden>→</span> {fmtDateShort(job.observation_start)} – {fmtDateShort(job.observation_end)}
      </p>
      {running && <ProcessingIndicator progress={job.progress} label={JOB_STAGE[job.stage] ?? job.stage} />}
      {job.status === "failed" && job.error && <p className="text-xs text-signal">{job.error}</p>}
      {job.status === "succeeded" && job.result_id && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-ink-2">Terminado {fmtRelative(job.finished_at)}</span>
          <Link href={`/app/compare?result=${job.result_id}`} className="font-semibold text-brand link-underline">
            Comparar imágenes
          </Link>
        </div>
      )}
    </li>
  );
}
