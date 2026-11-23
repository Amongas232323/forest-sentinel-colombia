"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { ButtonLink } from "@/components/ui/Button";
import { Logo } from "@/components/brand/Logo";
import { useConsent } from "@/features/privacy/consent";
import { useAuth } from "@/lib/auth/store";

export function SiteHeader() {
  const status = useAuth((s) => s.status);
  // Una cabecera tipo periódico, no una barra de vidrio flotante: papel sólido con una línea de tinta debajo.
  return (
    <header className="sticky top-0 z-50 border-b border-ink bg-paper">
      <nav aria-label="Principal" className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-5 sm:h-20 sm:px-8">
        <Logo />
        <ul className="hidden items-center gap-8 text-sm text-ink md:flex">
          <li><a href="#territorios" className="link-underline">Territorios</a></li>
          <li><a href="#como-funciona" className="link-underline">Cómo funciona</a></li>
          <li><Link href="/help" className="link-underline">Metodología</Link></li>
        </ul>
        {status === "authenticated" ? (
          <ButtonLink href="/app" size="sm" className="whitespace-nowrap" icon={<ArrowRight className="size-4 sm:hidden" aria-hidden />}>
            {/* En celulares la flecha hace el trabajo; la etiqueta queda como nombre accesible del link. */}
            <span className="sr-only sm:not-sr-only">Ir al centro de operaciones</span>
          </ButtonLink>
        ) : (
          <div className="flex items-center gap-1">
            <Link href="/login" className="hidden min-h-11 items-center px-3 text-sm text-ink link-underline sm:flex">Iniciar sesión</Link>
            <ButtonLink href="/register" size="sm" className="whitespace-nowrap">Crear cuenta</ButtonLink>
          </div>
        )}
      </nav>
    </header>
  );
}

export function SiteFooter() {
  const openPanel = useConsent((s) => s.openPanel);
  return (
    <footer className="relative border-t-2 border-ink bg-paper-2">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="flex flex-col gap-4">
          <Logo />
          <p className="max-w-sm text-sm leading-relaxed text-ink-2">
            Detección temprana de cambios en la cobertura forestal en Guaviare, la Sierra Nevada de Santa Marta, Cundinamarca y Amazonas.
            Cada hallazgo es una señal para revisar, no una conclusión.
          </p>
        </div>
        <div className="flex flex-col gap-2 text-sm">
          <p className="eyebrow mb-2 border-b border-rule pb-2">Plataforma</p>
          <Link href="/login" className="flex min-h-9 items-center text-ink-2 hover:text-ink link-underline">Iniciar sesión</Link>
          <Link href="/register" className="flex min-h-9 items-center text-ink-2 hover:text-ink link-underline">Crear cuenta</Link>
          <Link href="/help" className="flex min-h-9 items-center text-ink-2 hover:text-ink link-underline">Metodología y ayuda</Link>
        </div>
        <div className="flex flex-col gap-2 text-sm">
          <p className="eyebrow mb-2 border-b border-rule pb-2">Legal</p>
          <Link href="/privacy" className="flex min-h-9 items-center text-ink-2 hover:text-ink link-underline">Tratamiento de datos personales</Link>
          <Link href="/cookies" className="flex min-h-9 items-center text-ink-2 hover:text-ink link-underline">Cookies</Link>
          <button onClick={openPanel} className="flex min-h-9 items-center text-left text-ink-2 hover:text-ink link-underline">Cambiar preferencias de cookies</button>
        </div>
      </div>
      <div className="mx-auto max-w-7xl border-t border-rule px-5 py-6 font-mono text-[0.6875rem] leading-relaxed text-ink-2 sm:px-8">
        Contiene información modificada de Copernicus Sentinel · Texturas del planeta: NASA Visible Earth (dominio público) · Límites territoriales © OpenStreetMap contributors (ODbL)
      </div>
    </footer>
  );
}
