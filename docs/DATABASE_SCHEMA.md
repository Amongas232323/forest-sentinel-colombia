# Esquema de base de datos

PostgreSQL 16 + PostGIS 3.4. Migraciones con Alembic (`backend/migrations`). Todas las geometrías en **EPSG:4326** con índice **GiST** (creado por GeoAlchemy2). Los rásters **no** se guardan en la BD: viven en `DATA_DIR/runs/<job_id>/` y la BD guarda rutas relativas y extensiones.

## Diagrama (simplificado)

```
users ─┬─< auth_sessions            territories ─< monitored_regions ─< processing_jobs ─┬─ detection_results ─< detected_polygons
       ├─< password_reset_tokens          │                │                           └─< job_scenes >─ satellite_scenes >─ satellite_sources
       ├── user_preferences               │                └─< alerts ─< alert_events
       ├─< reports                        └─< alerts (territory_id)         ▲
       ├─< notifications >── alerts                                         └── detected_polygons.alert_id
       └─< audit_logs                model_versions ─< processing_jobs / detection_results / alerts
cookie_consents (subject seudónimo, user opcional)
```

## Tablas

| Tabla | Propósito | Claves e integridad |
|---|---|---|
| `users` | Cuentas | `uq_users_email_lower` (único sobre `lower(email)`); `role` enum `user_role`; bloqueo (`failed_login_count`, `locked_until`); aceptación de política (versión y fecha) |
| `auth_sessions` | Familias de refresh token | `refresh_token_hash` único (HMAC-SHA256); `previous_token_hash` para detectar reutilización; `ip_hash` seudonimizada |
| `password_reset_tokens` | Restablecimiento de un solo uso | `token_hash` único, `expires_at`, `used_at` |
| `user_preferences` | Preferencias de notificación | PK = `user_id`; `region_ids uuid[]`, `signals varchar[]` (vacío = todos) |
| `territories` | Los 4 territorios en alcance | `slug` único; `geom MULTIPOLYGON` GiST; fuente, licencia y atribución |
| `monitored_regions` | Zonas de vigilancia | FK territorio `RESTRICT`; `geom MULTIPOLYGON` GiST; `CHECK cadence_days 5–365`, `CHECK area_km2 > 0`; único (territorio, nombre). Contención en el territorio validada en el servicio (≥ 95 %, recorte) |
| `satellite_sources` | Catálogo de fuentes | `slug` único; `requires_credentials`, `enabled` |
| `satellite_scenes` | Inventario de escenas usadas | `scene_id` único; `assets jsonb` solo con **URLs remotas** |
| `model_versions` | Registro de detectores | único (`detector_id`, `version`); `CHECK kind IN ('rule-based','deep-learning')`; `metrics jsonb` |
| `processing_jobs` | Análisis | `CHECK` ventanas ordenadas y referencia < observación; `CHECK progress 0–1`; **índice único parcial** `uq_active_job_per_window` (zona + 4 fechas) `WHERE status IN ('queued','running')` |
| `job_scenes` | Escenas por análisis y periodo | PK compuesta |
| `detection_results` | Resultado de un análisis | 1:1 con job; calidad, áreas, fechas, `artifacts jsonb` (rutas relativas, esquinas), `extent POLYGON` GiST |
| `detected_polygons` | Polígonos de cambio | `geom MULTIPOLYGON` + `centroid POINT` GiST; `CHECK area_ha > 0`, `CHECK score 0–1`; `alert_id` (SET NULL) |
| `alerts` | Hallazgos para revisión | `number` por secuencia → código `FS-AAAA-NNNNN`; `geom`/`centroid` GiST; índice (`status`,`severity`); `CHECK confidence 0–1` |
| `alert_events` | Historial inmutable (revisiones) | tipos `created/redetected/status_changed/comment/notified`; `CHECK char_length(comment) ≤ 4000` |
| `notifications` | Registro de correos | **índice único parcial** (`user_id`,`alert_id`) `WHERE kind='alert'` → nunca dos correos por la misma alerta |
| `reports` | Informes generados | archivo en `DATA_DIR/reports`; acceso solo autor/admin |
| `audit_logs` | Auditoría | acción, recurso, `ip_hash`, `details jsonb` |
| `cookie_consents` | Prueba de consentimiento | `subject_id` aleatorio, versión, `ip_hash` |

## Tipos enumerados

`user_role`, `severity` (low/moderate/high/priority), `change_signal`, `alert_status`, `alert_event_type`, `job_status`, `notification_kind`, `notification_status`, `notification_frequency`, `report_format`. Se crean una sola vez al inicio de la migración (`scripts/fix_enum_migration.py` post-procesa el autogenerado para no duplicar `CREATE TYPE`).

## Consultas geoespaciales clave

- Deduplicación: `ST_Intersects(alerts.geom, :nuevo)` filtrado por zona y `last_detected_at ≥ now − 120 días` (usa GiST).
- Filtro por mapa: `ST_Intersects(alerts.geom, ST_MakeEnvelope(w,s,e,n,4326))`.
- Validación en PostGIS durante el seed: `ST_Within(region.geom, ST_Buffer(territory.geom, 1e-4))`.

## Migraciones

```bash
cd backend
alembic upgrade head                       # aplicar
alembic revision --autogenerate -m "..."   # nueva (revisar SIEMPRE el archivo generado)
alembic downgrade -1                       # revertir
```
El entorno de Alembic **ignora** tablas no declaradas en los modelos: la imagen PostGIS incluye esquemas `tiger`/`topology` que nunca deben tocarse. CI ejecuta `upgrade → downgrade → upgrade`.

## Retención

| Datos | Retención propuesta |
|---|---|
| Sesiones revocadas/caducadas | depuración periódica (> 30 días) |
| `audit_logs`, `cookie_consents` | 5 años |
| `runs/` (rásters de trabajo) | `work/` se puede borrar tras el análisis; conservar PNG de evidencia mientras existan alertas abiertas |
