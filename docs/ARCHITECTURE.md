# Arquitectura

## 1. Vista general

```
                       ┌──────────────────────── Navegador ─────────────────────────┐
                       │ Next.js (App Router) · R3F globo/terreno · MapLibre · Query │
                       └───────────────▲───────────────────────┬────────────────────┘
                                       │ mismo origen /api/v1/* (proxy Next → FastAPI)
                                       │                       │ teselas abiertas (mapa base,
┌──────────────────────────────────────┴───────────┐           │ elevación, mosaico S2)
│ FastAPI (app/)                                   │           ▼
│  api/routes  →  services  →  models (SQLAlchemy) │   OpenFreeMap · AWS Terrain · EOX
│  auth · regiones · jobs · alertas · reportes …   │
└──────┬─────────────────────┬─────────────────────┘
       │ SQL/PostGIS          │ Celery (Redis)
┌──────▼───────┐      ┌───────▼─────────────────────────────────────────────┐
│ PostgreSQL   │◄─────┤ Worker: run_job → sentinel_ml.run_pipeline           │
│ + PostGIS    │      │   STAC (Earth Search) → COG por ventanas (AWS S3)    │
└──────────────┘      │   → composición → detector → vectorización          │
                      │   → persist_result → generate_alerts → notify (SMTP) │
                      └──────────────────────────────────┬──────────────────┘
                                                         │ rásters de evidencia
                                                  DATA_DIR/runs/<job_id>/
```

## 2. Módulos y responsables

| Módulo | Carpeta | Rol del equipo | Contrato que expone |
|---|---|---|---|
| Visión artificial | `ml/src/sentinel_ml/{detectors,model,training}` | Especialista en visión artificial | Protocolo `ChangeDetector` → `DetectorOutput` |
| Pipeline satelital | `ml/src/sentinel_ml/{stac,raster_io,composite,grid,vectorize,pipeline}` | Especialista en datos satelitales | `run_pipeline()` → `PipelineResult` (`contracts.py`) |
| Backend y alertas | `backend/app` | Especialista en backend | OpenAPI `/api/v1/openapi.json` |
| Frontend | `frontend/src` | Especialista en frontend | Consume `lib/api/types.ts` (espejo del OpenAPI) |

Los contratos están versionados (`CONTRACT_VERSION` en `ml/contracts.py`) y probados entre módulos: `backend/tests/factories.py` construye resultados con las *dataclasses reales* del paquete ML, de modo que un cambio incompatible rompe las pruebas del backend.

## 3. Decisiones principales

| Decisión | Alternativas | Justificación |
|---|---|---|
| **Earth Search + Sentinel-2 L2A Collection-1** | Copernicus Data Space, Planetary Computer, GEE | Sin credenciales, COG en S3 (lectura por rangos HTTP), reprocesamiento homogéneo de ESA; la colección heredada mezcla líneas base y declara offsets erróneos en ítems `_1_` (lo comprobamos píxel a píxel). |
| **Detector espectral por reglas como baseline de producción** | Usar solo la red | Funciona desde el primer día, es explicable y auditable; la red solo se activa con un checkpoint evaluado. Ningún resultado se presenta como IA si no lo es. |
| **Siamese U-Net (FC-Siam-diff)** | U-Net++, DeepLabV3+, SegFormer | Diseñada para cambio bitemporal multiespectral; pesos compartidos (regulariza con pocos datos); ~1,4 M parámetros → inferencia en CPU viable. Ver AI_MODEL_DOCUMENTATION §4. |
| **PyTorch únicamente** | TF + PyTorch | Un solo framework; TensorFlow no aporta nada aquí. |
| **Rejilla UTM común por análisis** | Reproyectar por escena | Alineación píxel a píxel entre fechas (el desregistro genera bordes falsos). |
| **Procesamiento por teselas con marcadores en disco** | Cargar la escena completa | RAM acotada (~1024² px × bandas × escenas) y reanudación tras fallos (`acks_late`). |
| **Alertas = agregado de detecciones** | Una alerta por polígono | Deduplicación espacio-temporal: una perturbación, una alerta, un correo. |
| **Proxy de Next hacia la API** | CORS entre orígenes | Cookie de refresco *first-party* `SameSite=Strict`, CSP con `connect-src 'self'`. |
| **Token de acceso en memoria + refresh httpOnly rotado** | JWT en localStorage | Un XSS no puede robar una credencial duradera; la reutilización de un refresh revoca la sesión. |
| **Rásters en disco/objeto, metadatos en PostGIS** | Rásters en PostgreSQL | Requisito explícito; la BD guarda rutas relativas y geometrías vectoriales. |
| **Roles en enum + matriz de permisos en código** | Tablas `roles`/`permissions` | Tres roles fijos; la matriz (`api/deps.py::PERMISSIONS`) es única, probada y legible. Migrar a tablas es directo si aparecen roles configurables. |
| **Búsqueda local en el explorador** | Geocodificador externo | Privacidad: no se envían consultas a terceros. |

