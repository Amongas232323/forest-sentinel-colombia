"use client";

import Link from "next/link";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const base =
  // Botones del atlas: una etiqueta impresa, no una pastilla. Al pasar el mouse se oscurece y sube 1px; al presionar baja 1px.
  // La respuesta al presionar es inmediata (transform 120ms ease-out); el color mantiene un ease de 200ms.
  "group relative inline-flex select-none items-center justify-center gap-2 rounded-xs font-semibold [transition:background-color_200ms_var(--ease-plain),border-color_200ms_var(--ease-plain),color_200ms_var(--ease-plain),transform_120ms_ease-out] hover:-translate-y-px active:translate-y-px disabled:pointer-events-none disabled:opacity-45";

const variants: Record<Variant, string> = {
  primary: "bg-brand text-paper hover:bg-brand-2",
  secondary: "border border-ink bg-transparent text-ink hover:bg-paper-3",
  ghost: "text-ink-2 hover:bg-paper-2 hover:text-ink",
  danger: "border border-signal bg-transparent text-signal hover:bg-signal-tint",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-3.5 text-sm min-w-9",
  md: "h-11 px-5 text-[0.9375rem] min-w-11",
  lg: "h-13 px-6 text-base",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button ref={ref} type={type} className={cn(base, variants[variant], sizes[size], className)} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden /> : icon}
      {children}
    </button>
  );
});

export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  className,
  children,
  icon,
}: {
  href: string;
  variant?: Variant;
  size?: Size;
  className?: string;
  children: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <Link href={href} className={cn(base, variants[variant], sizes[size], className)}>
      {icon}
      {children}
    </Link>
  );
}
