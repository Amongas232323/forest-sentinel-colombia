# Pipeline satelital

Paquete `ml/src/sentinel_ml`. Entrada: AOI (bbox WGS84) + dos ventanas de fechas. Salida: `PipelineResult` (`contracts.py`) + evidencia en el directorio del análisis.

## 1. Etapas

| # | Etapa | Módulo | Detalle |
|---|---|---|---|
| 1 | Rejilla | `grid.py` | UTM de la zona (por centroide), 10 m, ajustada a múltiplos de 10 m. Límites: ≤ 2 500 km², ≤ 8 192 px por lado |
| 2 | Búsqueda | `stac.py` | Earth Search STAC, `eo:cloud_cover < 60`, orden por nubosidad, máx. 4 escenas por periodo |
| 3 | Validación de metadatos | `stac.py` | Activos requeridos, EPSG, fecha; **lista blanca de hosts HTTPS** y solo `.tif` (anti-SSRF) |
| 4 | Lectura por ventanas | `raster_io.py` | `WarpedVRT` sobre COG remotos → solo los bloques necesarios (rangos HTTP); bilineal para reflectancia, vecino más cercano para SCL; 8 lecturas paralelas |
| 5 | Calidad / nubes | `composite.py` | SCL inválido: 0, 1, 3, 8, 9, 10, 11 (sin dato, saturado, sombra, nubes media/alta, cirros, nieve); reflectancia fuera de [−0,05, 1,5] → inválida |
| 6 | Radiometría | `composite.py` | `reflectancia = DN · scale + offset` desde `raster:bands` del STAC (offset −0,1 en línea base ≥ 04.00) |
| 7 | Composición | `composite.py` | Mediana por píxel de las observaciones válidas (reduce nubes residuales y ruido) |
| 8 | Teselado | `pipeline.py` | Teselas de 1 024 px; cada una escribe evidencia y un marcador `tiles/r_c.json` |
| 9 | Detección | `detectors/` | `ChangeDetector.predict(ref, obs, valid)` → puntuación 0–1, señal, ΔNDVI, ΔNBR |
| 10 | Vectorización | `vectorize.py` | Apertura morfológica 3×3, componentes conexos (8-vecindad), unidad mínima 0,5 ha, Douglas-Peucker 10 m, área en UTM, reproyección a WGS84 |
| 11 | Severidad | `severity.py` | Umbrales configurables (AI_MODEL_DOCUMENTATION §6) |
| 12 | Evidencia | `pipeline.py` | PNG antes/después (ganancia fija → comparables), máscara RGBA, GeoTIFF int16 de 4 bandas (score, señal, ΔNDVI, ΔNBR ×1000), esquinas WGS84 |
| 13 | Puerta de calidad | `pipeline.py` | `quality_ok = False` si < 40 % del área es válida en algún periodo → el backend **no crea alertas** |

## 2. Política de colecciones

1. **Sentinel-2 L2A Collection-1** (`sentinel-2-c1-l2a`): reprocesamiento homogéneo de ESA → radiometría consistente entre años.
2. Solo si un periodo no tiene C1 se usa la colección heredada (`sentinel-2-l2a`), **deduplicada por adquisición** prefiriendo el procesamiento `_0_`. Motivo verificado: los ítems reprocesados `_1_` declaran `offset = −0,1` pero sus píxeles ya no lo requieren (NIR/SWIR coinciden con `_0_` sin aplicar el offset). Mezclarlos producía composiciones con tonos magenta. El resultado incluye una nota de calidad cuando se usa la colección heredada.

Cobertura C1 observada en la zona de Tinigua (escenas/año): 2018: 29 · 2019: 56 · 2020: 72 · 2021: 73 · **2022: 7** · 2023: 73 · 2024: 72 · 2025: 101.

## 3. Memoria y rendimiento

- Nunca se carga una escena completa: por tesela se leen ≤ 4 escenas × 7 bandas × 1 024² px (≈ 120 MB en float32).
- La vectorización lee el GeoTIFF de evidencia completo (int16; ≤ 8 192² → ≤ 512 MB en el peor caso permitido).
- Medido: 12 332 ha (1 114 × 1 107 px) en **71 s**; 49 461 ha (≈ 2 230² px) en **≈ 4 min** (dominado por latencia HTTP).

## 4. Reanudación e idempotencia

- `manifest.json` fija AOI, fechas, rejilla, escenas, detector y hash de configuración. Re-ejecutar con otros parámetros sobre el mismo directorio lanza `ManifestMismatchError`.
- Las teselas terminadas no se recalculan. Celery usa `acks_late` + `reject_on_worker_lost`: si un worker muere, otro retoma el análisis.
- `scenes.json` guarda el inventario de escenas para la BD.
- Límite de tiempo por análisis (`PIPELINE_MAX_RUNTIME_S`) y límites duros de Celery.

## 5. Seguridad de entradas externas

Los STAC y los COG son **entradas no confiables**: lista blanca de hosts (`config.ALLOWED_ASSET_HOSTS`), solo HTTPS, solo GeoTIFF, verificación de una banda por activo, límites de tamaño de la AOI, reflectancias fuera de rango descartadas, `torch.load(weights_only=True)` para checkpoints.

## 6. Fuentes evaluadas

| Fuente | Acceso | Estado | Notas |
|---|---|---|---|
| Earth Search (Element 84) — Sentinel-2 L2A C1 | Abierto, sin credenciales | **Integrada (principal)** | COG en `e84-earth-search-sentinel-data` (us-west-2) |
| Earth Search — Sentinel-2 L2A heredada | Abierto | Integrada (respaldo) | Ver §2 |
| Copernicus Data Space Ecosystem — Sentinel-1 GRD | Cuenta gratuita (OAuth) | No integrada | Radar útil con nubes persistentes (Amazonía, Sierra Nevada). Requiere calibración radiométrica, corrección de terreno y filtrado de *speckle*; plan: colección `sentinel-1-grd` + detector de caída de retrodispersión VH |
| NASA Earthdata — HLS Landsat (HLSL30) | Earthdata Login | No integrada | Histórico 30 m armonizado con S2; útil para series largas |
| Hansen GFC (UMD) | Abierto (CC BY 4.0) | Usada **solo para entrenamiento** | Etiquetas anuales de pérdida, 30 m |

## 7. Uso directo

```bash
python -m sentinel_ml.cli run --bbox -74.25 2.15 -74.15 2.25 \
  --reference 2018-12-01/2019-02-28 --observation 2019-12-01/2020-03-15 --out data/runs/tinigua
```
