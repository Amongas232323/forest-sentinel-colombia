import type { ReactNode } from "react";
import { SiteFooter, SiteHeader } from "./PublicChrome";

/** Layout editorial largo para las páginas de políticas y de ayuda. */
export function DocPage({ eyebrow, title, intro, toc, children }: { eyebrow: string; title: ReactNode; intro?: ReactNode; toc?: { id: string; label: string }[]; children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <main id="contenido" className="mx-auto max-w-6xl px-5 pt-14 pb-24 sm:px-8 sm:pt-20">
        <p className="eyebrow mb-4">{eyebrow}</p>
        <h1 className="max-w-3xl font-display display-tight text-[clamp(2.441rem,5vw,3.815rem)] leading-[1] font-medium text-ink">{title}</h1>
        {intro && <div className="mt-6 max-w-2xl text-lg text-ink-2">{intro}</div>}
        <div className="mt-12 grid gap-12 border-t border-ink pt-10 lg:grid-cols-[220px_minmax(0,1fr)]">
          {toc && (
            <nav aria-label="En esta página" className="hidden lg:block">
              <ul className="sticky top-28 flex flex-col gap-2 border-l border-ink pl-4 text-sm">
                {toc.map((t) => (
                  <li key={t.id}>
                    <a href={`#${t.id}`} className="text-ink-2 hover:text-ink">{t.label}</a>
                  </li>
                ))}
              </ul>
            </nav>
          )}
          <div className="prose-fs max-w-3xl">{children}</div>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}

export function DocSection({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-28 border-b border-rule py-8 first:pt-0">
      <h2 className="mb-4 font-display text-h3 font-medium text-ink">{title}</h2>
      <div className="flex flex-col gap-3 leading-relaxed text-ink-2 [&_strong]:text-ink [&_li]:ml-5 [&_li]:list-disc [&_a]:text-brand [&_a]:underline [&_a]:underline-offset-2">{children}</div>
    </section>
  );
}
