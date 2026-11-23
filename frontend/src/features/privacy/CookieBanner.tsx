"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Field";
import { useConsent } from "./consent";

export function CookieBanner() {
  const { choice, ready, panelOpen, load, decide, openPanel, closePanel } = useConsent();
  const [functional, setFunctional] = useState(false);
  const [analytics, setAnalytics] = useState(false);

  useEffect(load, [load]);
  useEffect(() => {
    // Nunca viene marcado por defecto: arrancamos de la elección guardada o de "apagado".
    setFunctional(choice?.functional ?? false);
    setAnalytics(choice?.analytics ?? false);
  }, [choice, panelOpen]);

  const visible = ready && (!choice || panelOpen);

  return (
    <AnimatePresence>
      {visible && (
        <motion.section
          role="dialog"
          aria-modal="false"
          aria-labelledby="cookie-title"
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 40 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="fixed inset-x-0 bottom-0 z-[80] max-h-[70svh] overflow-y-auto border-t-2 border-ink bg-field px-5 py-5 shadow-float sm:px-8 [&>*]:mx-auto [&>*]:max-w-5xl"
        >
          <p className="eyebrow mb-2">Privacidad</p>
          <h2 id="cookie-title" className="font-display text-h4 font-medium text-ink">
            Tú decides qué guardamos en tu navegador
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-2">
            Usamos almacenamiento estrictamente necesario para mantener tu sesión segura. Con tu permiso, también recordamos preferencias de la
            interfaz. Hoy no usamos herramientas analíticas ni publicitarias.{" "}
            <Link href="/cookies" className="text-brand link-underline">
              Detalle de cookies
            </Link>{" "}
            ·{" "}
            <Link href="/privacy" className="text-brand link-underline">
              Política de tratamiento de datos
            </Link>
          </p>

          {panelOpen || choice ? (
            <div className="mt-4 flex flex-col gap-3 border-y border-rule py-4">
              <Checkbox label="Necesarias" description="Sesión segura y registro de esta elección. Siempre activas." checked disabled onChange={() => undefined} />
              <Checkbox label="Funcionales" description="Recordar capas del mapa y paneles plegados en este dispositivo." checked={functional} onChange={setFunctional} />
              <Checkbox label="Analíticas" description="Medición de uso agregada. Actualmente no se usa ninguna herramienta." checked={analytics} onChange={setAnalytics} />
            </div>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-2">
            <Button size="sm" onClick={() => decide(true, true)}>
              Aceptar todas
            </Button>
            <Button size="sm" variant="secondary" onClick={() => decide(false, false)}>
              Rechazar opcionales
            </Button>
            {panelOpen || choice ? (
              <Button size="sm" variant="ghost" onClick={() => decide(functional, analytics)}>
                Guardar mi selección
              </Button>
            ) : (
              <Button size="sm" variant="ghost" onClick={openPanel}>
                Configurar preferencias
              </Button>
            )}
            {choice && (
              <Button size="sm" variant="ghost" onClick={closePanel} className="ml-auto">
                Cerrar
              </Button>
            )}
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}
