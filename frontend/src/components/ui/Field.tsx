"use client";

import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

const control =
  // Campo sobre papel: un fondo más claro con borde de 3:1 (WCAG 1.4.11); con foco la línea se engrosa en azul agua.
  "w-full rounded-xs border bg-field px-3.5 text-ink placeholder:text-ink-3 transition-[border-color,box-shadow] duration-150 focus:border-water focus:outline-none focus:shadow-[inset_0_0_0_1px_var(--color-water)] disabled:opacity-50";

interface FieldShellProps {
  label: string;
  hint?: ReactNode;
  error?: string;
  children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode;
  className?: string;
}

/** Etiqueta + control + pista + error, conectados con aria-describedby / aria-invalid. */
export function FieldShell({ label, hint, error, children, className }: FieldShellProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium text-ink">
        {label}
      </label>
      {children({ id, describedBy, invalid: !!error })}
      {hint && !error && (
        <p id={hintId} className="text-xs text-ink-2">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="flex items-center gap-1.5 text-xs text-signal">
          <span aria-hidden>▲</span> {error}
        </p>
      )}
    </div>
  );
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: ReactNode; error?: string };

export const TextField = forwardRef<HTMLInputElement, InputProps>(function TextField({ label, hint, error, className, ...rest }, ref) {
  return (
    <FieldShell label={label} hint={hint} error={error} className={className}>
      {({ id, describedBy, invalid }) => (
        <input
          ref={ref}
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={cn(control, "h-12", invalid ? "border-signal" : "border-rule-strong")}
          {...rest}
        />
      )}
    </FieldShell>
  );
});

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & { label: string; hint?: ReactNode; error?: string };

export const SelectField = forwardRef<HTMLSelectElement, SelectProps>(function SelectField({ label, hint, error, className, children, ...rest }, ref) {
  return (
    <FieldShell label={label} hint={hint} error={error} className={className}>
      {({ id, describedBy, invalid }) => (
        <select ref={ref} id={id} aria-describedby={describedBy} aria-invalid={invalid || undefined} className={cn(control, "select-chevron h-12 appearance-none pr-10", invalid ? "border-signal" : "border-rule-strong")} {...rest}>
          {children}
        </select>
      )}
    </FieldShell>
  );
});

type AreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; hint?: ReactNode; error?: string };

export const TextAreaField = forwardRef<HTMLTextAreaElement, AreaProps>(function TextAreaField({ label, hint, error, className, ...rest }, ref) {
  return (
    <FieldShell label={label} hint={hint} error={error} className={className}>
      {({ id, describedBy, invalid }) => (
        <textarea ref={ref} id={id} aria-describedby={describedBy} aria-invalid={invalid || undefined} className={cn(control, "min-h-28 py-3", invalid ? "border-signal" : "border-rule-strong")} {...rest} />
      )}
    </FieldShell>
  );
});

export function Checkbox({ label, description, checked, onChange, disabled, id: idProp }: { label: ReactNode; description?: ReactNode; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; id?: string }) {
  const auto = useId();
  const id = idProp ?? auto;
  return (
    <label htmlFor={id} className={cn("flex cursor-pointer items-start gap-3 rounded-xl p-2 -m-2 hover:bg-paper-2", disabled && "cursor-not-allowed opacity-60")}>
      <input id={id} type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span
        aria-hidden
        className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border border-rule-strong bg-paper transition-colors peer-checked:border-brand peer-checked:bg-brand peer-focus-visible:ring-2 peer-focus-visible:ring-water peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-paper [&>svg]:opacity-0 peer-checked:[&>svg]:opacity-100"
      >
        <svg viewBox="0 0 12 12" className="size-3 text-paper" fill="none" stroke="currentColor" strokeWidth="2.2">
          <path d="M2.5 6.5l2.2 2.2L9.5 3.5" />
        </svg>
      </span>
      <span className="flex flex-col">
        <span className="text-sm text-ink">{label}</span>
        {description && <span className="text-xs text-ink-2">{description}</span>}
      </span>
    </label>
  );
}
