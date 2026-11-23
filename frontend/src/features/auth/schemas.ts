import { z } from "zod";

/** La validación del lado del cliente copia las reglas del backend para dar feedback inmediato.
 *  El servidor vuelve a validar todo (nunca confíen en el cliente). */
export const passwordSchema = z
  .string()
  .min(12, "Usa al menos 12 caracteres.")
  .max(128, "Máximo 128 caracteres.")
  .refine((v) => new Set(v).size >= 5, "La contraseña es demasiado predecible.");

export const loginSchema = z.object({
  email: z.string().trim().email("Escribe un correo válido."),
  password: z.string().min(1, "Escribe tu contraseña."),
});

export const registerSchema = z
  .object({
    full_name: z.string().trim().min(2, "Escribe tu nombre.").max(120).regex(/^[^<>{}\\]+$/, "El nombre contiene caracteres no permitidos."),
    email: z.string().trim().email("Escribe un correo válido."),
    password: passwordSchema,
    confirm: z.string(),
    accept_privacy: z.literal(true, { errorMap: () => ({ message: "Debes aceptar la política para crear la cuenta." }) }),
  })
  .refine((d) => d.password === d.confirm, { path: ["confirm"], message: "Las contraseñas no coinciden." });

export const resetSchema = z
  .object({ password: passwordSchema, confirm: z.string() })
  .refine((d) => d.password === d.confirm, { path: ["confirm"], message: "Las contraseñas no coinciden." });

export type FieldErrors = Partial<Record<string, string>>;

export function zodErrors(error: z.ZodError): FieldErrors {
  const out: FieldErrors = {};
  for (const issue of error.issues) {
    const key = String(issue.path[0] ?? "form");
    out[key] ??= issue.message;
  }
  return out;
}
