import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { ResetForm } from "@/features/auth/forms";

export const metadata: Metadata = { title: "Nueva contraseña" };

export default function ResetPage() {
  return (
    <AuthLayout eyebrow="Recuperación" title={<>Elige una <span>nueva contraseña.</span></>} subtitle="Al guardarla se cerrarán tus sesiones abiertas en otros dispositivos.">
      <Suspense>
        <ResetForm />
      </Suspense>
    </AuthLayout>
  );
}
