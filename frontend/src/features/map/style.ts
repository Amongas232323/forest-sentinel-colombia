import type { StyleSpecification } from "maplibre-gl";

/**
 * Mapa base claro tipo "atlas de campo" hecho a mano (tierra de papel, agua pizarra, etiquetas en tinta) sobre tiles vectoriales abiertos
 * (OpenFreeMap · esquema OpenMapTiles · © colaboradores de OpenStreetMap).
 * Elevación real: AWS Terrain Tiles (codificación Terrarium, datos abiertos).
 */
export const TERRAIN_SOURCE = {
  type: "raster-dem" as const,
  tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
  encoding: "terrarium" as const,
  tileSize: 256,
  maxzoom: 14,
  attribution: "Elevación: <a href='https://registry.opendata.aws/terrain-tiles/'>AWS Terrain Tiles</a>",
};

export const SATELLITE_SOURCE = {
  type: "raster" as const,
  tiles: ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg"],
  tileSize: 256,
  maxzoom: 15,
  attribution: "<a href='https://s2maps.eu'>Sentinel-2 cloudless 2020</a> by EOX IT Services GmbH (Copernicus Sentinel data 2020, CC BY-NC-SA 4.0)",
};

export const forestStyle: StyleSpecification = {
  version: 8,
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: {
    omt: { type: "vector", url: "https://tiles.openfreemap.org/planet", attribution: "© <a href='https://openfreemap.org'>OpenFreeMap</a> © <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>" },
    terrain: TERRAIN_SOURCE,
    satellite: SATELLITE_SOURCE,
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#ece9df" } },
    {
      id: "landcover",
      type: "fill",
      source: "omt",
      "source-layer": "landcover",
      paint: {
        "fill-color": ["match", ["get", "class"], "wood", "#d3dcc4", "grass", "#e1e3cf", "farmland", "#ebe5d2", "wetland", "#d2dfd8", "sand", "#ece3cb", "ice", "#f4f3ee", "#e6e2d5"],
        "fill-opacity": 0.85,
      },
    },
    { id: "landuse", type: "fill", source: "omt", "source-layer": "landuse", filter: ["in", ["get", "class"], ["literal", ["residential", "commercial", "industrial"]]], paint: { "fill-color": "#ddd7c9", "fill-opacity": 0.8 } },
    { id: "satellite", type: "raster", source: "satellite", layout: { visibility: "none" }, paint: { "raster-opacity": 0.92, "raster-saturation": -0.15, "raster-brightness-max": 0.85 } },
    { id: "hillshade", type: "hillshade", source: "terrain", paint: { "hillshade-shadow-color": "#6f6a5c", "hillshade-highlight-color": "#fbfaf6", "hillshade-accent-color": "#a39d8c", "hillshade-exaggeration": 0.32 } },
    { id: "water", type: "fill", source: "omt", "source-layer": "water", paint: { "fill-color": "#c3d4dd" } },
    { id: "waterway", type: "line", source: "omt", "source-layer": "waterway", paint: { "line-color": "#7fa3b8", "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.4, 12, 1.6] } },
    {
      id: "roads",
      type: "line",
      source: "omt",
      "source-layer": "transportation",
      filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary", "secondary", "tertiary", "track"]]],
      paint: { "line-color": ["match", ["get", "class"], "track", "#b8a888", "#c4bca9"], "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.3, 14, 1.8], "line-opacity": 0.8 },
    },
    { id: "boundaries", type: "line", source: "omt", "source-layer": "boundary", filter: ["<=", ["get", "admin_level"], 4], paint: { "line-color": "#4c5750", "line-opacity": 0.7, "line-dasharray": [3, 2], "line-width": ["match", ["get", "admin_level"], 2, 1.2, 0.6] } },
    {
      id: "places",
      type: "symbol",
      source: "omt",
      "source-layer": "place",
      filter: ["in", ["get", "class"], ["literal", ["city", "town", "village"]]],
      layout: {
        "text-field": ["coalesce", ["get", "name:es"], ["get", "name"]],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["match", ["get", "class"], "city", 13, "town", 11, 10],
        "text-letter-spacing": 0.04,
      },
      paint: { "text-color": "#16211b", "text-halo-color": "#f4f2eb", "text-halo-width": 1.4 },
    },
  ],
};

export const COLOMBIA_BOUNDS: [[number, number], [number, number]] = [
  [-79.5, -4.4],
  [-66.8, 12.6],
];
