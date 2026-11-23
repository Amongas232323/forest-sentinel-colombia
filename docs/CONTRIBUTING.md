# Contribuir

El repositorio está organizado para que **cuatro personas trabajen en paralelo** sin bloquearse, unidas por contratos explícitos y probados.

## 1. Responsabilidades

| Rol | Carpeta propia | Entrega | No debe tocar sin acordar |
|---|---|---|---|
| Visión artificial | `ml/src/sentinel_ml/{detectors,model,training}`, `ml/training/` | Detectores que cumplan `ChangeDetector`; checkpoints con métricas | `contracts.py` |
| Pipeline satelital | `ml/src/sentinel_ml/{stac,raster_io,composite,grid,vectorize,pipeline,config}` | `run_pipeline() → PipelineResult` | Esquema de BD |
| Backend y alertas | `backend/` | API OpenAPI, persistencia, alertas, correo, seguridad | `frontend/` |
| Frontend | `frontend/` | Interfaz que consume la API | Esquemas Pydantic |

## 2. Contratos

1. **Detector → Pipeline** (`ml/src/sentinel_ml/detectors/base.py`): `predict(reference, observation, valid) -> DetectorOutput(score, signal, ndvi_drop, nbr_drop)`; `score` en 0–1 con NaN donde no es válido, donde `0.5` es el corte de decisión. `parameters()` debe ser serializable a JSON.
2. **Pipeline → Backend** (`ml/src/sentinel_ml/contracts.py`): `PipelineResult` y `Finding`. Cambiar un campo exige subir `CONTRACT_VERSION` y adaptar `backend/app/services/jobs.py::persist_result`. Las pruebas del backend construyen resultados con estas mismas *dataclasses* (`backend/tests/factories.py`): si rompes el contrato, el CI del backend falla.
3. **Backend → Frontend**: los esquemas de `backend/app/schemas/` son la fuente de verdad (`/api/v1/openapi.json`). `frontend/src/lib/api/types.ts` los replica 1:1. **El frontend no inventa campos**: si necesita uno nuevo, se añade primero al esquema Pydantic.

## 3. Convenciones

- **Idioma**: código e identificadores en inglés; textos de interfaz, correos, mensajes de error y documentación de usuario en español de Colombia.
- **Python**: 3.11+, tipado completo, `ruff check` y `ruff format` (140 columnas). Lógica en `services/`, rutas delgadas en `api/routes/`.
- **TypeScript**: estricto (`noUncheckedIndexedAccess`), ESLint de Next. Lógica de datos en `lib/` y `features/*`, nunca dentro de componentes de presentación genéricos.
- **API**: rutas en plural, `snake_case` en JSON, errores con el sobre estándar.
- **BD**: nombres de restricciones deterministas (`NAMING` en `db/base.py`), toda migración revisada a mano.
- **Commits**: imperativo y en español o inglés consistente (`feat(alerts): deduplicate by intersection`).

## 4. Flujo de trabajo

1. Rama desde `main`: `feat/<rol>-<tema>`.
2. Pruebas locales del módulo tocado (ver README). Si cambias un contrato, ejecuta las tres suites.
3. Pull request con descripción de qué cambia en los contratos. CI ejecuta lint, tipos, pruebas, migraciones `up/down/up`, build y auditoría de dependencias.
4. Revisión de al menos un integrante de otro rol si el PR toca un contrato.

## 5. Estrategia de integración

- Cada rol puede trabajar con **dobles reales del contrato**: el frontend con la API levantada y datos del seed; el backend con `factories.pipeline_result()`; el pipeline con `SpectralBaselineDetector`; el modelo con `ml/tests/test_training.py` (datos sintéticos).
- Prueba de integración real: lanzar un análisis desde la interfaz sobre una zona del seed y verificar alerta + correo en Mailpit.

## 6. Añadir un detector nuevo

1. Implementa la clase con `detector_id`, `version`, `kind` y `predict/parameters`.
2. Regístrala en `detectors/__init__.py::get_detector`.
3. Evalúala con `python -m sentinel_ml.training train …` o un script equivalente sobre el **conjunto de prueba geográfico** y documenta las métricas en `AI_MODEL_DOCUMENTATION.md`.
4. Nunca pongas `kind="deep-learning"` a algo que no sea un modelo entrenado.
