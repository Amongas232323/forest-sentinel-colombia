// MapLibre 6 corre el procesamiento de tiles en un worker que viene como archivo aparte
// (maplibre-gl-worker.mjs). El bundler de Next no lo copia, entonces lo dejamos en public/
// antes de dev y build, y MapView le dice a MapLibre dónde encontrarlo con setWorkerUrl.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = createRequire(import.meta.url).resolve("maplibre-gl/package.json");
const src = join(dirname(pkg), "dist", "maplibre-gl-worker.mjs");
const outDir = join(root, "public", "vendor");

mkdirSync(outDir, { recursive: true });
copyFileSync(src, join(outDir, "maplibre-gl-worker.mjs"));
console.log("worker de MapLibre copiado a public/vendor/");
