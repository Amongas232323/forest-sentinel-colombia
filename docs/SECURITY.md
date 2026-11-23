# Seguridad

Referencias: OWASP Top 10 (2021), OWASP API Security Top 10 (2023), NIST SP 800-63B, OWASP ASVS 4.0 (nivel 2 como objetivo).

## 1. Activos y amenazas

| Activo | Amenaza principal | Impacto |
|---|---|---|
| Cuentas y sesiones | Fuerza bruta, robo de token, XSS | Suplantación, revisión fraudulenta de alertas |
| Decisiones sobre alertas | Modificación no autorizada, repudio | Pérdida de confianza en los hallazgos |
| Ubicación de hallazgos | Exposición pública | Riesgo para personas o comunidades asociadas a un predio |
| Infraestructura (BD, worker) | SSRF vía STAC, archivos maliciosos, agotamiento de recursos | Acceso interno, caída del servicio |
| Correo | Envío masivo, phishing con enlaces de la plataforma | Reputación, spam |

## 2. Controles implementados

### Autenticación (A07)
- Contraseñas **Argon2id** (m=64 MiB, t=3, p=1) con re-hash automático si cambian los parámetros; mínimo 12 caracteres, bloqueo de contraseñas triviales (NIST 800-63B: longitud sobre composición).
- Hash ficticio para igualar tiempos cuando el usuario no existe; mensajes idénticos para correo inexistente / contraseña errónea / cuenta bloqueada.
- **Bloqueo temporal** tras `LOGIN_MAX_ATTEMPTS` (5) fallos durante `LOGIN_LOCKOUT_MINUTES` (15), más límites por IP y por correo.
- **Access token** JWT HS256 de 15 min, solo en memoria del navegador. **Refresh token** opaco (384 bits) en cookie `httpOnly; SameSite=Strict; Path=/api/v1/auth; Secure` (en staging/producción), almacenado como HMAC-SHA256.
- **Rotación** en cada uso y **detección de reutilización**: presentar un refresh ya rotado revoca la familia completa (OAuth 2.0 Security BCP §4.14).
- Cerrar sesión, cambiar o restablecer la contraseña y desactivar un usuario **revocan las sesiones** y los access tokens dejan de valer de inmediato (cada petición verifica que la sesión siga activa).
- Restablecimiento: token de un solo uso, 30 min, respuesta idéntica exista o no la cuenta.

### Autorización (A01, API1/API5)
- Matriz única de permisos en `backend/app/api/deps.py` aplicada en **cada endpoint** con `Depends(require(...))`.
- **IDOR**: informes y notificaciones se filtran por propietario; un recurso ajeno responde `404` (no `403`) para no revelar su existencia.
- **Asignación masiva**: todos los esquemas Pydantic usan `extra="forbid"` (p. ej., no se puede enviar `role` al registrarse; probado).
- Un administrador no puede cambiar su propio rol ni desactivarse.

### Validación de entradas (A03, API8)
- Pydantic estricto (tipos, longitudes, patrones, rangos de fechas); geometrías validadas con Shapely (válidas, WGS84, ≤ 5 000 vértices) y contenidas en un territorio.
- SQL solo vía SQLAlchemy con parámetros enlazados; sin SQL concatenado.
- **CSV injection** neutralizada (prefijo `'` en celdas que empiezan por `= + - @`).
- Cuerpos > 1 MB rechazados (`413`).

### Protección de la API (API4, API6)
- **Rate limiting** con Redis (ventana fija): global 600/min/IP y límites específicos para login, registro, restablecimiento, refresh, STAC, análisis e informes. Si Redis cae, los buckets de autenticación **fallan cerrados**.
- CORS restrictivo (lista explícita de orígenes; `https` obligatorio en producción, validado al arrancar).
- **CSRF**: cookies `SameSite=Strict` + verificación de `Origin` en `/auth/refresh`; las demás rutas usan Bearer (inmune a CSRF).
- Índice único parcial impide análisis duplicados simultáneos (consumo de recursos).

