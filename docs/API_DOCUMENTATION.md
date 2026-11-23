# API — Forest Sentinel v1

Base: `/api/v1`. Especificación OpenAPI viva: `GET /api/v1/openapi.json` (Swagger en `/api/docs`, deshabilitado en producción). Los tipos del frontend (`frontend/src/lib/api/types.ts`) son un espejo 1:1 de estos esquemas.

## Convenciones

- JSON UTF-8; fechas ISO 8601 (UTC); geometrías GeoJSON en EPSG:4326 `[lon, lat]`.
- Autenticación: `Authorization: Bearer <access_token>` (15 min). El refresh viaja en la cookie httpOnly `fs_refresh` (`Path=/api/v1/auth`, `SameSite=Strict`).
- Paginación: `?page=1&page_size=20` → `{ items, total, page, page_size }`.
- Errores: siempre el mismo sobre, nunca trazas internas:

```json
{ "error": { "code": "validation_error", "message": "Los datos enviados no son válidos.",
             "details": [{ "field": "email", "message": "value is not a valid email address" }] } }
```

| HTTP | `code` típicos |
|---|---|
| 401 | `unauthorized`, `invalid_token`, `session_revoked`, `invalid_credentials`, `session_expired` |
| 403 | `forbidden` |
| 404 | `not_found` (también para recursos ajenos: evita enumeración/IDOR) |
| 409 | `conflict`, `email_taken`, `job_duplicate`, `invalid_transition`, `region_name_taken` |
| 413 | `payload_too_large` (> 1 MB) |
| 422 | `validation_error`, `outside_territory`, `region_too_large`, `invalid_geometry` |
| 429 | `rate_limited` (cabecera `Retry-After`) |
| 502 | `stac_unavailable` |

## Permisos

| Permiso | Observador | Analista | Admin |
|---|:-:|:-:|:-:|
| Leer territorios, zonas, alertas, resultados, estadísticas | ✔ | ✔ | ✔ |
| Crear informes / descargar los propios | ✔ | ✔ | ✔ |
| Crear/editar zonas, lanzar análisis | | ✔ | ✔ |
| Revisar alertas (estado, observaciones), enviar informes por correo | | ✔ | ✔ |
| Eliminar zonas, gestionar usuarios, leer auditoría | | | ✔ |

La autorización se aplica **en el servidor** (`api/deps.py::require`). La interfaz solo oculta lo que el servidor ya prohíbe.

## Endpoints

### Autenticación
| Método | Ruta | Descripción | Límite |
|---|---|---|---|
| POST | `/auth/register` | `{email, full_name, password, accept_privacy: true}` → usuario observador | 5/h/IP |
| POST | `/auth/login` | `{email, password}` → `{access_token, expires_in, user}` + cookie | 20/5 min/IP, 10/5 min/correo, bloqueo tras 5 fallos (15 min) |
| POST | `/auth/refresh` | Rota el refresh. `204` si no hay sesión. Verifica `Origin` | 60/min |
| POST | `/auth/logout` · `/auth/logout-all` | Revoca la sesión actual / todas | |
| GET | `/auth/me` | Usuario actual | |
| POST | `/auth/password/forgot` | Siempre `202` con el mismo mensaje | 5/h/IP, 3/h/correo |
| POST | `/auth/password/reset` | `{token, password}` (token de un uso, 30 min) | 10/h |
| POST | `/auth/password/change` | Revoca todas las sesiones | |

### Territorios y zonas
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/territories` | Los 4 territorios con conteos de zonas y alertas abiertas |
| GET | `/territories/public` · `/territories/geometries` | Públicos (portada, globo, mapa) |
| GET/POST | `/regions` | Listar (`?territory=`) / crear `{territory_slug, name, geometry, cadence_days}` — la geometría debe estar ≥ 95 % dentro del territorio y medir 1–2 500 km² |
| GET/PATCH/DELETE | `/regions/{id}` | Detalle, editar (`name, description, cadence_days, is_active`), eliminar (admin) |
| GET | `/regions/{id}/scenes?start&end&max_cloud` | Escenas Sentinel-2 disponibles (consulta STAC en vivo, 20/min) |

### Análisis y resultados
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/regions/{id}/jobs` | `{reference_start, reference_end, observation_start, observation_end}` → `202` (10/h). Reglas: referencia < observación, ≥ 2017-01-01, ≤ hoy, cada periodo ≤ 180 días |
| GET | `/jobs` · `/jobs/{id}` | Historial (`?region_id=`) y estado (`stage`, `progress`, `error`) |
| GET | `/results/{id}` | Calidad, áreas, escenas usadas, detector, evidencia firmada |
| GET | `/results/{id}/polygons` | GeoJSON FeatureCollection de polígonos de cambio |
| GET | `/results/{id}/evidence/{reference|observation|overlay}?exp&sig` | PNG; URL firmada (HMAC), no requiere Bearer |

### Alertas
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/alerts` | Filtros: `status` (múltiple), `severity` (múltiple), `territory`, `region_id`, `date_from`, `date_to`, `bbox=w,s,e,n`; `order=recent|severity|area` |
| GET | `/alerts/geojson` | Mismos filtros, para el mapa |
| GET | `/alerts/{id}` | Detalle: geometría, explicación, evidencia, NDVI/NBR, historial, `allowed_transitions` |
| PATCH | `/alerts/{id}/status` | `{status, comment}` — `comment` obligatorio para `confirmed`/`dismissed` |
| POST | `/alerts/{id}/comments` | `{comment}` (≤ 4 000) |

Flujo de estados: `new → pending_review | in_review | dismissed`; `pending_review → in_review | dismissed`; `in_review → confirmed | dismissed | pending_review`; `confirmed → closed | in_review`; `dismissed → in_review | closed`; `closed → in_review`.

Cada alerta incluye `explanation` en lenguaje natural:

```json
"explanation": {
  "headline": "Se detectó una posible pérdida de vegetación",
  "summary": "El sistema identificó una diferencia importante entre las imágenes satelitales del 29 de febrero de 2024 y el 13 de febrero de 2025.",
  "area_text": "Área estimada afectada: 14,9 hectáreas (≈ 21 canchas de fútbol)",
  "confidence_text": "Intensidad de la señal: alta. Detectado por análisis espectral por reglas (no IA). No es una probabilidad calibrada.",
  "caveat": "Una pérdida de vegetación no siempre es deforestación: …"
}
```

### Estadísticas, informes, preferencias
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/stats/overview` | Indicadores del tablero, calculados desde la BD |
| POST | `/reports` | `{format: csv|pdf, title, filters}` (20/h) |
| GET | `/reports` · `/reports/{id}/download` | Solo propios (admin: todos) |
| POST | `/reports/{id}/email` | `{to: [≤10 correos]}` (analista) |
| GET/PUT | `/me/preferences` | Notificaciones: activación, correo, severidad mínima, frecuencia, zonas, tipos |
| GET | `/me/notifications` | Historial de envíos |
| POST | `/notifications/unsubscribe?token=` | Baja con token HMAC (sin sesión) |

### Administración, privacidad, salud
| Método | Ruta | Descripción |
|---|---|---|
| GET · PATCH | `/users` · `/users/{id}` | `{role, is_active}`; no se puede modificar a sí mismo |
| GET | `/audit?action=` | Registro de auditoría |
| GET | `/privacy/info` | Responsable y versión de la política |
| POST · GET | `/privacy/consent` · `/privacy/consent/{subject_id}` | Prueba de consentimiento de cookies |
| GET | `/sources` | Fuentes satelitales y su estado de integración |
| GET | `/health` · `/health/ready` | Vida y disponibilidad (BD) |
