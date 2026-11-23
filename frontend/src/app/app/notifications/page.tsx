"use client";

import { useEffect, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Checkbox, SelectField, TextField } from "@/components/ui/Field";
import { EmptyState, LoadingBlock, toast } from "@/components/ui/Feedback";
import { ApiError } from "@/lib/api/client";
import { useNotifications, usePreferences, useRegions, useSavePreferences } from "@/lib/api/hooks";
import type { ChangeSignal, NotificationFrequency, Preferences, Severity } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { SEVERITY, SIGNAL, fmtDateTime } from "@/lib/format";

const KIND = { alert: "Alerta", digest: "Resumen", report: "Informe", password_reset: "Seguridad" } as const;
const STATUS_TXT = { pending: "Pendiente", sent: "Enviado", failed: "Falló", skipped: "Omitido" } as const;

export default function NotificationsPage() {
  const prefs = usePreferences();
  const save = useSavePreferences();
  const regions = useRegions();
  const [page, setPage] = useState(1);
  const history = useNotifications(page);
  const [form, setForm] = useState<Preferences | null>(null);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (prefs.data) setForm(prefs.data);
  }, [prefs.data]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    if (form.notify_email && !/^\S+@\S+\.\S+$/.test(form.notify_email)) return setError("Escribe un correo válido o deja el campo vacío.");
    setError(undefined);
    try {
      await save.mutateAsync({ ...form, notify_email: form.notify_email || null });
      toast.success(form.notifications_enabled ? "Preferencias guardadas. Te avisaremos por correo." : "Notificaciones desactivadas.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudieron guardar.");
    }
  }

  const toggleIn = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  return (
    <>
      <PageHeader eyebrow="Notificaciones" title={<>Que te avisen <span>solo lo importante.</span></>} description="Elige qué zonas te interesan, desde qué nivel de importancia y con qué frecuencia. Nunca recibirás dos correos por la misma alerta." />
      <div className="grid grid-cols-1 gap-6 px-5 pb-12 sm:px-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {!form ? (
          <LoadingBlock rows={4} />
        ) : (
          <form onSubmit={submit} className="panel panel-ticks flex flex-col gap-6 p-5 sm:p-6">
            <label className="flex items-center justify-between gap-4 rounded-xl border border-rule bg-field p-4">
              <span>
                <span className="block font-semibold text-ink">Recibir notificaciones por correo</span>
                <span className="block text-xs text-ink-2">Desactivado por defecto. Puedes cancelarlas en cualquier momento.</span>
              </span>
              <input type="checkbox" role="switch" className="peer sr-only" checked={form.notifications_enabled} onChange={(e) => setForm({ ...form, notifications_enabled: e.target.checked })} />
              <span aria-hidden className="relative h-6 w-11 shrink-0 rounded-xs border border-rule-strong bg-paper-3 transition-colors peer-checked:border-brand peer-checked:bg-brand peer-focus-visible:ring-2 peer-focus-visible:ring-water after:absolute after:top-px after:left-px after:size-5 after:rounded-[1px] after:bg-ink-3 after:transition-transform peer-checked:after:translate-x-5 peer-checked:after:bg-field" />
            </label>
            <fieldset disabled={!form.notifications_enabled} className={cn("flex flex-col gap-5", !form.notifications_enabled && "opacity-50")}>
              <TextField label="Correo de destino" type="email" value={form.notify_email ?? ""} onChange={(e) => setForm({ ...form, notify_email: e.target.value })} placeholder={form.effective_email} hint={`Si lo dejas vacío usaremos ${form.effective_email}.`} error={error} />
              <SelectField label="Avisarme desde" value={form.min_severity} onChange={(e) => setForm({ ...form, min_severity: e.target.value as Severity })}>
                {(Object.keys(SEVERITY) as Severity[]).map((s) => <option key={s} value={s}>{SEVERITY[s].label} o superior</option>)}
              </SelectField>
              <SelectField label="Frecuencia" value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value as NotificationFrequency })}>
                <option value="immediate">Inmediata · un correo por cada alerta nueva</option>
                <option value="daily">Resumen diario · 7:00 a. m.</option>
                <option value="weekly">Resumen semanal · lunes</option>
              </SelectField>
              <fieldset>
                <legend className="mb-2 text-sm font-medium text-ink">Tipos de cambio <span className="text-xs text-ink-2">(ninguno marcado = todos)</span></legend>
                <div className="flex flex-col gap-2">
                  {(Object.keys(SIGNAL) as ChangeSignal[]).map((s) => (
                    <Checkbox key={s} label={SIGNAL[s].label} checked={form.signals.includes(s)} onChange={() => setForm({ ...form, signals: toggleIn(form.signals, s) })} />
                  ))}
                </div>
              </fieldset>
              <fieldset>
                <legend className="mb-2 text-sm font-medium text-ink">Zonas <span className="text-xs text-ink-2">(ninguna marcada = todas)</span></legend>
                <div className="grid max-h-56 gap-2 overflow-y-auto pr-1">
                  {regions.data?.map((r) => (
                    <Checkbox key={r.id} label={r.name} description={r.territory_name} checked={form.region_ids.includes(r.id)} onChange={() => setForm({ ...form, region_ids: toggleIn(form.region_ids, r.id) })} />
                  ))}
                </div>
              </fieldset>
            </fieldset>
            <Button type="submit" loading={save.isPending} className="self-start">Guardar preferencias</Button>
          </form>
        )}

        <section aria-labelledby="sent-title">
          <h2 id="sent-title" className="mb-4 font-display text-2xl text-ink">Historial de envíos</h2>
          {history.isLoading && <LoadingBlock rows={3} />}
          {history.data?.items.length === 0 && <EmptyState title="Sin envíos" description="Aquí verás cada correo que te enviemos y si llegó al servidor de correo." />}
          <ul className="flex flex-col gap-2">
            {history.data?.items.map((n) => (
              <li key={n.id} className="flex items-start gap-3 rounded-2xl border border-rule bg-paper-2 p-4">
                <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.status === "sent" ? "bg-brand" : n.status === "failed" ? "bg-signal" : "bg-ink-3")} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink">{n.subject}</p>
                  <p className="mt-0.5 font-mono text-[0.6875rem] text-ink-2">{KIND[n.kind]} · {STATUS_TXT[n.status]} · {fmtDateTime(n.sent_at ?? n.created_at)} · {n.to_email}</p>
                </div>
              </li>
            ))}
          </ul>
          {history.data && history.data.total > history.data.page_size && (
            <div className="mt-4 flex justify-center gap-2">
              <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</Button>
              <Button size="sm" variant="ghost" disabled={page * history.data.page_size >= history.data.total} onClick={() => setPage((p) => p + 1)}>Siguiente</Button>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
