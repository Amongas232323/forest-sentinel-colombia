import type { Metadata } from "next";
import Link from "next/link";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { RegisterForm } from "@/features/auth/forms";

export const metadata: Metadata = { title: "Crear cuenta" };

export default function RegisterPage() {
  return (
    <AuthLayout
      eyebrow="Nueva cuenta"
      title={<>Únete a la <span>vigilancia.</span></>}
      subtitle="Consulta alertas, explora los territorios y recibe avisos cuando algo cambie."
      footer={<>¿Ya tienes cuenta? <Link href="/login" className="text-brand link-underline">Inicia sesión</Link></>}
    >
      <RegisterForm />
    </AuthLayout>
  );
}
