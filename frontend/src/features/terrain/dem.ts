/**
 * Elevación real desde AWS Terrain Tiles (codificación PNG Terrarium, datos abiertos):
 *   height_m = (R * 256 + G + B / 256) - 32768
 */
const TILE = 256;
const URL_T = (z: number, x: number, y: number) => `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${x}/${y}.png`;

const lon2x = (lon: number, z: number) => ((lon + 180) / 360) * 2 ** z;
const lat2y = (lat: number, z: number) => {
  const r = (lat * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * 2 ** z;
};

export interface HeightGrid {
  width: number;
  height: number;
  data: Float32Array; // metros, por filas, el norte en la fila 0
  min: number;
  max: number;
  /** tamaño en terreno de la grilla, en metros */
  spanX: number;
  spanY: number;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`tile ${src}`));
    img.src = src;
  });
}

export async function fetchHeightGrid([w, s, e, n]: [number, number, number, number], resolution = 192): Promise<HeightGrid> {
  let z = 14;
  while (z > 6 && (Math.floor(lon2x(e, z)) - Math.floor(lon2x(w, z)) > 2 || Math.floor(lat2y(s, z)) - Math.floor(lat2y(n, z)) > 2)) z--;
  const x0 = Math.floor(lon2x(w, z)), x1 = Math.floor(lon2x(e, z));
  const y0 = Math.floor(lat2y(n, z)), y1 = Math.floor(lat2y(s, z));
  const canvas = document.createElement("canvas");
  canvas.width = (x1 - x0 + 1) * TILE;
  canvas.height = (y1 - y0 + 1) * TILE;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("canvas unavailable");
  const jobs: Promise<void>[] = [];
  for (let x = x0; x <= x1; x++)
    for (let y = y0; y <= y1; y++)
      jobs.push(loadImage(URL_T(z, x, y)).then((img) => ctx.drawImage(img, (x - x0) * TILE, (y - y0) * TILE)));
  await Promise.all(jobs);
  const px = ctx.getImageData(0, 0, canvas.width, canvas.height).data;

  const data = new Float32Array(resolution * resolution);
  let min = Infinity, max = -Infinity;
  const sample = (fx: number, fy: number) => {
    const ix = Math.min(canvas.width - 1, Math.max(0, Math.round(fx)));
    const iy = Math.min(canvas.height - 1, Math.max(0, Math.round(fy)));
    const i = (iy * canvas.width + ix) * 4;
    return px[i]! * 256 + px[i + 1]! + px[i + 2]! / 256 - 32768;
  };
  for (let r = 0; r < resolution; r++) {
    const lat = n - ((n - s) * r) / (resolution - 1);
    const fy = (lat2y(lat, z) - y0) * TILE;
    for (let c = 0; c < resolution; c++) {
      const lon = w + ((e - w) * c) / (resolution - 1);
      const h = sample((lon2x(lon, z) - x0) * TILE, fy);
      data[r * resolution + c] = h;
      if (h < min) min = h;
      if (h > max) max = h;
    }
  }
  const latMid = ((n + s) / 2) * (Math.PI / 180);
  return { width: resolution, height: resolution, data, min, max, spanX: (e - w) * 111_320 * Math.cos(latMid), spanY: (n - s) * 110_574 };
}
