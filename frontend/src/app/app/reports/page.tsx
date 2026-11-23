"use client";

import { Download, FileSpreadsheet, FileText, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { EmptyState, LoadingBlock, toast } from "@/components/ui/Feedback";
import { ApiError, downloadFile } from "@/lib/api/client";
import { useCreateReport, useEmailReport, useReports } from "@/lib/api/hooks";
import type { AlertFilters, Report, ReportFormat, Severity } from "@/lib/api/types";
import { hasRole, useAuth } from "@/lib/auth/store";
import { fmtDateTime, fmtNumber } from "@/lib/format";

function EmailForm({ report, onDone }: { report: Report; onDone: () => void }) {
  const send = useEmailReport();
  const [error, setError] = useState<string>();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const raw = String(new FormData(e.currentTarget).get("to") ?? "");
    const to = raw.split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean);
    if (!to.length || to.some((t) => !/^\S+@\S+\.\S+$/.test(t))) return setError("Escribe uno o varios correos válidos separados por comas.");
    if (to.length > 10) return setError("Máximo 10 destinatarios.");
    try {
      const res = await send.mutateAsync({ id: report.id, to });
      const ok = res.filter((n) => n.status === "sent").length;
      toast[ok === res.length ? "success" : "error"](`Enviado a ${ok} de ${res.length} destinatarios.`);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo enviar.");
    }
  }
  return (
    <form onSubmit={submit} className="mt-3 flex flex-col gap-3 border-t border-rule pt-3 sm:flex-row sm:items-end">
      <TextField label="Enviar a" name="to" placeholder="correo@entidad.gov.co, otro@ong.org" error={error} className="flex-1" />
      <Button type="submit" size="sm" loading={send.isPending} icon={<Send className="size-4" />}>Enviar</Button>
    </form>
  );
}

export default function ReportsPage() {
  const user = useAuth((s) => s.user);
  const reports = useReports();
  const create = useCreateReport();
  const [emailFor, setEmailFor] = useState<string | null>(null);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const severity = String(fd.get("severity"));
    const filters: AlertFilters = {
      territory: String(fd.get("territory")) || undefined,
      severity: severity ? (severity.split(",") as Severity[]) : undefined,
      date_from: String(fd.get("date_from")) || undefined,
      date_to: String(fd.get("date_to")) || undefined,
    };
    try {
      const r = await create.mutateAsync({ format: String(fd.get("format")) as ReportFormat, title: String(fd.get("title")) || "Informe de hallazgos", filters });
      toast.success(`Informe listo con ${r.alert_count} hallazgos.`);
      await downloadFile(r.download_url, `informe.${r.format}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo generar el informe.");
    }
  }

  return (
    <>
      <PageHeader eyebrow="Reportes" title={<>Informes para <span>decidir y actuar.</span></>} description="PDF con resumen ejecutivo y evidencia visual, o CSV para análisis propio. Se construyen con los datos reales del momento." />
      <div className="grid grid-cols-1 gap-x-10 gap-y-10 px-5 pb-16 sm:px-8 xl:grid-cols-[400px_minmax(0,1fr)]">
        <form onSubmit={submit} className="flex flex-col gap-4 self-start border-2 border-ink bg-field p-5">
          <p className="eyebrow">Nuevo informe</p>
          <TextField label="Título" name="title" defaultValue="Informe de hallazgos" maxLength={200} />
          <SelectField label="Formato" name="format" defaultValue="pdf">
            <option value="pdf">PDF · resumen ejecutivo con evidencia</option>
            <option value="csv">CSV · tabla completa</option>
          </SelectField>
          <SelectField label="Territorio" name="territory" defaultValue="">
            <option value="">Todos</option>
            <option value="guaviare">Guaviare</option>
            <option value="sierra-nevada-santa-marta">Sierra Nevada de Santa Marta</option>
            <option value="cundinamarca">Cundinamarca</option>
            <option value="amazonas">Amazonas</option>
          </SelectField>
          <SelectField label="Prioridad" name="severity" defaultValue="">
            <option value="">Todas</option>
            <option value="priority,high">Importantes y prioritarios</option>
            <option value="priority">Solo prioritarios</option>
          </SelectField>
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Desde" name="date_from" type="date" className="" />
            <TextField label="Hasta" name="date_to" type="date" className="" />
          </div>
          <Button type="submit" loading={create.isPending} icon={<Download className="size-4" />}>Generar y descargar</Button>
        </form>

        <section aria-labelledby="history-title">
          <h2 id="history-title" className="border-b border-ink pb-3 font-display text-h4 font-medium text-ink">Informes generados</h2>
          {reports.isLoading && <LoadingBlock rows={3} />}
          {reports.data?.length === 0 && <EmptyState title="Sin informes" description="Genera tu primer informe con el formulario." />}
          <ul className="flex flex-col">
            {reports.data?.map((r) => (
              <li key={r.id} className="border-b border-rule py-4">
                <div className="flex flex-wrap items-center gap-4">
                  {r.format === "pdf" ? <FileText className="size-6 text-brand" aria-hidden /> : <FileSpreadsheet className="size-6 text-brand" aria-hidden />}
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-ink">{r.title}</p>
                    <p className="text-xs text-ink-2">{fmtDateTime(r.created_at)} · {r.alert_count} hallazgos · {fmtNumber(r.size_bytes / 1024, 0)} KB · {r.format.toUpperCase()}</p>
                  </div>
                  <Button size="sm" variant="secondary" icon={<Download className="size-4" />} onClick={() => downloadFile(r.download_url, `informe.${r.format}`).catch(() => toast.error("No se pudo descargar."))}>Descargar</Button>
                  {hasRole(user, "analyst") && (
                    <Button size="sm" variant="ghost" icon={<Send className="size-4" />} onClick={() => setEmailFor(emailFor === r.id ? null : r.id)} aria-expanded={emailFor === r.id}>Enviar</Button>
                  )}
                </div>
                {emailFor === r.id && <EmailForm report={r} onDone={() => setEmailFor(null)} />}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
