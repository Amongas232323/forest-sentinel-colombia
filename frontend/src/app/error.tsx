"use client";

import { Button } from "@/components/ui/Button";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <main id="contenido" className="grid min-h-[100svh] place-items-center px-5 text-center">
      <div className="flex max-w-md flex-col items-center gap-4">
        <p className="eyebrow !text-signal">Algo salió mal</p>
        <h1 className="font-display display-tight text-4xl text-ink">No pudimos mostrar esta vista.</h1>
        <p className="text-ink-2">El error quedó registrado. Puedes intentarlo de nuevo.</p>
        <Button onClick={reset}>Reintentar</Button>
      </div>
    </main>
  );
}
