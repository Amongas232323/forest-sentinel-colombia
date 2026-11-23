"use client";

import { Button } from "@/components/ui/Button";
import { DocPage, DocSection } from "@/components/layout/DocPage";
import { CONSENT_VERSION, useConsent } from "@/features/privacy/consent";
import { fmtDateTime } from "@/lib/format";

const ROWS = [
  ["fs_refresh", "Necesaria", "Cookie httpOnly que mantiene tu sesión de forma segura (rotación en cada uso).", "14 días"],
  ["fs_consent", "Necesaria", "Almacenamiento local con tu elección sobre cookies y la versión de la política.", "Hasta que cambie la política"],
  ["fs_ui", "Funcional", "Almacenamiento local con preferencias de la interfaz, como las capas del mapa.", "Hasta que lo borres"],
];

export default function CookiesPage() {
  const { choice, openPanel } = useConsent();
  return (
    <DocPage eyebrow={`Cookies · versión ${CONSENT_VERSION}`} title={<>Lo que guardamos <span>en tu navegador.</span></>} intro={<p>Pocas cosas, todas explicadas. Hoy no usamos cookies analíticas ni publicitarias.</p>}>
      <DocSection id="tu-eleccion" title="Tu elección actual">
        {choice ? (
          <p>
            Funcionales: <strong>{choice.functional ? "permitidas" : "rechazadas"}</strong> · Analíticas: <strong>{choice.analytics ? "permitidas" : "rechazadas"}</strong> · decidido el {fmtDateTime(choice.decided_at)}.
          </p>
        ) : (
          <p>Aún no has elegido. Solo usamos lo estrictamente necesario.</p>
        )}
        <Button variant="secondary" onClick={openPanel} className="self-start">Cambiar preferencias</Button>
      </DocSection>
      <DocSection id="inventario" title="Inventario">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="font-mono text-[0.6875rem] tracking-wider text-brand uppercase">
              <tr><th className="py-2 pr-4">Nombre</th><th className="py-2 pr-4">Categoría</th><th className="py-2 pr-4">Para qué</th><th className="py-2">Duración</th></tr>
            </thead>
            <tbody>
              {ROWS.map(([n, c, p, d]) => (
                <tr key={n} className="border-t border-rule align-top">
                  <td className="py-3 pr-4 font-mono text-ink">{n}</td><td className="py-3 pr-4">{c}</td><td className="py-3 pr-4">{p}</td><td className="py-3">{d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DocSection>
      <DocSection id="categorias" title="Categorías">
        <ul>
          <li><strong>Necesarias:</strong> sin ellas no puedes iniciar sesión de forma segura. No requieren consentimiento y no se usan para otra cosa.</li>
          <li><strong>Funcionales:</strong> recuerdan preferencias de la interfaz. Solo se escriben si las aceptas.</li>
          <li><strong>Analíticas:</strong> la categoría existe para que cualquier herramienta futura quede bloqueada hasta que la autorices. Actualmente no hay ninguna.</li>
        </ul>
        <p>Los mapas descargan teselas de servicios abiertos (OpenFreeMap, EOX, AWS); estas descargas no usan cookies de terceros.</p>
      </DocSection>
    </DocPage>
  );
}