### SSRF y archivos externos (API7, A10)
- El pipeline solo lee de **hosts en lista blanca** (`ALLOWED_ASSET_HOSTS`), solo `https`, solo `.tif`. Probado contra `169.254.169.254`, `file://`, `http://` y hosts arbitrarios.
- Los checkpoints se cargan con `torch.load(weights_only=True)` y un campo `format` obligatorio (sin deserialización arbitraria).
- La evidencia se sirve por **nombres en lista blanca** (no rutas) con verificación `base in path.parents`; URL firmadas HMAC con caducidad.
- Límites de AOI (área y píxeles), tiempo máximo por análisis y límites duros de Celery; Celery solo acepta JSON (nunca *pickle*).

### Frontend (A03/A05)
- **CSP con nonce** por petición (`script-src 'self' 'nonce-…' 'strict-dynamic'`), `object-src 'none'`, `frame-ancestors 'none'`, `connect-src` limitado al propio origen y a los proveedores de teselas.
- React escapa todo el contenido; no se usa `dangerouslySetInnerHTML`. Los comentarios con HTML se almacenan literalmente y se muestran como texto (probado).
- Redirecciones post-login solo a rutas relativas (sin *open redirect*).
- Ningún secreto en el bundle: el navegador solo conoce rutas relativas `/api/v1`.

### Cabeceras y transporte
API: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `CORP`, `CSP default-src 'none'`, `Cache-Control: no-store` en `/auth`, **HSTS** en producción. HTTPS obligatorio en producción (ver DEPLOYMENT.md).

### Infraestructura
- Secretos solo por variables de entorno (`.env` en `.gitignore`); el arranque falla en producción si `JWT_SECRET` contiene `CHANGE_ME`.
- Contenedores sin root (`uid 10001`), sistema de archivos de solo lectura, `cap_drop: ALL`, `no-new-privileges`; puertos ligados a `127.0.0.1`.
- Logs estructurados JSON con `request_id`; las IP se guardan **seudonimizadas** (HMAC) en auditoría y consentimientos.
- **Auditoría** de inicio/cierre de sesión, bloqueos, reutilización de tokens, cambios de rol, revisiones de alertas, informes y preferencias.
- CI: `pip-audit` y `npm audit --omit=dev --audit-level=high`.

## 3. Pruebas de seguridad automatizadas

`backend/tests/test_auth.py` y `test_system.py`: enumeración de usuarios, bloqueo, rate limit, rotación y reutilización de refresh, flags de cookie, rechazo de `Origin` ajeno, revocación al cerrar sesión, tokens manipulados, asignación masiva, matriz de permisos, IDOR de informes, firmas de evidencia y *path traversal*, CSV injection, límite de tamaño, cabeceras, errores sin trazas. `ml/tests`: SSRF de activos STAC y formato de checkpoint.

## 4. Riesgos residuales y pendientes

| Riesgo | Mitigación recomendada |
|---|---|
| Sin MFA | Añadir TOTP/WebAuthn para administradores |
| Sin verificación de correo al registrarse | Enviar enlace de verificación antes de activar notificaciones |
| `style-src 'unsafe-inline'` (estilos de MapLibre/Framer Motion) | Aceptado; no permite ejecutar scripts |
| Rate limiting por IP detrás de NAT/proxy | Configurar `--forwarded-allow-ips` solo para el proxy de confianza |
| Backups no automatizados en este repositorio | Ver DEPLOYMENT.md §5 |
| Proveedores de teselas ven la IP del usuario | Documentado en la política de privacidad; se pueden auto-alojar |

## 5. Reporte de vulnerabilidades

Escribe al contacto de seguridad del despliegue (variable `PRIVACY_CONTACT_EMAIL` o el que defina la entidad) sin publicar detalles hasta que exista una corrección.
