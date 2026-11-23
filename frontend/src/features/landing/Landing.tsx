"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { motion } from "framer-motion";
import { ArrowDown, ArrowRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { SiteFooter, SiteHeader } from "@/components/layout/PublicChrome";
import { SeverityBadge } from "@/components/ui/Badges";
import { TERRITORY_NAMES } from "@/features/globe/Globe";
import { MapView, type MLMap } from "@/features/map/MapView";
import { TerritorySilhouette } from "@/features/regions/TerritorySilhouette";
import type { GeoJSONGeometry } from "@/lib/api/types";
import { useReducedMotion } from "@/lib/device";
import { fmtCoord, fmtDate, fmtNumber } from "@/lib/format";
import story from "./story-data.json";

interface TerritoryInfo {
  slug: string;
  name: string;
  description: string;
  area_km2: number;
  geometry: GeoJSONGeometry;
}

function useStaticTerritories(): TerritoryInfo[] {
  const [items, setItems] = useState<TerritoryInfo[]>([]);
  useEffect(() => {
    fetch("/data/territories.geojson")
      .then((r) => r.json())
      .then((fc: { features: { properties: Omit<TerritoryInfo, "geometry">; geometry: GeoJSONGeometry }[] }) => setItems(fc.features.map((f) => ({ ...f.properties, geometry: f.geometry }))))
      .catch(() => setItems([]));
  }, []);
  return items;
}

/** Hoja principal: Colombia sobre el mapa base de papel, los cuatro territorios en tinta, el hallazgo real como punto de señal. */
function LocatorMap({ territories }: { territories: TerritoryInfo[] }) {
  const mapRef = useRef<MLMap | null>(null);
  const [lon, lat] = story.finding.centroid as [number, number];

  function draw(map: MLMap) {
    if (!territories.length || map.getSource("territories")) return;
    map.addSource("territories", {
      type: "geojson",
      data: { type: "FeatureCollection", features: territories.map((t) => ({ type: "Feature", properties: { name: TERRITORY_NAMES[t.slug] ?? t.name }, geometry: t.geometry })) },
    });
    map.addLayer({ id: "t-fill", type: "fill", source: "territories", paint: { "fill-color": "#1F4D36", "fill-opacity": 0.14 } });
    map.addLayer({ id: "t-line", type: "line", source: "territories", paint: { "line-color": "#16211B", "line-width": 1.4 } });
    map.addLayer({
      id: "t-label",
      type: "symbol",
      source: "territories",
      layout: { "text-field": ["get", "name"], "text-font": ["Noto Sans Bold"], "text-size": 12, "text-transform": "uppercase", "text-letter-spacing": 0.08, "text-offset": [0, 0], "text-max-width": 9 },
      paint: { "text-color": "#16211B", "text-halo-color": "#F4F2EB", "text-halo-width": 2 },
    });
    map.addSource("finding", { type: "geojson", data: { type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [lon, lat] } } });
    map.addLayer({ id: "finding", type: "circle", source: "finding", paint: { "circle-color": "#A82820", "circle-radius": 5, "circle-stroke-color": "#FBFAF6", "circle-stroke-width": 2 } });
  }

  useEffect(() => {
    if (mapRef.current?.isStyleLoaded()) draw(mapRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [territories]);

  return (
    <MapView
      className="absolute inset-0"
      interactive={false}
      label="Mapa de Colombia con los cuatro territorios vigilados"
      options={{ fitBoundsOptions: { padding: 24 } }}
      onLoad={(map) => {
        mapRef.current = map;
        draw(map);
      }}
    />
  );
}

const enter = (delay: number) => ({ initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { delay, duration: 0.5, ease: [0.2, 0, 0, 1] as const } });

export function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const territories = useStaticTerritories();

  // El único momento ligado al scroll en toda la página: la lámina de evidencia pasa de "antes" a "después"
  // y luego a la máscara de cambio, dentro de su propia sección fija. Todo lo demás se queda quieto.
  useEffect(() => {
    if (reduced) return;
    gsap.registerPlugin(ScrollTrigger);
    const ctx = gsap.context(() => {
      const ev = document.querySelector<HTMLElement>("[data-evidence]");
      if (ev) {
        ScrollTrigger.create({
          trigger: "[data-chapter='evidencia']",
          start: "top top",
          end: "bottom bottom",
          scrub: 0.6,
          onUpdate: (self) => {
            const p = self.progress;
            ev.style.setProperty("--reveal", String(Math.min(1, p / 0.45)));
            ev.style.setProperty("--mask", String(Math.max(0, Math.min(1, (p - 0.45) / 0.25))));
            ev.style.setProperty("--metrics", String(Math.max(0, Math.min(1, (p - 0.65) / 0.2))));
          },
        });
      }
    }, root);
    return () => ctx.revert();
  }, [reduced]);

  const obsDate = fmtDate(story.observation.last);
  const refDate = fmtDate(story.reference.last);
  const [lon, lat] = story.finding.centroid as [number, number];

  return (
    <div ref={root} className="relative">
      <SiteHeader />

      <main id="contenido">
        {/* ── Hero: la propuesta a la izquierda, el territorio a la derecha ── */}
        <section data-enter className="border-b border-ink">
          <div className="mx-auto grid min-h-[calc(100svh-5rem)] max-w-7xl grid-cols-1 gap-x-12 gap-y-10 px-5 py-12 sm:px-8 lg:grid-cols-12 lg:items-center lg:py-16">
            <div className="lg:col-span-7">
              <motion.p {...enter(0)} className="eyebrow mb-6">
                ● Observatorio forestal · Sentinel-2 · Colombia
              </motion.p>
              <h1 className="font-display text-[clamp(2.9rem,6.2vw,5.6rem)] leading-[0.96] font-medium tracking-[-0.02em] text-ink">
                <motion.span className="block" {...enter(0.05)}>
                  Ver el bosque
                </motion.span>
                <motion.span className="block" {...enter(0.1)}>
                  antes de perderlo.
                </motion.span>
              </h1>
              <motion.p {...enter(0.18)} className="mt-8 max-w-xl text-lead text-ink-2">
                Forest Sentinel compara imágenes satelitales de distintas fechas, señala dónde el bosque cambió y lo explica en palabras
                sencillas, para que alguien pueda revisarlo a tiempo.
              </motion.p>
              <motion.div {...enter(0.24)} className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-3">
                <ButtonLink href="/app" size="lg" icon={<ArrowRight className="size-5" />}>
                  Entrar al centro de operaciones
                </ButtonLink>
                <a href="#territorios" className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-ink link-underline">
                  <ArrowDown className="size-4" /> Ver cómo funciona
                </a>
              </motion.div>
            </div>
            <motion.div {...enter(0.12)} className="plate relative aspect-[4/5] w-full sm:aspect-[5/4] lg:col-span-5 lg:aspect-[4/5] lg:max-h-[calc(100svh-9rem)]">
              <LocatorMap territories={territories} />
            </motion.div>
          </div>
        </section>

        {/* ── 01 Territorios: cuatro contornos, uno al lado del otro, cada uno a su escala ── */}
        <section id="territorios" className="scroll-mt-20 border-b border-ink">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:py-28">
            <div className="grid gap-8 lg:grid-cols-12">
              <p className="eyebrow lg:col-span-3">01 · Dónde vigilamos</p>
              <div className="lg:col-span-9">
                <h2 className="max-w-3xl font-display text-[clamp(2.441rem,4.6vw,3.815rem)] leading-[1.02] font-medium text-ink">Cuatro territorios, cuatro bosques distintos.</h2>
                <p className="mt-6 max-w-2xl text-lead text-ink-2">
                  Desde la selva amazónica hasta el macizo costero más alto del mundo. Los límites provienen de fuentes abiertas y cada zona de
                  vigilancia debe estar dentro de ellos.
                </p>
              </div>
            </div>
            <ul className="mt-14 grid gap-px border-y border-ink bg-rule sm:grid-cols-2 lg:grid-cols-4">
              {territories.map((t, i) => (
                <li key={t.slug} className="flex flex-col gap-4 bg-paper p-5 sm:p-6">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-mono text-xs text-ink-2">0{i + 1}</span>
                    <span className="font-mono text-xs text-ink-2">{fmtNumber(t.area_km2)} km²</span>
                  </div>
                  <TerritorySilhouette geometry={t.geometry} className="mx-auto h-36 w-full max-w-[12rem]" />
                  <h3 className="font-display text-h4 font-medium text-ink">{TERRITORY_NAMES[t.slug] ?? t.name}</h3>
                  <p className="text-sm leading-relaxed text-ink-2">{t.description}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── 02 Satélite: tres cifras presentadas como ficha técnica ── */}
        <section className="border-b border-ink">
          <div className="mx-auto grid max-w-7xl gap-8 px-5 py-20 sm:px-8 lg:grid-cols-12 lg:py-28">
            <p className="eyebrow lg:col-span-3">02 · Los ojos en órbita</p>
            <div className="lg:col-span-9">
              <h2 className="max-w-3xl font-display text-[clamp(2.441rem,4.6vw,3.815rem)] leading-[1.02] font-medium text-ink">Un satélite pasa sobre cada punto cada pocos días.</h2>
              <p className="mt-6 max-w-2xl text-lead text-ink-2">
                Usamos Sentinel-2, la misión abierta del programa europeo Copernicus. Sus satélites observan la Tierra en luz visible e
                infrarroja, la que revela cómo de sana está la vegetación.
              </p>
              <dl className="mt-14 grid border-t border-ink sm:grid-cols-3">
                {[
                  ["10 m", "tamaño de cada píxel en las bandas visibles e infrarrojo cercano"],
                  ["~5 días", "entre pasadas sobre el ecuador con la constelación completa"],
                  ["13", "bandas espectrales, de lo visible al infrarrojo de onda corta"],
                ].map(([k, v]) => (
                  <div key={k} className="border-b border-rule py-6 sm:border-b-0 sm:border-l sm:px-6 sm:first:border-l-0 sm:first:pl-0">
                    <dt className="font-display text-[clamp(3.052rem,5vw,4.768rem)] leading-none font-medium text-ink">{k}</dt>
                    <dd className="mt-3 max-w-[28ch] text-sm leading-snug text-ink-2">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        {/* ── 03 Problema: la única franja oscura de la página, solo texto ── */}
        <section className="bg-ink text-paper">
          <div className="mx-auto grid min-h-[70svh] max-w-7xl content-center gap-8 px-5 py-24 sm:px-8 lg:grid-cols-12">
            <p className="eyebrow !text-paper/80 lg:col-span-3">03 · El problema</p>
            <div className="lg:col-span-9">
              <h2 className="font-display text-[clamp(3rem,7vw,6rem)] leading-[0.98] font-medium tracking-[-0.015em]">Casi siempre, nos enteramos tarde.</h2>
              <p className="mt-8 max-w-2xl text-lead text-paper/85">
                Los territorios son enormes, los recursos para recorrerlos son pocos y una tala puede pasar meses sin que nadie la vea. Las
                imágenes existen: lo difícil es revisarlas todas, todo el tiempo.
              </p>
            </div>
          </div>
        </section>

        {/* ── 04 Evidencia (datos reales de Sentinel-2): el momento especial, fijo en su propia sección ── */}
        <section id="como-funciona" data-chapter="evidencia" className={reduced ? "border-b border-ink px-5 sm:px-8" : "relative h-[300vh] border-b border-ink px-5 sm:px-8"}>
          <div data-evidence className={reduced ? "flex py-20" : "sticky top-16 flex min-h-[calc(100svh-4rem)] items-center py-12 sm:top-20 sm:min-h-[calc(100svh-5rem)]"} style={{ "--reveal": reduced ? 1 : 0, "--mask": reduced ? 1 : 0, "--metrics": reduced ? 1 : 0 } as React.CSSProperties}>
            <div className="mx-auto grid w-full max-w-7xl items-center gap-10 lg:grid-cols-12">
              <div className="flex flex-col gap-6 lg:col-span-5">
                <p className="eyebrow">04 · Cómo funciona</p>
                <h2 className="font-display text-[clamp(2rem,3.6vw,3.052rem)] leading-[1.04] font-medium text-ink">
                  Comparamos el antes y el después. <span className="text-ink-2">La máquina señala; una persona decide.</span>
                </h2>
                <ol className="flex flex-col border-t border-ink text-sm text-ink">
                  <li className="flex gap-4 border-b border-rule py-3"><span className="font-mono text-ink-2">a.</span> Combinamos varias imágenes de cada periodo y descartamos nubes y sombras.</li>
                  <li className="flex gap-4 border-b border-rule py-3"><span className="font-mono text-ink-2">b.</span> Medimos cuánto bajó el verdor y la estructura del bosque en cada píxel de 10 m.</li>
                  <li className="flex gap-4 border-b border-rule py-3"><span className="font-mono text-ink-2">c.</span> Dibujamos las áreas de cambio, calculamos su superficie y creamos una alerta para revisar.</li>
                </ol>
                <div className="border-2 border-ink bg-field p-5" style={{ opacity: "var(--metrics)", transform: "translateY(calc((1 - var(--metrics)) * 12px))" }}>
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity="priority" />
                    <span className="font-mono text-xs text-ink-2">{fmtCoord(lon, lat)}</span>
                  </div>
                  <p className="mt-3 font-display text-h4 font-medium text-ink">Se detectó una posible pérdida de vegetación</p>
                  <p className="mt-1 text-sm text-ink-2">
                    Diferencia importante entre las imágenes del {refDate} y el {obsDate}. Área estimada:{" "}
                    <strong className="text-ink">{fmtNumber(story.finding.area_ha, 1)} hectáreas</strong>.
                  </p>
                  <p className="mt-3 font-mono text-[0.6875rem] leading-relaxed text-ink-2">
                    Datos reales · {story.region} · {story.detector} · caída media de NDVI {story.finding.mean_ndvi_drop} · {story.attribution}
                  </p>
                </div>
              </div>

              <figure className="plate relative aspect-square w-full lg:col-span-7">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/story/before.jpg" alt={`Imagen Sentinel-2 de ${story.region} del ${refDate}: bosque continuo`} className="absolute inset-0 size-full object-cover" />
                <div className="absolute inset-0" style={{ clipPath: "inset(0 0 0 calc((1 - var(--reveal)) * 100%))" }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src="/story/after.jpg" alt={`Imagen Sentinel-2 del mismo lugar del ${obsDate}: aparece un claro`} className="absolute inset-0 size-full object-cover" />
                </div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/story/change.png" alt="Áreas de cambio detectadas resaltadas en rojo y ámbar" className="absolute inset-0 size-full object-cover [image-rendering:pixelated]" style={{ opacity: "var(--mask)" }} />
                {/* La línea de corte se mueve con la revelación: una línea fina, como una regla atravesando la lámina. */}
                <div aria-hidden className="pointer-events-none absolute inset-y-0 w-px bg-field shadow-[0_0_0_1px_rgb(22_33_27/0.55)]" style={{ left: "calc((1 - var(--reveal)) * 100%)", opacity: "calc(var(--reveal) * (1 - var(--reveal)) * 4)" }} />
                <figcaption className="absolute inset-x-0 bottom-0 flex flex-wrap justify-between gap-2 font-mono text-[0.6875rem] text-ink">
                  <span className="bg-field px-2 py-1">ANTES · {fmtDate(story.reference.last, { day: "2-digit", month: "short", year: "numeric" })}</span>
                  <span className="bg-field px-2 py-1">DESPUÉS · {fmtDate(story.observation.last, { day: "2-digit", month: "short", year: "numeric" })}</span>
                </figcaption>
              </figure>
            </div>
          </div>
        </section>

        {/* ── 05 Plataforma: un índice, no seis tarjetas idénticas ── */}
        <section className="border-b border-ink">
          <div className="mx-auto grid max-w-7xl gap-8 px-5 py-20 sm:px-8 lg:grid-cols-12 lg:py-28">
            <p className="eyebrow lg:col-span-3">05 · La plataforma</p>
            <div className="lg:col-span-9">
              <h2 className="max-w-3xl font-display text-[clamp(2.441rem,4.6vw,3.815rem)] leading-[1.02] font-medium text-ink">De la imagen satelital a una decisión informada.</h2>
              <ol className="mt-14 grid border-t border-ink sm:grid-cols-2">
                {[
                  ["Imágenes reales y abiertas", "Escenas Sentinel-2 consultadas en vivo, con nubes enmascaradas y la fuente de cada imagen registrada."],
                  ["Detección explicable", "Cada hallazgo indica qué método lo detectó, con qué intensidad y con qué calidad de imagen."],
                  ["Explorador geográfico", "Territorios, zonas, alertas y relieve 3D en un mapa diseñado para leerse rápido."],
                  ["Comparador temporal", "Desliza entre el antes y el después, con la máscara de cambio y los polígonos encima."],
                  ["Alertas sin ruido", "Una alerta por perturbación aunque se detecte varias veces, y un solo correo por alerta."],
                  ["Revisión humana", "Confirmar o descartar exige una observación. Todo queda en un historial auditable."],
                ].map(([title, text], i) => (
                  <li key={title} className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-x-3 border-b border-rule py-6 sm:odd:pr-8 sm:even:border-l sm:even:pl-8">
                    <span className="font-mono text-sm text-ink-2">{String(i + 1).padStart(2, "0")}</span>
                    <div>
                      <h3 className="text-lg font-semibold text-ink">{title}</h3>
                      <p className="mt-2 text-sm leading-relaxed text-ink-2">{text}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        {/* ── Cierre: la única franja de marca ── */}
        <section className="bg-brand text-paper">
          <div className="mx-auto flex max-w-7xl flex-col items-start gap-8 px-5 py-20 sm:px-8 md:flex-row md:items-end md:justify-between lg:py-24">
            <div>
              <h2 className="font-display text-[clamp(2.441rem,4.6vw,3.815rem)] leading-[1.02] font-medium">Empieza a vigilar un territorio.</h2>
              <p className="mt-4 max-w-lg text-lead text-paper/85">Crea una cuenta, explora las zonas activas y recibe un correo cuando algo cambie.</p>
            </div>
            <ButtonLink href="/register" size="lg" icon={<ArrowRight className="size-5" />} className="bg-paper! text-brand! hover:bg-field!">
              Crear cuenta gratuita
            </ButtonLink>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
