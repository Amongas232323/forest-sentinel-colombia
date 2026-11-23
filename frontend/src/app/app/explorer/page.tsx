"use client";

import { Crosshair, Layers, PenSquare, Search, X } from "lucide-react";
import type { GeoJSONSource, Map as MLMap, MapMouseEvent } from "maplibre-gl";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { toast } from "@/components/ui/Feedback";
import { MapView } from "@/features/map/MapView";
import { geometryBounds, setAlerts, setRegions, setTerritories, setVisibility } from "@/features/map/layers";
import { uiStorage } from "@/features/privacy/consent";
import { ApiError } from "@/lib/api/client";
import { useAlertsGeo, useCreateRegion, useRegions, useTerritoryGeometries } from "@/lib/api/hooks";
import type { GeoJSONGeometry } from "@/lib/api/types";
import { hasRole, useAuth } from "@/lib/auth/store";
import { cn } from "@/lib/cn";
import { fmtCoord, fmtKm2 } from "@/lib/format";
import { TERRITORY_NAMES } from "@/features/globe/Globe";

type LayerKey = "territories" | "regions" | "alerts" | "satellite" | "terrain";
const LAYER_IDS: Record<Exclude<LayerKey, "terrain">, string[]> = {
  territories: ["territories-fill", "territories-line"],
  regions: ["regions-fill", "regions-line", "regions-label"],
  alerts: ["alerts-fill", "alerts-line", "alerts-point"],
  satellite: ["satellite"],
};
const LAYER_LABELS: Record<LayerKey, string> = {
  territories: "Territorios",
  regions: "Zonas vigiladas",
  alerts: "Alertas",
  satellite: "Mosaico Sentinel-2 (2020)",
  terrain: "Relieve 3D",
};
const DEFAULT_LAYERS: Record<LayerKey, boolean> = { territories: true, regions: true, alerts: true, satellite: false, terrain: false };

function applyLayers(map: MLMap, l: Record<LayerKey, boolean>) {
  (Object.keys(LAYER_IDS) as (keyof typeof LAYER_IDS)[]).forEach((k) => setVisibility(map, LAYER_IDS[k], l[k]));
  if (l.terrain) {
    map.setTerrain({ source: "terrain", exaggeration: 1.6 });
    if (map.getPitch() < 30) map.easeTo({ pitch: 60, duration: 900 });
  } else {
    map.setTerrain(null);
  }
}

interface SearchHit {
  label: string;
  sub: string;
  bounds: [[number, number], [number, number]];
}

function parseCoords(q: string): [number, number] | null {
  const m = q.trim().match(/^(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)$/);
  if (!m) return null;
  const lat = Number(m[1]), lon = Number(m[2]);
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? [lon, lat] : null;
}

