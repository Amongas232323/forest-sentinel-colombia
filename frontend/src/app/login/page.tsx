import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { LoginForm } from "@/features/auth/forms";

export const metadata: Metadata = { title: "Iniciar sesión" };

export default function LoginPage() {
  return (
    <AuthLayout
      eyebrow="Acceso"
      title={<>Bienvenido de <span>vuelta.</span></>}
      subtitle="Entra al centro de operaciones para revisar lo que cambió en tus territorios."
      footer={<>¿No tienes cuenta? <Link href="/register" className="text-brand link-underline">Créala aquí</Link></>}
    >
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthLayout>
  );
}
