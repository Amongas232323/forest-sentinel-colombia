# Forest Sentinel — Guía para ejecutar y entender el proyecto

Esta guía explica, paso a paso y sin rodeos, **qué es** Forest Sentinel, **con qué está hecho**, **cómo funciona por dentro** y **cómo ponerlo a funcionar** en un computador con Windows (los mismos pasos sirven en Linux/macOS con pequeñas diferencias que se indican).

---

## 1. ¿Qué es Forest Sentinel?

Es una plataforma web que **vigila bosques de Colombia usando imágenes de satélite**. Trabaja en cuatro territorios: **Guaviare, Sierra Nevada de Santa Marta, Cundinamarca y Amazonas**.

En pocas palabras:

1. Descarga imágenes reales del satélite europeo **Sentinel-2** de una zona, en dos momentos distintos (un «antes» y un «después»).
2. Compara ambas imágenes píxel por píxel (cada píxel son 10 × 10 metros) y detecta dónde el bosque perdió verdor de forma marcada.
3. Dibuja el contorno de cada área afectada, calcula cuántas hectáreas mide y crea una **alerta**.
4. Muestra la alerta en un mapa, la explica con frases sencillas («Se detectó una posible pérdida de vegetación… 14,9 hectáreas») y **avisa por correo** a quien lo haya pedido.
5. Una persona (un analista) revisa la evidencia y **confirma o descarta** el hallazgo. El sistema nunca declara «deforestación» por sí solo.

---

## 2. Tecnologías usadas

### Lenguajes

| Lenguaje | Dónde se usa | Para qué |
|---|---|---|
| **Python 3.12** | `backend/` y `ml/` | Servidor (API), procesamiento de imágenes satelitales, inteligencia artificial |
| **TypeScript** | `frontend/` | Toda la interfaz web (es JavaScript con tipos, para evitar errores) |
| **SQL** (PostgreSQL + PostGIS) | Base de datos | Guardar usuarios, zonas, alertas y **geometrías** (polígonos en el mapa) |
| **GLSL** | `frontend/src/features/globe/shaders.ts` | Pequeños programas que corren en la tarjeta gráfica para pintar el globo 3D |
| **HTML/CSS** | Interfaz y plantillas de correo | Estructura y estilos (CSS con Tailwind) |
| **YAML / Dockerfile** | `docker-compose.yml`, Dockerfiles, CI | Infraestructura y automatización |

### Backend (el «cerebro» del servidor)

| Tecnología | Función |
|---|---|
| **FastAPI** | Framework que crea la API web (las direcciones `/api/v1/...` que usa la interfaz) |
| **Pydantic** | Valida todos los datos que llegan (fechas, correos, geometrías…) |
| **SQLAlchemy 2 + GeoAlchemy2** | Habla con la base de datos desde Python, incluidas geometrías |
| **Alembic** | Crea y actualiza las tablas de la base de datos (migraciones) |
| **PostgreSQL 16 + PostGIS 3.4** | Base de datos con capacidades geográficas (intersecciones, áreas, índices espaciales) |
| **Celery + Redis** | Ejecuta en segundo plano los análisis satelitales, que tardan minutos, sin bloquear la web |
| **Argon2id + JWT** | Seguridad: contraseñas cifradas y sesiones con tokens que caducan |
| **Jinja2 + SMTP** | Plantillas y envío de correos |
| **ReportLab** | Genera informes PDF |

### Procesamiento satelital e inteligencia artificial (`ml/`)

| Tecnología | Función |
|---|---|
| **pystac-client** | Busca imágenes en el catálogo público **Earth Search** (sin claves) |
| **Rasterio / GDAL** | Lee solo el trozo necesario de cada imagen satelital directamente desde internet |
| **NumPy / OpenCV** | Cálculos sobre las imágenes (índices de vegetación, limpieza de ruido) |
| **Shapely / PyProj** | Convierte las áreas detectadas en polígonos y mide su superficie |
| **PyTorch** | Red neuronal **Siamese U-Net** para detectar cambios (experimental) |

### Frontend (lo que ve el usuario)

| Tecnología | Función |
|---|---|
| **Next.js 15 + React 19** | Estructura de la aplicación web y sus páginas |
| **Tailwind CSS 4** | Estilos visuales (paleta forestal propia) |
| **Three.js + React Three Fiber + Drei** | Globo terrestre 3D y terreno 3D con relieve real |
| **GSAP ScrollTrigger + Framer Motion** | Animaciones al hacer scroll y microinteracciones |
| **MapLibre GL** | Mapas interactivos (explorador y comparador) |
| **TanStack Query + Zustand** | Pedir datos a la API y manejar el estado de la sesión |
| **Zod** | Validar formularios antes de enviarlos |
| **Vitest + Testing Library + axe** | Pruebas automáticas, incluidas pruebas de accesibilidad |

### Infraestructura

**Docker / Docker Compose** (contenedores), **Mailpit** (bandeja de correo de pruebas), **GitHub Actions** (pruebas automáticas en cada cambio).

### Fuentes de datos (todas abiertas)

