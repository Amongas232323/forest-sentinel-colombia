# Despliegue

## 1. Requisitos

- Servidor Linux con Docker Engine 24+ y Compose v2 (4 vCPU / 8 GB RAM recomendados para el worker).
- Dominio con DNS y certificado TLS (Let's Encrypt).
- Servidor SMTP o proveedor transaccional (SPF, DKIM y DMARC configurados para el dominio de `MAIL_FROM`).
- Salida HTTPS hacia `earth-search.aws.element84.com`, `*.s3.us-west-2.amazonaws.com` y los proveedores de teselas (desde los navegadores).

## 2. Configuración de producción

```bash
cp .env.example .env
```

| Variable | Producción |
|---|---|
| `ENVIRONMENT` | `production` (activa cookies `Secure`, HSTS, oculta `/api/docs`, valida secretos) |
| `JWT_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD` | Aleatorias y distintas |
| `CORS_ORIGINS`, `PUBLIC_WEB_URL` | `https://tu-dominio` |
| `SMTP_*`, `MAIL_FROM` | Credenciales del proveedor; `SMTP_STARTTLS=true` o `SMTP_SSL=true` |
| `DOCKER_SMTP_HOST` | Host SMTP real que usan los contenedores. **Obligatorio**: si queda en Mailpit, la API se niega a arrancar en producción |
| `BOOTSTRAP_ADMIN_*` | Solo para el primer arranque; luego elimínalas |
| `PRIVACY_CONTROLLER_*` | Datos reales del responsable del tratamiento |
| `MODEL_CHECKPOINT` | Vacío (detector por reglas) o ruta a un checkpoint evaluado y aprobado |

Nunca subas `.env` al repositorio; en la nube usa el gestor de secretos del proveedor.

## 3. Arranque

```bash
docker compose --profile full up -d --build
docker compose logs -f api worker
```
El servicio `api` ejecuta `alembic upgrade head` y el seed idempotente antes de arrancar.

## 4. Proxy TLS (Nginx)

Todos los puertos de Compose están ligados a `127.0.0.1`. Publica solo el proxy:

```nginx
server {
  listen 443 ssl http2;
  server_name tu-dominio;
  ssl_certificate     /etc/letsencrypt/live/tu-dominio/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/tu-dominio/privkey.pem;
  client_max_body_size 1m;
  location / {
    proxy_pass http://127.0.0.1:3000;          # Next.js (proxy interno a la API)
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
  }
}
server { listen 80; server_name tu-dominio; return 301 https://$host$request_uri; }
```
Uvicorn corre con `--proxy-headers`; limita `--forwarded-allow-ips` a la IP del proxy para que el rate limiting use la IP real.

## 5. Copias de seguridad y retención

```bash
# Diario (cron): base de datos
docker compose exec -T db pg_dump -U $POSTGRES_USER -Fc $POSTGRES_DB > backups/fs-$(date +%F).dump
# Evidencia y reportes
tar czf backups/data-$(date +%F).tgz -C /var/lib/docker/volumes/forest-sentinel_satdata/_data runs reports
```
Conserva 7 diarias, 4 semanales y 12 mensuales, cifradas y fuera del servidor. **Prueba la restauración** (`pg_restore`) al menos trimestralmente. Depura `runs/*/work/` (rásters intermedios) tras 30 días.

## 6. Observabilidad

- Logs JSON a stdout con `request_id` (API) y eventos `job_*` (worker): envíalos a Loki/ELK/CloudWatch.
- Salud: `GET /api/v1/health` (vida) y `/api/v1/health/ready` (BD). Las imágenes incluyen `HEALTHCHECK`.
- Alertas operativas sugeridas: tasa de `5xx`, trabajos `failed` por hora, cola de Celery > N, correos `failed`.
- Monitoreo de errores (Sentry u otro): se puede añadir con el SDK oficial en `create_app()` y en el worker; no se incluye por defecto para no enviar datos a terceros sin decisión explícita.

## 7. Separación de entornos

`development` → Mailpit, docs abiertas, cookies sin `Secure`. `staging` → igual que producción con datos de prueba. `production` → validaciones de arranque estrictas. Usa bases de datos, secretos y buckets distintos por entorno.

## 8. Actualizaciones

```bash
git pull && docker compose --profile full build && docker compose --profile full up -d
```
Las migraciones se aplican al arrancar `api`. Revisa el changelog de migraciones antes de actualizar producción y ten un backup reciente.
