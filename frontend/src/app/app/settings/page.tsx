"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { toast } from "@/components/ui/Feedback";
import { passwordSchema } from "@/features/auth/schemas";
import { useConsent } from "@/features/privacy/consent";
import { api, ApiError } from "@/lib/api/client";
import { useSources } from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth/store";
import { ROLE, fmtDate } from "@/lib/format";

export default function SettingsPage() {
  const { user, clear } = useAuth();
  const router = useRouter();
  const openPanel = useConsent((s) => s.openPanel);
  const sources = useSources();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  async function changePassword(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const current = String(fd.get("current") ?? "");
    const next = String(fd.get("next") ?? "");
    const check = passwordSchema.safeParse(next);
    if (!check.success) return setErrors({ next: check.error.issues[0]!.message });
    if (next !== fd.get("confirm")) return setErrors({ confirm: "Las contraseñas no coinciden." });
    setLoading(true);
    try {
      await api("/auth/password/change", { method: "POST", body: { current_password: current, new_password: next } });
      toast.success("Contraseña actualizada. Inicia sesión de nuevo.");
      clear();
      router.replace("/login");
    } catch (err) {
      setErrors({ current: err instanceof ApiError ? err.message : "No se pudo cambiar." });
    } finally {
      setLoading(false);
    }
  }

  async function logoutAll() {
    await api("/auth/logout-all", { method: "POST" }).catch(() => undefined);
    clear();
    router.replace("/login");
  }

  if (!user) return null;
  return (
    <>
      <PageHeader eyebrow="Configuración" title={<>Tu cuenta y <span>tu privacidad.</span></>} />
      <div className="grid grid-cols-1 gap-6 px-5 pb-12 sm:px-8 xl:grid-cols-2">
        <section className="panel flex flex-col gap-3 p-5" aria-labelledby="profile-title">
          <h2 id="profile-title" className="font-display text-2xl text-ink">Perfil</h2>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-ink-2">Nombre</dt><dd className="text-ink">{user.full_name}</dd></div>
            <div><dt className="text-ink-2">Correo</dt><dd className="text-ink">{user.email}</dd></div>
            <div><dt className="text-ink-2">Rol</dt><dd className="text-ink">{ROLE[user.role]}</dd></div>
            <div><dt className="text-ink-2">Cuenta creada</dt><dd className="text-ink">{fmtDate(user.created_at)}</dd></div>
          </dl>
          <p className="text-xs text-ink-2">Para corregir o eliminar tus datos personales, escribe al canal indicado en la política de tratamiento de datos.</p>
        </section>

        <form onSubmit={changePassword} className="panel flex flex-col gap-4 p-5" aria-labelledby="pw-title" noValidate>
          <h2 id="pw-title" className="font-display text-2xl text-ink">Cambiar contraseña</h2>
          <TextField label="Contraseña actual" name="current" type="password" autoComplete="current-password" error={errors.current} />
          <TextField label="Nueva contraseña" name="next" type="password" autoComplete="new-password" hint="Mínimo 12 caracteres." error={errors.next} />
          <TextField label="Repite la nueva contraseña" name="confirm" type="password" autoComplete="new-password" error={errors.confirm} />
          <Button type="submit" loading={loading} className="self-start">Actualizar contraseña</Button>
        </form>

        <section className="panel flex flex-col gap-3 p-5" aria-labelledby="sec-title">
          <h2 id="sec-title" className="font-display text-2xl text-ink">Sesiones</h2>
          <p className="text-sm text-ink-2">Si usaste tu cuenta en un equipo compartido o perdiste un dispositivo, cierra todas las sesiones.</p>
          <Button variant="danger" onClick={logoutAll} className="self-start">Cerrar todas las sesiones</Button>
        </section>

        <section className="panel flex flex-col gap-3 p-5" aria-labelledby="cookie-title">
          <h2 id="cookie-title" className="font-display text-2xl text-ink">Cookies y almacenamiento</h2>
          <p className="text-sm text-ink-2">Revisa o cambia lo que guardamos en este navegador.</p>
          <Button variant="secondary" onClick={openPanel} className="self-start">Cambiar preferencias</Button>
        </section>

        <section className="panel flex flex-col gap-3 p-5 xl:col-span-2" aria-labelledby="sources-title">
          <h2 id="sources-title" className="font-display text-2xl text-ink">Fuentes satelitales</h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {sources.data?.map((s) => (
              <li key={s.slug} className="rounded-xl border border-rule bg-field p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold text-ink">{s.name}</p>
                  <span className={`rounded-xs border px-1.5 py-0.5 font-mono text-[0.6875rem] ${s.enabled ? "border-brand text-brand" : "border-rule-strong text-ink-2"}`}>{s.enabled ? "ACTIVA" : "NO INTEGRADA"}</span>
                </div>
                <p className="mt-1 text-xs text-ink-2">{s.provider}</p>
                <p className="mt-2 text-xs text-ink-2">{s.notes}</p>
                <p className="mt-2 font-mono text-[0.6875rem] text-ink-2">{s.license}{s.requires_credentials ? " · requiere credenciales" : ""}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
