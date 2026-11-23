"use client";

import { motion } from "framer-motion";
import { ArrowUpRight, MapPin } from "lucide-react";
import Link from "next/link";
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges";
import type { Alert } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { fmtDateShort, fmtHa, fmtRelative } from "@/lib/format";

const RAIL: Record<Alert["severity"], string> = { low: "bg-moss", moderate: "bg-ochre-mark", high: "bg-ochre", priority: "bg-signal" };

/**
 * Una alerta como línea de libro contable, que se lee en pocos segundos: código y prioridad en el margen,
 * qué y dónde en el cuerpo, qué tan grande y desde cuándo alineados al borde derecho.
 */
export function AlertRow({ alert, index = 0, compact = false }: { alert: Alert; index?: number; compact?: boolean }) {
  return (
    <motion.li initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: Math.min(index, 8) * 0.02, duration: 0.2, ease: [0.2, 0, 0, 1] }}>
      <Link
        href={`/app/alerts/${alert.id}`}
        className="group relative grid grid-cols-[minmax(0,1fr)_auto] gap-x-5 gap-y-2 border-b border-rule py-4 pr-2 pl-4 transition-colors duration-200 hover:bg-paper-2 sm:grid-cols-[10.5rem_minmax(0,1fr)_auto]"
      >
        <span aria-hidden className={cn("absolute inset-y-4 left-0 w-[3px]", RAIL[alert.severity])} />
        <div className="col-span-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 sm:col-span-1 sm:flex-col sm:items-start">
          <span className="font-mono text-xs text-ink-2">{alert.code}</span>
          <SeverityBadge severity={alert.severity} />
        </div>
        <div className="min-w-0">
          <p className="text-base font-semibold leading-snug text-ink group-hover:underline group-hover:decoration-1 group-hover:underline-offset-4">{alert.explanation.headline}</p>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-2">
            <MapPin className="size-3.5 shrink-0" strokeWidth={1.6} aria-hidden />
            <span className="min-w-0">
              {alert.region_name} · {alert.territory_name}
            </span>
          </p>
          {!compact && (
            <p className="mt-1 text-sm text-ink-2">
              Imágenes del {fmtDateShort(alert.reference_date)} y el {fmtDateShort(alert.observation_date)}
              {alert.detection_count > 1 && <> · detectada {alert.detection_count} veces</>}
            </p>
          )}
          {!compact && <StatusBadge status={alert.status} className="mt-2" />}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 text-right">
          <p className="font-display text-h4 leading-none font-medium text-ink sm:text-h3">{fmtHa(alert.area_ha)}</p>
          <p className="font-mono text-xs text-ink-2">{fmtRelative(alert.last_detected_at)}</p>
          <ArrowUpRight className="mt-auto size-4 text-brand opacity-0 transition-[opacity,transform] duration-200 group-hover:translate-x-0.5 group-hover:opacity-100" aria-hidden />
        </div>
      </Link>
    </motion.li>
  );
}
