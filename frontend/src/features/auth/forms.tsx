"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Checkbox, TextField } from "@/components/ui/Field";
import { toast } from "@/components/ui/Feedback";
import { api, ApiError } from "@/lib/api/client";
import type { TokenResponse } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/store";
import { loginSchema, registerSchema, resetSchema, zodErrors, type FieldErrors } from "./schemas";

function safeNext(next: string | null): string {
  // Solo rutas relativas del mismo sitio (evita open redirects).
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/app";
}

function serverErrors(err: unknown): FieldErrors {
  if (err instanceof ApiError) {
    const fields: FieldErrors = { form: err.message };
    err.details.forEach((d) => (fields[d.field] = d.message));
    return fields;
  }
  return { form: "No hay conexión con el servidor. Inténtalo de nuevo." };
}

function FormError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-xl border border-signal bg-signal-tint px-4 py-3 text-sm text-signal">
      {message}
    </p>
  );
}

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const setSession = useAuth((s) => s.setSession);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    const parsed = loginSchema.safeParse(data);
    if (!parsed.success) return setErrors(zodErrors(parsed.error));
    setLoading(true);
    setErrors({});
    try {
      const res = await api<TokenResponse>("/auth/login", { method: "POST", body: parsed.data, auth: false });
      setSession(res.access_token, res.user);
      router.replace(safeNext(params.get("next")));
    } catch (err) {
      setErrors(serverErrors(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <FormError message={errors.form} />
      <TextField label="Correo electrónico" name="email" type="email" autoComplete="email" required error={errors.email} />
      <TextField label="Contraseña" name="password" type="password" autoComplete="current-password" required error={errors.password} />
      <div className="flex justify-end">
        <Link href="/forgot-password" className="text-sm text-brand link-underline">
          ¿Olvidaste tu contraseña?
        </Link>
      </div>
      <Button type="submit" size="lg" loading={loading}>
        Entrar
      </Button>
    </form>
  );
}

export function RegisterForm() {
  const router = useRouter();
  const [errors, setErrors] = useState<FieldErrors>({});
  const [accept, setAccept] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = { ...Object.fromEntries(new FormData(e.currentTarget)), accept_privacy: accept };
    const parsed = registerSchema.safeParse(data);
    if (!parsed.success) return setErrors(zodErrors(parsed.error));
    setLoading(true);
    setErrors({});
    try {
      const { full_name, email, password, accept_privacy } = parsed.data;
      await api("/auth/register", { method: "POST", body: { full_name, email, password, accept_privacy }, auth: false });
      toast.success("Cuenta creada. Ya puedes iniciar sesión.");
      router.push("/login");
    } catch (err) {
      setErrors(serverErrors(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <FormError message={errors.form} />
      <TextField label="Nombre completo" name="full_name" autoComplete="name" required error={errors.full_name} />
      <TextField label="Correo electrónico" name="email" type="email" autoComplete="email" required error={errors.email} />
      <TextField label="Contraseña" name="password" type="password" autoComplete="new-password" required hint="Mínimo 12 caracteres. Una frase fácil de recordar funciona bien." error={errors.password} />
      <TextField label="Repite la contraseña" name="confirm" type="password" autoComplete="new-password" required error={errors.confirm} />
      <div className="flex flex-col gap-1">
        <Checkbox
          checked={accept}
          onChange={setAccept}
          label={
            <>
              Autorizo el tratamiento de mis datos personales según la{" "}
              <Link href="/privacy" className="text-brand underline" target="_blank">
                política de tratamiento de datos
              </Link>{" "}
              (Ley 1581 de 2012).
            </>
          }
          description="Usamos tu nombre y correo solo para tu cuenta y las notificaciones que actives."
        />
        {errors.accept_privacy && (
          <p role="alert" className="text-xs text-signal">
            ▲ {errors.accept_privacy}
          </p>
        )}
      </div>
      <Button type="submit" size="lg" loading={loading}>
        Crear cuenta
      </Button>
      <p className="text-xs text-ink-2">Las cuentas nuevas tienen rol de observación. Un administrador puede asignar permisos de análisis.</p>
    </form>
  );
}

export function ForgotForm() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email") ?? "").trim();
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError("Escribe un correo válido.");
    setLoading(true);
    try {
      await api("/auth/password/forgot", { method: "POST", body: { email }, auth: false });
      setSent(true);
    } catch (err) {
      setError(serverErrors(err).form);
    } finally {
      setLoading(false);
    }
  }

  if (sent)
    return (
      <div role="status" className="panel panel-ticks p-6">
        <p className="text-ink">Si el correo está registrado, te enviamos un enlace para elegir una nueva contraseña. Revisa también la carpeta de correo no deseado.</p>
        <p className="mt-2 text-sm text-ink-2">El enlace vence en 30 minutos.</p>
      </div>
    );
  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <TextField label="Correo electrónico" name="email" type="email" autoComplete="email" required error={error} />
      <Button type="submit" size="lg" loading={loading}>
        Enviar enlace
      </Button>
    </form>
  );
}

export function ResetForm() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const parsed = resetSchema.safeParse(Object.fromEntries(new FormData(e.currentTarget)));
    if (!parsed.success) return setErrors(zodErrors(parsed.error));
    setLoading(true);
    try {
      await api("/auth/password/reset", { method: "POST", body: { token, password: parsed.data.password }, auth: false });
      toast.success("Contraseña actualizada. Inicia sesión.");
      router.push("/login");
    } catch (err) {
      setErrors(serverErrors(err));
    } finally {
      setLoading(false);
    }
  }

  if (!token) return <FormError message="El enlace no es válido. Solicita uno nuevo." />;
  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <FormError message={errors.form} />
      <TextField label="Nueva contraseña" name="password" type="password" autoComplete="new-password" error={errors.password} hint="Mínimo 12 caracteres." />
      <TextField label="Repite la contraseña" name="confirm" type="password" autoComplete="new-password" error={errors.confirm} />
      <Button type="submit" size="lg" loading={loading}>
        Guardar contraseña
      </Button>
    </form>
  );
}