- **Sentinel-2 L2A Collection-1** (Copernicus/ESA) vía Earth Search en AWS: las imágenes satelitales.
- **OpenStreetMap / geoBoundaries**: límites de los territorios.
- **AWS Terrain Tiles**: elevación del terreno para el 3D.
- **NASA Visible Earth**: textura del globo (solo decorativa).
- **Hansen Global Forest Change**: etiquetas para entrenar la IA.

---

## 3. ¿Cómo funciona? (el recorrido de un análisis)

```
 Usuario (navegador)
      │  1. Elige una zona y dos periodos de fechas → «Lanzar análisis»
      ▼
 Frontend (Next.js) ──► API (FastAPI) ──► guarda el trabajo en PostgreSQL
                                   └──► lo pone en cola (Redis)
                                              │
                                              ▼
                               Worker (Celery) ejecuta el pipeline:
   2. Busca imágenes Sentinel-2 del «antes» y del «después» (las menos nubladas)
   3. Lee solo el pedazo de imagen que cubre la zona
   4. Quita nubes y sombras usando la clasificación de ESA
   5. Combina varias imágenes por periodo (mediana) → imagen limpia
   6. Calcula NDVI (verdor) y NBR (estructura del bosque) antes y después
   7. Marca los píxeles que eran bosque y perdieron mucho verdor
   8. Agrupa esos píxeles en áreas, descarta las menores de 0,5 ha y mide hectáreas
   9. Guarda polígonos y evidencia (imágenes antes/después y máscara de cambio)
  10. Crea alertas (sin duplicar si el área ya tenía una alerta abierta)
  11. Envía un correo a los usuarios suscritos (uno solo por alerta)
                                              │
                                              ▼
 El usuario ve la alerta en el tablero, la compara en el mapa (antes/después
 o terreno 3D) y la confirma o descarta dejando una observación.
```

**Detector usado.** Hoy la plataforma usa un **detector espectral por reglas** (claras, documentadas y auditables). La red neuronal **Siamese U-Net** está entrenada y evaluada con datos reales, pero sus resultados aún no son lo bastante precisos para producción, así que está **desactivada**. La interfaz siempre dice qué método produjo cada alerta y nunca llama «IA» a lo que no lo es.

**Roles de usuario.**

- **Observador**: consulta mapas, alertas e informes.
- **Analista**: además crea zonas, lanza análisis y revisa alertas.
- **Administrador**: además gestiona usuarios y consulta la auditoría.

---

## 4. Paso a paso para ejecutarlo (Windows)

### 4.1 Requisitos (instalar una sola vez)

1. **Docker Desktop**: <https://www.docker.com/products/docker-desktop>. Ábrelo y espera a que diga *Engine running*.
2. **Python 3.12**: <https://www.python.org/downloads/>. Durante la instalación marca *Add Python to PATH*.
3. **Node.js 20 LTS**: <https://nodejs.org>.
4. **Git**: <https://git-scm.com> (incluye *Git Bash*, la terminal recomendada).
5. Conexión a internet: las imágenes satelitales se leen en línea.

Comprueba en una terminal:

```bash
docker --version
python --version
node --version
```

### 4.2 Configurar el proyecto

Abre **Git Bash** en la carpeta del proyecto (`zentinel-pruebaa`):

```bash
cp .env.example .env
```

Abre `.env` con un editor y cambia **todos** los valores que dicen `CHANGE_ME`:

| Variable | Qué poner |
|---|---|
| `POSTGRES_PASSWORD` | Una contraseña inventada para la base de datos (y **la misma** dentro de `DATABASE_URL`) |
| `REDIS_PASSWORD` | Otra contraseña inventada (y **la misma** dentro de `REDIS_URL`) |
| `JWT_SECRET` | Un texto largo y aleatorio. Genéralo con `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` | El correo y la contraseña (mínimo 12 caracteres) del primer administrador |
| `PRIVACY_CONTROLLER_*` | Nombre y datos de la entidad responsable (para la política de privacidad) |

> En Windows usa `127.0.0.1` y no `localhost` en `DATABASE_URL`, `REDIS_URL` y `SMTP_HOST` (ya viene así en la plantilla). Con `localhost`, Windows intenta primero IPv6 y la conexión se queda colgada.

### 4.3 Levantar la base de datos, Redis y el correo de pruebas

```bash
docker compose --profile dev up -d db redis mailpit
```

Esto crea tres contenedores:

- **db**: PostgreSQL con PostGIS, en el puerto 5433.
- **redis**: la cola de trabajos, en el puerto 6380.
- **mailpit**: un buzón falso para ver los correos en <http://localhost:8025>.

### 4.4 Instalar y preparar el backend

```bash
python -m venv .venv
source .venv/Scripts/activate          # en Linux/macOS: source .venv/bin/activate
pip install -e ml -e "backend[dev]"
cd backend
alembic upgrade head                   # crea todas las tablas
python -m app.seed                     # carga los 4 territorios, 4 zonas iniciales, fuentes y el administrador
```

