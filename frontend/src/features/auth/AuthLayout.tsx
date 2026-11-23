import type { ReactNode } from "react";
import { Logo } from "@/components/brand/Logo";

/** Layout dividido: formulario a la izquierda, un recorte real de Sentinel-2 a la derecha enmarcado como lámina del atlas. */
export function AuthLayout({ eyebrow, title, subtitle, children, footer }: { eyebrow: string; title: ReactNode; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="grid min-h-[100svh] lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
      <main id="contenido" className="flex flex-col px-5 py-8 sm:px-10">
        <Logo />
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-12">
          <p className="eyebrow mb-3">{eyebrow}</p>
          <h1 className="font-display display-tight text-h1 font-medium text-ink">{title}</h1>
          {subtitle && <p className="mt-4 text-ink-2">{subtitle}</p>}
          <div className="mt-10">{children}</div>
          {footer && <div className="mt-8 text-sm text-ink-2">{footer}</div>}
        </div>
      </main>
      <aside className="relative hidden border-l border-ink bg-paper-2 p-10 lg:block" aria-hidden>
        <div className="plate absolute inset-10">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/story/after.jpg" alt="" className="absolute inset-0 size-full object-cover" />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/story/change.png" alt="" className="absolute inset-0 size-full object-cover opacity-90 [image-rendering:pixelated]" />
        <p className="absolute right-0 bottom-0 max-w-xs bg-field px-3 py-2 text-right font-mono text-[0.6875rem] leading-relaxed text-ink-2">
          Guaviare · Sentinel-2 L2A · febrero de 2025
          <br />
          Contiene información modificada de Copernicus Sentinel
        </p>
        </div>
      </aside>
    </div>
  );
}
