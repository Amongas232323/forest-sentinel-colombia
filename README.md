# Forest Sentinel

Plataforma web de **detección temprana de cambios en la cobertura forestal** en cuatro territorios de Colombia: Guaviare, Sierra Nevada de Santa Marta, Cundinamarca y Amazonas.
Compara imágenes satelitales **Sentinel-2** de dos periodos, señala dónde disminuyó la vegetación, calcula el área y crea alertas georreferenciadas que una persona confirma o descarta.
Incluye mapa interactivo, comparador antes/después, informes PDF/CSV y avisos por correo.

> ¿Lo acabas de descargar de GitHub? Empieza por la guía [COMO_USAR.md](COMO_USAR.md).

## Requisitos

Para el camino rápido solo necesitas:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (en marcha)
- [Git](https://git-scm.com/downloads)

## Inicio rápido

```powershell
git clone https://github.com/Amongas232323/forest-sentinel-colombia.git forest-sentinel
cd forest-sentinel ; powershell -ExecutionPolicy Bypass -File scripts\setup.ps1     # Windows
# cd forest-sentinel && ./scripts/setup.sh                                          # Linux, macOS o Git Bash
docker compose --profile full up --build
```

1. El script de preparación crea `.env`, genera contraseñas seguras, te pide **solo el correo del administrador** y al final muestra **el correo y la contraseña** para entrar. Guárdalos.
2. La primera construcción tarda varios minutos (descarga PyTorch, PostGIS y dependencias). Las siguientes son rápidas.
3. Cuando en la terminal aparezca `web ... Ready`, abre **http://localhost:3000** e inicia sesión con esas credenciales.

Las migraciones de la base de datos y los datos iniciales (territorios, zonas, fuentes y administrador) se aplican solos al arrancar, mediante el servicio `migrate`.

Para detenerlo: `Ctrl + C` y luego `docker compose --profile full down` (añade `-v` para borrar también los datos).

## Direcciones útiles

| Qué | Dirección |
|---|---|
| Aplicación web | http://localhost:3000 |
| Estado de la API | http://localhost:8000/api/v1/health |
| Documentación de la API (Swagger) | http://localhost:8000/api/docs |
| Mailpit (correos enviados por la app) | http://localhost:8025 |

## Primer uso

1. Entra con el correo y la contraseña que mostró el script.
2. Ve a **Zonas**, abre una zona y en **Nuevo análisis** elige **Temporada seca, año contra año**.
3. Pulsa **Lanzar análisis** y sigue el progreso; tarda entre 1 y 10 minutos según la zona.
4. Las alertas aparecen en **Centro** y **Alertas**; los correos de aviso llegan a Mailpit.

La temporada seca (diciembre a marzo) tiene menos nubes; con otras fechas el análisis puede terminar con «calidad insuficiente» y sin alertas.

## Desarrollo local sin Docker (opcional)

Para trabajar en el código con recarga en caliente. Necesitas Python 3.11+ y **Node 22** (también funciona con Node 20, pero algunas herramientas de diseño exigen 22). La base de datos, Redis y Mailpit siguen en Docker:

```bash
docker compose --profile dev up -d db redis mailpit
```

**PowerShell**

```powershell
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -e ml -e "backend[dev]"
cd backend ; alembic upgrade head ; python -m app.seed
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# otra terminal (en Windows el worker necesita --pool=solo):
cd backend ; ..\.venv\Scripts\Activate.ps1 ; celery -A app.worker.celery_app worker --loglevel=INFO --pool=solo
# otra terminal:
cd frontend ; npm install ; npm run dev
```

**Git Bash**

```bash
python -m venv .venv && source .venv/Scripts/activate      # Linux/macOS: .venv/bin/activate
pip install -e ml -e "backend[dev]"
cd backend && alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# otra terminal:
cd backend && source ../.venv/Scripts/activate && celery -A app.worker.celery_app worker --loglevel=INFO --pool=solo
# otra terminal:
cd frontend && npm install && npm run dev
```

Las pruebas y el estado detallado del proyecto están en [docs/ESTADO_Y_PRUEBAS.md](docs/ESTADO_Y_PRUEBAS.md).

## Problemas frecuentes

**Docker usa `CHANGE_ME` aunque el `.env` está bien.**
Docker Compose da prioridad a las variables definidas en la terminal sobre el `.env`. El script de preparación te avisa si las hay. Para verlas y borrarlas:

```powershell
Get-ChildItem Env: | Where-Object { $_.Value -like "*CHANGE_ME*" }          # verlas
Remove-Item Env:POSTGRES_PASSWORD                                            # borrar en esta sesión
[Environment]::SetEnvironmentVariable("POSTGRES_PASSWORD", $null, "User")    # borrar de forma permanente
```

En Git Bash: `env | grep CHANGE_ME` y `unset POSTGRES_PASSWORD` (quítalas también de `~/.bashrc`). Abre una terminal nueva después.

**`WinError 10013` o «port is already allocated».** Otro proceso usa el puerto (3000, 8000, 5433, 6380, 8025 o 1025):

```powershell
netstat -ano | findstr :8000        # la última columna es el PID
taskkill /PID <PID> /F
```

O cambia el puerto en `.env` (`WEB_PORT`, `API_PORT`, `POSTGRES_PORT`, `REDIS_PORT`, `MAILPIT_UI_PORT`, `MAILPIT_SMTP_PORT`). Si cambias `WEB_PORT`, ajusta también `CORS_ORIGINS` y `PUBLIC_WEB_URL`.

**En Windows, `localhost` falla o va lento al ejecutar sin Docker.** Usa `127.0.0.1` en `DATABASE_URL`, `REDIS_URL` y `API_ORIGIN` (el script ya lo hace): `localhost` puede resolverse a IPv6 (`::1`), donde Docker no escucha.

**Contraseñas con `$`.** Docker Compose interpreta `$` como el inicio de una variable y corta la contraseña. Usa solo letras y números (como las que genera el script) o escribe `$$`.

**«BOOTSTRAP_ADMIN_PASSWORD must have at least 12 characters».** La contraseña del administrador debe tener al menos 12 caracteres. Cámbiala en `.env` y vuelve a arrancar.

**Error 429 («demasiados intentos») al iniciar sesión.** Suele significar que la API no conecta con Redis, donde guarda el límite de intentos. Revisa que el contenedor `redis` esté en marcha (`docker compose ps`) y que `REDIS_PASSWORD` coincida con la que tenía al crearse. Si de verdad fallaste varias veces, espera 15 minutos.

**Cambié contraseñas en `.env` después de crear los contenedores y ya no conecta.** PostgreSQL y Redis guardan la contraseña con la que se crearon. Para recrearlos:

```bash
docker compose --profile full up --build --force-recreate    # conserva los datos (sirve para Redis)
docker compose --profile full down -v                        # borra los datos: PostgreSQL vuelve a crearse con la nueva contraseña
```

## Estructura

| Carpeta | Contenido |
|---|---|
| `backend/` | API FastAPI, modelos PostGIS, migraciones Alembic, tareas Celery, correo e informes |
| `ml/` | Pipeline satelital `sentinel_ml`: lectura Sentinel-2, nubes, composición, detectores y modelo Siamese U-Net |
| `frontend/` | Aplicación web Next.js 15 + React 19 + Tailwind 4 + MapLibre |
| `contracts/` | Contrato OpenAPI y esquema de resultados del pipeline |
| `scripts/` | Preparación del entorno (`setup.ps1`, `setup.sh`) |
| `docs/` | Documentación detallada |

## Documentación

| Documento | Contenido |
|---|---|
| [GUIA_EJECUCION.md](docs/GUIA_EJECUCION.md) | Guía paso a paso para ejecutar y entender el proyecto |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Módulos, flujos y decisiones |
| [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) | Endpoints, permisos y errores |
| [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | Tablas, geometrías e índices |
| [SATELLITE_PIPELINE.md](docs/SATELLITE_PIPELINE.md) | Fuentes y etapas del procesamiento satelital |
| [AI_MODEL_DOCUMENTATION.md](docs/AI_MODEL_DOCUMENTATION.md) | Detectores, modelo, métricas y límites |
| [SECURITY.md](docs/SECURITY.md) | Amenazas y controles |
| [PRIVACY.md](docs/PRIVACY.md) | Ley 1581 de 2012, datos tratados y cookies |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Despliegue en producción |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Cómo contribuir |
| [ESTADO_Y_PRUEBAS.md](docs/ESTADO_Y_PRUEBAS.md) | Estado real, pruebas y créditos de datos |

Contiene información modificada de Copernicus Sentinel (ESA). Créditos completos de datos en [ESTADO_Y_PRUEBAS.md](docs/ESTADO_Y_PRUEBAS.md#créditos-de-datos).
