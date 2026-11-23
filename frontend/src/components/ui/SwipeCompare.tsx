"use client";

import { useId, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Comparación de imágenes antes/después con un slider accesible desde teclado
 * (input range nativo → funcionan las flechas, Home/End y los lectores de pantalla).
 */
export function SwipeCompare({
  before,
  after,
  overlay,
  beforeLabel,
  afterLabel,
  alt,
  overlayOpacity = 1,
  className,
  children,
}: {
  before: string;
  after: string;
  overlay?: string;
  beforeLabel: string;
  afterLabel: string;
  alt: string;
  overlayOpacity?: number;
  className?: string;
  children?: ReactNode;
}) {
  const [pos, setPos] = useState(50);
  const id = useId();
  return (
    <figure className={cn("relative overflow-hidden rounded-[var(--radius-panel)] bg-paper select-none", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={before} alt={`${alt} — ${beforeLabel}`} className="absolute inset-0 size-full object-cover" draggable={false} />
      <div className="absolute inset-0" style={{ clipPath: `inset(0 0 0 ${pos}%)` }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={after} alt={`${alt} — ${afterLabel}`} className="absolute inset-0 size-full object-cover" draggable={false} />
        {overlay && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={overlay} alt="" aria-hidden className="absolute inset-0 size-full object-cover [image-rendering:pixelated]" style={{ opacity: overlayOpacity }} draggable={false} />
        )}
      </div>
      <div aria-hidden className="pointer-events-none absolute inset-y-0 w-px bg-field shadow-[0_0_0_1px_rgb(22_33_27/0.55)]" style={{ left: `${pos}%` }}>
        <div className="absolute top-1/2 left-1/2 grid size-10 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-xs border border-ink bg-field font-mono text-xs text-ink shadow-float">⟷</div>
      </div>
      <span className="absolute top-3 left-3 rounded-xs bg-field px-2 py-1 font-mono text-[0.6875rem] text-ink">{beforeLabel}</span>
      <span className="absolute top-3 right-3 rounded-xs bg-field px-2 py-1 font-mono text-[0.6875rem] text-ink">{afterLabel}</span>
      <label htmlFor={id} className="sr-only">
        Deslizador de comparación: mueve para ver más de la imagen anterior o posterior
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        value={pos}
        onChange={(e) => setPos(Number(e.target.value))}
        className="absolute inset-0 size-full cursor-ew-resize opacity-0"
        aria-valuetext={`${pos}% imagen anterior visible`}
      />
      {children}
    </figure>
  );
}
