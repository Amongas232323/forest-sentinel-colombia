"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingBlock, toast } from "@/components/ui/Feedback";
import { ApiError } from "@/lib/api/client";
import { useAudit, useUpdateUser, useUsers } from "@/lib/api/hooks";
import type { Role } from "@/lib/api/types";
import { hasRole, useAuth } from "@/lib/auth/store";
import { cn } from "@/lib/cn";
import { ROLE, fmtDateTime, fmtRelative } from "@/lib/format";

const ROLE_HELP: Record<Role, string> = {
  observer: "Consulta alertas, mapas e informes.",
  analyst: "Además crea zonas, lanza análisis y revisa alertas.",
  admin: "Además gestiona usuarios y consulta la auditoría.",
};

function UsersTab() {
  const me = useAuth((s) => s.user);
  const users = useUsers();
  const update = useUpdateUser();
  async function change(id: string, body: { role?: Role; is_active?: boolean }) {
    try {
      await update.mutateAsync({ id, ...body });
      toast.success("Usuario actualizado.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo actualizar.");
    }
  }
  if (users.isLoading) return <LoadingBlock rows={4} />;
  if (users.isError) return <ErrorState message="No pudimos cargar los usuarios." />;
  return (
    <ul className="flex flex-col gap-3">
      {users.data?.map((u) => (
        <li key={u.id} className={cn("panel flex flex-col gap-4 p-4 sm:flex-row sm:items-center", !u.is_active && "opacity-60")}>
          <div className="grid size-10 shrink-0 place-items-center rounded-xs border border-ink font-display text-lg font-semibold" aria-hidden>{u.full_name[0]?.toUpperCase()}</div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold text-ink">{u.full_name} {u.id === me?.id && <span className="text-xs text-brand">(tú)</span>}</p>
            <p className="truncate text-xs text-ink-2">{u.email} · último acceso {fmtRelative(u.last_login_at)}</p>
          </div>
          <label className="flex flex-col gap-1 text-xs text-ink-2">
            Rol
            <select value={u.role} disabled={u.id === me?.id} onChange={(e) => change(u.id, { role: e.target.value as Role })} className="h-10 rounded-xl border border-rule bg-field px-3 text-sm text-ink" title={ROLE_HELP[u.role]}>
              {(Object.keys(ROLE_HELP) as Role[]).map((r) => <option key={r} value={r}>{ROLE[r]}</option>)}
            </select>
          </label>
          <Button size="sm" variant={u.is_active ? "danger" : "secondary"} disabled={u.id === me?.id} onClick={() => change(u.id, { is_active: !u.is_active })}>
            {u.is_active ? "Desactivar" : "Reactivar"}
          </Button>
        </li>
      ))}
    </ul>
  );
}

function AuditTab() {
  const [page, setPage] = useState(1);
  const audit = useAudit(page);
  if (audit.isLoading) return <LoadingBlock rows={5} />;
  if (!audit.data?.items.length) return <EmptyState title="Sin registros" description="Aquí aparecerán inicios de sesión, cambios de rol, revisiones y otras acciones sensibles." />;
  return (
    <>
      <ul className="flex flex-col divide-y divide-rule rounded-2xl border border-rule bg-paper-2">
        {audit.data.items.map((a) => (
          <li key={a.id} className="grid gap-1 px-4 py-3 text-sm sm:grid-cols-[180px_220px_1fr]">
            <span className="font-mono text-[0.6875rem] text-ink-2">{fmtDateTime(a.created_at)}</span>
            <span className="font-mono text-xs text-brand">{a.action}</span>
            <span className="truncate font-mono text-[0.6875rem] text-ink-2">{a.resource_type ? `${a.resource_type}:${a.resource_id?.slice(0, 8)}` : ""} {Object.keys(a.details).length ? JSON.stringify(a.details) : ""}</span>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex justify-center gap-2">
        <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</Button>
        <Button size="sm" variant="ghost" disabled={page * audit.data.page_size >= audit.data.total} onClick={() => setPage((p) => p + 1)}>Siguiente</Button>
      </div>
    </>
  );
}

export default function UsersPage() {
  const user = useAuth((s) => s.user);
  const [tab, setTab] = useState<"users" | "audit">("users");
  if (!hasRole(user, "admin")) return <div className="p-8"><ErrorState message="Esta sección es solo para administración." /></div>;
  return (
    <>
      <PageHeader eyebrow="Administración" title={<>Personas y <span>permisos.</span></>} description="Los permisos se verifican en el servidor en cada solicitud; esta pantalla solo los gestiona." />
      <div className="px-5 pb-12 sm:px-8">
        <div role="tablist" aria-label="Secciones de administración" className="mb-6 inline-flex border border-ink">
          {([["users", "Usuarios"], ["audit", "Auditoría"]] as const).map(([k, l]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={cn("min-h-10 px-5 py-2 text-sm", tab === k ? "bg-ink text-paper" : "text-ink hover:bg-paper-3")}>{l}</button>
          ))}
        </div>
        {tab === "users" ? <UsersTab /> : <AuditTab />}
      </div>
    </>
  );
}
