import type { Metadata } from "next";
import Link from "next/link";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { ForgotForm } from "@/features/auth/forms";

export const metadata: Metadata = { title: "Recuperar contraseña" };

export default function ForgotPage() {
  return (
    <AuthLayout
      eyebrow="Recuperación"
      title={<>¿Olvidaste tu <span>contraseña?</span></>}
      subtitle="Escribe tu correo y te enviaremos un enlace de un solo uso."
      footer={<Link href="/login" className="text-brand link-underline">Volver a iniciar sesión</Link>}
    >
      <ForgotForm />
    </AuthLayout>
  );
}