## 4. Flujo de un análisis

1. `POST /regions/{id}/jobs` valida fechas (Pydantic) y crea `processing_jobs` (índice único parcial evita duplicados activos) → `enqueue_job`.
2. El worker `run_job` llama a `jobs.execute_job`: registra la versión del detector (`model_versions`), corre `run_pipeline` con un *progress writer* que actualiza `stage/progress` cada 2 s.
3. `persist_result` guarda escenas (`satellite_scenes`, `job_scenes`), `detection_results` y `detected_polygons`.
4. `generate_alerts`: puerta de calidad (cobertura ≥ 40 % por composición, ≥ 60 % en el entorno del polígono), umbral de severidad, recorte a la geometría de la zona, deduplicación (`ST_Intersects` en 120 días; reapertura si una alerta descartada crece ×1,5).
5. `notify_alerts`: un correo por (usuario, alerta) garantizado por índice único parcial + `ON CONFLICT DO NOTHING`.
6. El frontend consulta `/jobs` cada 3 s mientras hay trabajos activos; las URL de evidencia están firmadas (HMAC, 1 h).

## 5. Frontend por dominios

```
src/app/            rutas (landing, auth, /app/*, privacidad, ayuda)
src/features/       landing · globe · terrain · map · compare · alerts · regions · dashboard · auth · privacy
src/components/     ui (Button, Field, Badges, Feedback, SwipeCompare) · layout (AppShell, PublicChrome, DocPage) · brand
src/lib/            api (client, hooks, types) · auth (store) · format · device · cn
```

- **Escenas 3D** se cargan con `next/dynamic` (`ssr:false`): three.js no entra en la carga inicial (103 kB compartidos). Se pausan fuera de pantalla (`IntersectionObserver` → `frameloop="never"`), escalan resolución/partículas por nivel de GPU y tienen *fallback* 2D sin WebGL.
- La cámara del globo se controla desde un store Zustand leído en `useFrame` (sin re-renders por fotograma); GSAP ScrollTrigger escribe los objetivos. Etiquetas y marcadores se proyectan a DOM propio (accesibles, con oclusión por cara oculta).
- Con `prefers-reduced-motion` se desactivan *pin/scrub* y la narrativa se muestra estática.

## 6. Escalabilidad

- API sin estado → réplicas horizontales detrás de un proxy TLS.
- Workers escalables por concurrencia; el pipeline está limitado por E/S HTTP (8 lecturas paralelas por escena).
- `DATA_DIR` es un volumen; para varios nodos montar almacenamiento compartido u objeto (S3/MinIO) — `evidence.artifact_path` es el único punto a adaptar.
- Índices GiST en todas las geometrías; consultas de alertas por `bbox` usan `ST_Intersects` con índice.