### 4.5 Arrancar los servicios (3 terminales)

Abre **tres terminales** en la carpeta `backend` y activa en cada una el entorno virtual (`source ../.venv/Scripts/activate`):

```bash
# Terminal 1 — API
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Worker que ejecuta los análisis satelitales
celery -A app.worker.celery_app worker --loglevel=INFO --pool=solo

# Terminal 3 (opcional) — Tareas programadas: análisis periódicos y resúmenes por correo
celery -A app.worker.celery_app beat --loglevel=INFO
```

> `--pool=solo` es obligatorio en Windows. En Linux puedes quitarlo.

Comprueba que la API responde abriendo <http://127.0.0.1:8000/api/v1/health>. Debe mostrar `{"status":"ok"}`. La documentación interactiva de la API está en <http://127.0.0.1:8000/api/docs>.

### 4.6 Arrancar la interfaz web

En una **cuarta terminal**:

```bash
cd frontend
npm install
npm run dev
```

Abre **<http://localhost:3000>**. Verás la portada con el globo 3D.

### 4.7 Usarlo por primera vez

1. Pulsa **Iniciar sesión** y entra con el correo y la contraseña de administrador que pusiste en `.env`.
2. Ve a **Zonas**, abre una zona (por ejemplo *Corredor San José del Guaviare – Charras*).
3. En **Nuevo análisis** elige *Temporada seca, año contra año* y pulsa **Lanzar análisis**. Verás el progreso en vivo; tarda entre 1 y 10 minutos.
4. Al terminar, ve a **Alertas** o al **Centro**: aparecen los hallazgos reales. Abre uno para ver la comparación antes/después, el **terreno 3D** y el panel de revisión.
5. En **Notificaciones** activa los correos y revisa los mensajes en <http://localhost:8025>.
6. En **Reportes** genera un PDF o un CSV.

### 4.8 Alternativa: todo con Docker (sin instalar Python ni Node)

```bash
docker compose --profile full up --build
```

Levanta API, worker, programador, web, base de datos y Redis. La web queda en <http://localhost:3000>. La primera construcción tarda varios minutos.

---

## 5. Pruebas automáticas

```bash
cd ml && pytest -q              # 30 pruebas: pipeline, detectores, modelo y entrenamiento
cd backend && pytest -q         # 59 pruebas: API, seguridad, alertas, correos e informes (requiere el contenedor db)
cd frontend && npm test         # 25 pruebas: componentes, formularios, accesibilidad y contrato con la API
cd frontend && npm run lint && npm run typecheck && npm run build
```

---

## 6. Entrenar la red neuronal (opcional, avanzado)

```bash
python -m sentinel_ml.training build --config ml/training/aois.json --out ml/datasets/gfc
python -m sentinel_ml.training train --config ml/training/aois.json --data ml/datasets/gfc --out ml/checkpoints/siamese-unet-0.1.0.pt
python -m sentinel_ml.training.report ml/checkpoints/siamese-unet-0.1.0.metrics.json docs/AI_MODEL_DOCUMENTATION.md
```

La construcción del dataset tarda unos 20–30 minutos y el entrenamiento en CPU unos 30. Para que la plataforma use el modelo, pon `MODEL_CHECKPOINT=ml/checkpoints/siamese-unet-0.1.0.pt` en `.env`. No se recomienda con los resultados actuales (ver `docs/AI_MODEL_DOCUMENTATION.md`).

---

## 7. Problemas frecuentes

| Problema | Solución |
|---|---|
| `failed to connect to the docker API` | Abre Docker Desktop y espera a que el motor esté en marcha |
| La API se queda colgada al conectar a la BD | Usa `127.0.0.1` en lugar de `localhost` en `.env` |
| `Target database is not up to date` | Ejecuta `alembic upgrade head` dentro de `backend/` |
| El análisis queda «En cola» para siempre | El worker de Celery no está corriendo (terminal 2) |
| El worker muestra `invalid username-password pair` | Redis se reinició (por ejemplo, al reiniciar Docker Desktop) mientras el worker conectaba. Cierra el worker y vuelve a arrancarlo |
| El análisis termina sin alertas y con «calidad insuficiente» | Había demasiadas nubes en esas fechas; prueba la temporada seca (diciembre–marzo) |
| No llegan correos | Activa las notificaciones en la página **Notificaciones** y revisa <http://localhost:8025> |
| El mapa o el globo no aparecen | El navegador necesita WebGL activado; sin él se muestra una versión 2D |

---

## 8. Dónde está cada cosa

```
backend/    API, base de datos, alertas, correos, seguridad      → docs/API_DOCUMENTATION.md
ml/         Pipeline satelital e inteligencia artificial         → docs/SATELLITE_PIPELINE.md, docs/AI_MODEL_DOCUMENTATION.md
frontend/   Interfaz web, globo 3D, mapas, comparador            → docs/ARCHITECTURE.md
docs/       Arquitectura, BD, seguridad, privacidad, despliegue, guía de contribución
contracts/  Contratos entre módulos (OpenAPI y esquema del pipeline)
```
