import Link from "next/link";
import { cn } from "@/lib/cn";

/** Marca: la mira de un topógrafo sobre una hoja — un punto fijo de observación sobre el bosque. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("size-9", className)} aria-hidden>
      <circle cx="20" cy="20" r="14" fill="none" stroke="var(--color-ink)" strokeWidth="1.3" />
      <path d="M20 1v8M20 31v8M1 20h8M31 20h8" stroke="var(--color-ink)" strokeWidth="1.3" />
      <path d="M20 10.5c4.6 3.4 5.9 8.8 0 18.5-5.9-9.7-4.6-15.1 0-18.5z" fill="var(--color-brand)" />
      <path d="M20 14v13" stroke="var(--color-paper)" strokeWidth=".9" />
    </svg>
  );
}

export function Logo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("group flex items-center gap-2.5", className)} aria-label="Forest Sentinel, inicio">
      <LogoMark />
      <span className="flex flex-col leading-none">
        <span className="font-display text-[1.375rem] font-semibold tracking-[-0.01em] whitespace-nowrap text-ink transition-colors duration-200 group-hover:text-brand">Forest Sentinel</span>
        <span className="mt-1 hidden text-[0.6875rem] font-semibold tracking-[0.08em] text-ink-2 sm:block">VIGILANCIA FORESTAL</span>
      </span>
    </Link>
  );
}
