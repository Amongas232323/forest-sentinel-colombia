"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button } from "@/components/ui/Button";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { api, ApiError } from "@/lib/api/client";

function Unsubscribe() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  // Pide un clic explícito: los escáneres de correo que precargan links no deberían desuscribir a nadie.
  async function confirm() {
    setState("loading");
    try {
      const res = await api<{ message: string }>(`/notifications/unsubscribe?token=${encodeURIComponent(token)}`, { method: "POST", auth: false });
      setMessage(res.message);
      setState("done");
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "No pudimos procesar la solicitud.");
      setState("error");
    }
  }
  if (state === "done" || state === "error")
    return (
      <div role="status" className="panel panel-ticks p-6">
        <p className="text-ink">{message}</p>
        <Link href="/app/notifications" className="mt-4 inline-block text-sm text-brand link-underline">Gestionar notificaciones</Link>
      </div>
    );
  return (
    <Button size="lg" onClick={confirm} loading={state === "loading"} disabled={!token}>
      Sí, dejar de recibir correos
    </Button>
  );
}

export default function UnsubscribePage() {
  return (
    <AuthLayout eyebrow="Notificaciones" title={<>¿Dejar de recibir <span>alertas?</span></>} subtitle="Puedes volver a activarlas cuando quieras desde tu cuenta.">
      <Suspense>
        <Unsubscribe />
      </Suspense>
    </AuthLayout>
  );
}