export default function ExplorerPage() {
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const mapRef = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const [layers, setLayers] = useState(DEFAULT_LAYERS);
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [query, setQuery] = useState("");
  const [panelOpen, setPanelOpen] = useState(true);
  const [drawing, setDrawing] = useState(false);
  const [draft, setDraft] = useState<GeoJSONGeometry | null>(null);
  const drawStart = useRef<[number, number] | null>(null);

  const territories = useTerritoryGeometries();
  const regions = useRegions();
  const alerts = useAlertsGeo({ status: ["new", "pending_review", "in_review", "confirmed"] });

  useEffect(() => setLayers(uiStorage.get("explorer-layers", DEFAULT_LAYERS)), []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (territories.data) setTerritories(map, territories.data);
    if (regions.data) setRegions(map, regions.data);
    if (alerts.data) setAlerts(map, alerts.data);
    applyLayers(map, layers);
  }, [ready, territories.data, regions.data, alerts.data, layers]);

  function toggleLayer(k: LayerKey) {
    setLayers((prev) => {
      const next = { ...prev, [k]: !prev[k] };
      uiStorage.set("explorer-layers", next);
      return next;
    });
  }

  const hits: SearchHit[] = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    const coords = parseCoords(query);
    if (coords) return [{ label: fmtCoord(coords[0], coords[1]), sub: "Ir a coordenadas", bounds: [[coords[0] - 0.05, coords[1] - 0.05], [coords[0] + 0.05, coords[1] + 0.05]] }];
    const out: SearchHit[] = [];
    territories.data?.forEach((t) => {
      const name = TERRITORY_NAMES[t.slug] ?? t.slug;
      if (name.toLowerCase().includes(q)) out.push({ label: name, sub: "Territorio", bounds: geometryBounds(t.geometry) });
    });
    regions.data?.forEach((r) => {
      if (r.name.toLowerCase().includes(q)) out.push({ label: r.name, sub: `Zona · ${r.territory_name}`, bounds: geometryBounds(r.geometry) });
    });
    alerts.data?.features.forEach((f) => {
      const code = String(f.properties?.code ?? "");
      if (code.toLowerCase().includes(q)) out.push({ label: code, sub: `Alerta · ${f.properties?.region}`, bounds: geometryBounds(f.geometry as GeoJSONGeometry) });
    });
    return out.slice(0, 8);
  }, [query, territories.data, regions.data, alerts.data]);

  function goTo(hit: SearchHit) {
    mapRef.current?.fitBounds(hit.bounds, { padding: 80, duration: 1400, maxZoom: 14 });
    setQuery("");
  }

  function onLoad(map: MLMap) {
    mapRef.current = map;
    setReady(true);
    map.on("mousemove", (e) => setCursor([e.lngLat.lng, e.lngLat.lat]));
    for (const layer of ["alerts-fill", "alerts-point"]) {
      map.on("click", layer, (e) => {
        const f = e.features?.[0];
        if (f?.id) router.push(`/app/alerts/${f.id}`);
      });
      map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
    }
    map.on("click", "regions-fill", (e) => {
      if (drawStart.current !== null || map.getCanvas().dataset.drawing === "1") return;
      const id = e.features?.[0]?.properties?.id;
      if (id && !e.defaultPrevented) router.push(`/app/regions/${id}`);
    });
    map.addSource("draft", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: "draft-fill", type: "fill", source: "draft", paint: { "fill-color": "#1F4D36", "fill-opacity": 0.16 } });
    map.addLayer({ id: "draft-line", type: "line", source: "draft", paint: { "line-color": "#1F4D36", "line-width": 2, "line-dasharray": [2, 1] } });
  }

  // Dibujo del rectángulo: primer clic = esquina A, mover el mouse = vista previa, segundo clic = esquina B.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !drawing) return;
    map.getCanvas().dataset.drawing = "1";
    map.getCanvas().style.cursor = "crosshair";
    const rect = (a: [number, number], b: [number, number]): GeoJSONGeometry => ({
      type: "Polygon",
      coordinates: [[[a[0], a[1]], [b[0], a[1]], [b[0], b[1]], [a[0], b[1]], [a[0], a[1]]]],
    });
    const show = (g: GeoJSONGeometry | null) => (map.getSource("draft") as GeoJSONSource).setData({ type: "FeatureCollection", features: g ? [{ type: "Feature", properties: {}, geometry: g }] : [] });
    const onClick = (e: MapMouseEvent) => {
      e.preventDefault();
      const p: [number, number] = [e.lngLat.lng, e.lngLat.lat];
      if (!drawStart.current) {
        drawStart.current = p;
        return;
      }
      const g = rect(drawStart.current, p);
      drawStart.current = null;
      show(g);
      setDraft(g);
      setDrawing(false);
    };
    const onMove = (e: MapMouseEvent) => drawStart.current && show(rect(drawStart.current, [e.lngLat.lng, e.lngLat.lat]));
    map.on("click", onClick);
    map.on("mousemove", onMove);
    return () => {
      map.off("click", onClick);
      map.off("mousemove", onMove);
      map.getCanvas().style.cursor = "";
      delete map.getCanvas().dataset.drawing;
    };
  }, [drawing]);

  function cancelDraft() {
    setDraft(null);
    drawStart.current = null;
    (mapRef.current?.getSource("draft") as GeoJSONSource | undefined)?.setData({ type: "FeatureCollection", features: [] });
  }

  const canDraw = hasRole(user, "analyst");

  return (
    <div className="relative h-[calc(100svh-3.5rem-4rem)] lg:h-[100svh]">
      <MapView className="absolute inset-0" label="Mapa interactivo de territorios, zonas y alertas" onLoad={onLoad} />

      {/* Panel de control */}
      <div className="pointer-events-none absolute inset-x-3 top-3 flex flex-col gap-2 sm:inset-x-auto sm:left-4 sm:top-4 sm:w-[340px]">
        <div className="panel pointer-events-auto p-3">
          <label className="relative block">
            <span className="sr-only">Buscar territorio, zona, código de alerta o coordenadas</span>
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-2" aria-hidden />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && hits[0] && goTo(hits[0])}
              placeholder="Zona, alerta (FS-…) o «2.39, -72.79»"
              className="h-11 w-full rounded-xl border border-rule bg-paper/95 pr-3 pl-9 text-sm text-ink placeholder:text-ink-2 focus:border-brand focus:outline-none"
              role="combobox"
              aria-expanded={hits.length > 0}
              aria-controls="search-results"
            />
          </label>
          {hits.length > 0 && (
            <ul id="search-results" role="listbox" className="mt-2 flex flex-col">
              {hits.map((h) => (
                <li key={h.label + h.sub} role="option" aria-selected={false}>
                  <button onClick={() => goTo(h)} className="flex w-full flex-col rounded-lg px-3 py-2 text-left hover:bg-paper-2">
                    <span className="text-sm text-ink">{h.label}</span>
                    <span className="text-xs text-ink-2">{h.sub}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 px-1 text-[0.6875rem] text-ink-2">La búsqueda es local: no enviamos tu consulta a servicios externos.</p>
        </div>

        <div className="panel pointer-events-auto p-3">
          <button onClick={() => setPanelOpen((v) => !v)} className="flex w-full items-center justify-between px-1 text-sm font-semibold text-ink" aria-expanded={panelOpen}>
            <span className="flex items-center gap-2"><Layers className="size-4 text-brand" aria-hidden /> Capas</span>
            <span className="font-mono text-xs text-ink-2">{panelOpen ? "−" : "+"}</span>
          </button>
          {panelOpen && (
            <ul className="mt-3 flex flex-col gap-1">
              {(Object.keys(LAYER_LABELS) as LayerKey[]).map((k) => (
                <li key={k}>
                  <label className="flex cursor-pointer items-center justify-between rounded-lg px-2 py-2 text-sm text-ink hover:bg-paper-2">
                    {LAYER_LABELS[k]}
                    <input type="checkbox" role="switch" checked={layers[k]} onChange={() => toggleLayer(k)} className="peer sr-only" />
                    <span aria-hidden className="relative h-5 w-9 rounded-xs border border-rule-strong bg-paper-3 transition-colors peer-checked:border-brand peer-checked:bg-brand peer-focus-visible:ring-2 peer-focus-visible:ring-water after:absolute after:top-px after:left-px after:size-4 after:rounded-[1px] after:bg-ink-3 after:transition-transform peer-checked:after:translate-x-4 peer-checked:after:bg-field" />
                  </label>
                </li>
              ))}
            </ul>
          )}
          {panelOpen && (
            <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-rule px-2 pt-3 text-[0.6875rem] text-ink-2" aria-label="Leyenda">
              <li className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-brand" aria-hidden /> Territorio</li>
              <li className="flex items-center gap-1.5"><span className="h-0.5 w-4 border-t border-dashed border-ink" aria-hidden /> Zona</li>
              <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-signal" aria-hidden /> Prioritario</li>
              <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-ochre-mark" aria-hidden /> Importante / moderado</li>
            </ul>
          )}
        </div>

        {canDraw && !draft && (
          <Button className="pointer-events-auto self-start" variant={drawing ? "primary" : "secondary"} size="sm" icon={<PenSquare className="size-4" />} onClick={() => { cancelDraft(); setDrawing((v) => !v); }}>
            {drawing ? "Haz clic en dos esquinas…" : "Dibujar una zona nueva"}
          </Button>
        )}
      </div>

      {cursor && (
        <p className="pointer-events-none absolute bottom-10 left-1/2 hidden -translate-x-1/2 items-center gap-2 rounded-xs border border-ink bg-field px-3 py-1.5 font-mono text-[0.6875rem] text-ink backdrop-blur sm:flex" aria-hidden>
          <Crosshair className="size-3 text-brand" /> {fmtCoord(cursor[0], cursor[1])}
        </p>
      )}

      {draft && <NewRegionDialog geometry={draft} onClose={cancelDraft} />}
    </div>
  );
}

function NewRegionDialog({ geometry, onClose }: { geometry: GeoJSONGeometry; onClose: () => void }) {
  const create = useCreateRegion();
  const router = useRouter();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const ring = (geometry.coordinates as number[][][])[0]!;
  const w = Math.abs(ring[1]![0]! - ring[0]![0]!) * 111.32 * Math.cos(((ring[0]![1]! + ring[2]![1]!) / 2) * (Math.PI / 180));
  const h = Math.abs(ring[2]![1]! - ring[0]![1]!) * 110.57;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const name = String(fd.get("name") ?? "").trim();
    if (name.length < 3) return setErrors({ name: "Escribe un nombre de al menos 3 caracteres." });
    try {
      const region = await create.mutateAsync({ territory_slug: String(fd.get("territory")), name, description: String(fd.get("description") ?? ""), geometry, cadence_days: Number(fd.get("cadence")) });
      toast.success("Zona creada. Ya puedes lanzar su primer análisis.");
      router.push(`/app/regions/${region.id}`);
    } catch (err) {
      setErrors({ form: err instanceof ApiError ? err.message : "No se pudo crear la zona." });
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="new-region-title" className="absolute inset-x-3 bottom-3 z-10 sm:inset-x-auto sm:right-4 sm:bottom-4 sm:w-[380px]">
      <form onSubmit={submit} className="panel panel-ticks flex flex-col gap-4 p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="eyebrow">Nueva zona</p>
            <h2 id="new-region-title" className="font-display text-2xl text-ink">Vigilar esta área</h2>
            <p className="mt-1 font-mono text-xs text-ink-2">≈ {fmtKm2(w * h)} · máximo 2.500 km²</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Cancelar" className="grid size-11 place-items-center rounded-xs text-ink-2 hover:bg-paper-3"><X className="size-4" /></button>
        </div>
        {errors.form && <p role="alert" className="rounded-xl border border-signal bg-signal-tint px-3 py-2 text-sm text-signal">{errors.form}</p>}
        <SelectField label="Territorio" name="territory" defaultValue="guaviare" hint="La zona debe quedar dentro de este territorio.">
          {Object.entries(TERRITORY_NAMES).map(([slug, name]) => <option key={slug} value={slug}>{name}</option>)}
        </SelectField>
        <TextField label="Nombre" name="name" required autoFocus error={errors.name} />
        <TextField label="Descripción (opcional)" name="description" />
        <SelectField label="Frecuencia de análisis automático" name="cadence" defaultValue="30">
          <option value="15">Cada 15 días</option>
          <option value="30">Cada 30 días</option>
          <option value="60">Cada 60 días</option>
        </SelectField>
        <div className={cn("flex gap-2")}>
          <Button type="submit" loading={create.isPending}>Crear zona</Button>
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
        </div>
      </form>
    </div>
  );
}
