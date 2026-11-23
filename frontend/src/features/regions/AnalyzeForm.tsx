"use client";

import { CloudSun } from "lucide-react";
import { useMemo, useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { toast } from "@/components/ui/Feedback";
import { ApiError } from "@/lib/api/client";
import { useAvailableScenes, useSubmitJob } from "@/lib/api/hooks";
import type { JobCreate, Scene } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { fmtDateShort, isoDay } from "@/lib/format";

const DAY = 86_400_000;

/** Mismas reglas que JobCreate del backend (se vuelven a validar en el servidor). */
const jobSchema = z
  .object({ reference_start: z.string(), reference_end: z.string(), observation_start: z.string(), observation_end: z.string() })
  .superRefine((d, ctx) => {
    const t = (s: string) => new Date(s).getTime();
    if (t(d.reference_start) > t(d.reference_end) || t(d.observation_start) > t(d.observation_end)) ctx.addIssue({ code: "custom", message: "Cada periodo debe empezar antes de terminar." });
    if (t(d.reference_end) >= t(d.observation_start)) ctx.addIssue({ code: "custom", message: "El periodo de referencia debe ser anterior al de observación." });
    if (t(d.reference_start) < t("2017-01-01")) ctx.addIssue({ code: "custom", message: "No hay imágenes homogéneas antes de 2017." });
    if (t(d.observation_end) > Date.now()) ctx.addIssue({ code: "custom", message: "La observación no puede terminar en el futuro." });
    for (const [a, b] of [[d.reference_start, d.reference_end], [d.observation_start, d.observation_end]] as const)
      if ((t(b) - t(a)) / DAY > 180) ctx.addIssue({ code: "custom", message: "Cada periodo puede abarcar máximo 180 días." });
  });

function presets(): { id: string; label: string; hint: string; value: JobCreate }[] {
  const now = new Date();
  // La última temporada seca que ya terminó completa (termina el 15 de marzo).
  const thisYear = now.getUTCFullYear();
  const y = now.getTime() > Date.UTC(thisYear, 2, 15) ? thisYear : thisYear - 1;
  const today = isoDay(now);
  return [
    {
      id: "recent",
      label: "Cambios recientes",
      hint: "Últimos 45 días frente a los 90 anteriores. Ideal para alerta temprana.",
      value: {
        reference_start: isoDay(new Date(now.getTime() - 136 * DAY)),
        reference_end: isoDay(new Date(now.getTime() - 46 * DAY)),
        observation_start: isoDay(new Date(now.getTime() - 45 * DAY)),
        observation_end: today,
      },
    },
    {
      id: "dry",
      label: "Temporada seca, año contra año",
      hint: "Diciembre–marzo: menos nubes y la época en que más se tala en la Amazonía.",
      value: { reference_start: `${y - 2}-12-01`, reference_end: `${y - 1}-03-15`, observation_start: `${y - 1}-12-01`, observation_end: `${y}-03-15` },
    },
  ];
}

function SceneStrip({ scenes, loading, error }: { scenes?: Scene[]; loading: boolean; error: boolean }) {
  if (loading) return <p className="text-xs text-ink-2 motion-safe:animate-pulse">Consultando el catálogo satelital…</p>;
  if (error) return <p className="text-xs text-ochre">No pudimos consultar el catálogo ahora. Puedes lanzar el análisis igualmente.</p>;
  if (!scenes) return null;
  if (scenes.length === 0) return <p className="text-xs text-ochre">No hay imágenes con menos de 60 % de nubes en este periodo. Prueba otras fechas.</p>;
  return (
    <div>
      <div className="flex h-10 items-end gap-0.5" aria-hidden>
        {scenes.slice(0, 40).map((s) => (
          <span key={s.scene_id} title={`${fmtDateShort(s.acquired_at)} · ${Math.round(s.cloud_cover ?? 0)} % nubes`} className="w-1.5 rounded-t bg-brand-tint" style={{ height: `${Math.max(10, 100 - (s.cloud_cover ?? 0))}%` }} />
        ))}
      </div>
      <p className="mt-1 text-xs text-ink-2">
        {scenes.length} {scenes.length === 1 ? "imagen disponible" : "imágenes disponibles"} · la más despejada: {Math.round(scenes[0]?.cloud_cover ?? 0)} % de nubes. Se combinan las 4 mejores.
      </p>
    </div>
  );
}

export function AnalyzeForm({ regionId, disabled }: { regionId: string; disabled?: boolean }) {
  const options = useMemo(presets, []);
  const [preset, setPreset] = useState(options[0]!.id);
  const [custom, setCustom] = useState<JobCreate>(options[0]!.value);
  const [error, setError] = useState<string>();
  const submit = useSubmitJob(regionId);
  const value = preset === "custom" ? custom : options.find((o) => o.id === preset)!.value;

  const ref = useAvailableScenes(regionId, value.reference_start, value.reference_end, true);
  const obs = useAvailableScenes(regionId, value.observation_start, value.observation_end, true);

  async function launch() {
    const parsed = jobSchema.safeParse(value);
    if (!parsed.success) return setError(parsed.error.issues[0]?.message);
    setError(undefined);
    try {
      await submit.mutateAsync(value);
      toast.success("Análisis en cola. Verás el progreso en esta página.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo lanzar el análisis.");
    }
  }

  const dateInput = (key: keyof JobCreate, label: string) => (
    <label className="flex flex-col gap-1 text-xs text-ink-2">
      {label}
      <input
        type="date"
        value={custom[key]}
        min="2017-01-01"
        max={isoDay(new Date())}
        onChange={(e) => setCustom((c) => ({ ...c, [key]: e.target.value }))}
        className="h-11 rounded-xl border border-rule bg-field px-3 text-sm text-ink"
      />
    </label>
  );

  return (
    <section aria-labelledby="analyze-title" className="panel panel-ticks flex flex-col gap-5 p-5">
      <div>
        <p className="eyebrow mb-1">Nuevo análisis</p>
        <h2 id="analyze-title" className="font-display text-2xl text-ink">¿Qué periodos comparamos?</h2>
      </div>
      <div role="radiogroup" aria-label="Periodos" className="grid gap-2">
        {[...options, { id: "custom", label: "Elegir fechas", hint: "Define tú los dos periodos (máximo 180 días cada uno).", value: custom }].map((o) => (
          <label key={o.id} className={cn("flex cursor-pointer gap-3 rounded-xl border p-3 transition-colors", preset === o.id ? "border-brand bg-brand-tint" : "border-rule hover:border-rule-strong")}>
            <input type="radio" name="preset" value={o.id} checked={preset === o.id} onChange={() => setPreset(o.id)} className="mt-1 accent-[#1F4D36]" />
            <span>
              <span className="block text-sm font-semibold text-ink">{o.label}</span>
              <span className="block text-xs text-ink-2">{o.hint}</span>
            </span>
          </label>
        ))}
      </div>
      {preset === "custom" && (
        <div className="grid grid-cols-2 gap-3">
          {dateInput("reference_start", "Referencia: desde")}
          {dateInput("reference_end", "Referencia: hasta")}
          {dateInput("observation_start", "Observación: desde")}
          {dateInput("observation_end", "Observación: hasta")}
        </div>
      )}
      <div className="grid gap-4 rounded-xl bg-field p-4 sm:grid-cols-2">
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink"><CloudSun className="size-3.5 text-brand" aria-hidden /> Antes · {fmtDateShort(value.reference_start)} – {fmtDateShort(value.reference_end)}</p>
          <SceneStrip scenes={ref.data} loading={ref.isLoading} error={ref.isError} />
        </div>
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink"><CloudSun className="size-3.5 text-brand" aria-hidden /> Después · {fmtDateShort(value.observation_start)} – {fmtDateShort(value.observation_end)}</p>
          <SceneStrip scenes={obs.data} loading={obs.isLoading} error={obs.isError} />
        </div>
      </div>
      {error && <p role="alert" className="text-sm text-signal">▲ {error}</p>}
      <Button onClick={launch} loading={submit.isPending} disabled={disabled}>
        Lanzar análisis
      </Button>
      <p className="text-xs text-ink-2">El análisis descarga solo la porción necesaria de cada imagen. Suele tardar entre 1 y 10 minutos según el tamaño de la zona.</p>
    </section>
  );
}
