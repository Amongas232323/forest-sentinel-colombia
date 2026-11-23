# Cómo usar Forest Sentinel después de descargarlo

Esta guía es para quien llega al repositorio desde GitHub y quiere ponerlo a correr en su computador, sin tener que conocer el código. Si buscas más detalle técnico, mira el [README](README.md) y la carpeta [docs/](docs/).

---

## 1. Qué necesitas instalar

| Programa | Para qué | Descarga |
|---|---|---|
| **Docker Desktop** | Corre la base de datos, la API, el worker y la web en contenedores | https://www.docker.com/products/docker-desktop/ |
| **Git** (opcional) | Para clonar el repositorio y recibir actualizaciones | https://git-scm.com/downloads |

- Docker Desktop tiene que estar **abierto y en marcha** antes de seguir.
- Recomendado: 8 GB de RAM libres y unos 10 GB de disco (la primera vez se descargan PyTorch, PostGIS y las dependencias).
- Funciona en Windows 10/11, macOS y Linux.

## 2. Descargar el proyecto

**Opción A — con Git (recomendada):**

```bash
git clone https://github.com/Amongas232323/forest-sentinel-colombia.git
cd forest-sentinel-colombia
```

**Opción B — sin Git:** en la página del repositorio pulsa **Code → Download ZIP**, descomprime el archivo y abre una terminal dentro de la carpeta descomprimida.

## 3. Preparar la configuración (solo la primera vez)

El repositorio **no trae contraseñas ni archivo `.env`**: cada persona genera los suyos. Hay un script que lo hace por ti:

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

**Linux, macOS o Git Bash:**

```bash
./scripts/setup.sh
```

El script:

1. Revisa que Docker esté funcionando.
2. Crea el archivo `.env` a partir de la plantilla `.env.example` y genera contraseñas seguras.
3. Te pide **un correo** para la cuenta de administrador.
4. Revisa que los puertos necesarios estén libres.
5. Al final te muestra **el correo y la contraseña del administrador. Guárdalos**, los necesitas para entrar.

> El archivo `.env` es privado: no lo subas a ningún lado ni lo compartas. Ya está excluido de Git.

## 4. Arrancar la aplicación

```bash
docker compose --profile full up --build
```

- La primera vez tarda varios minutos. Las siguientes veces arranca rápido.
- Las migraciones de la base de datos y los datos iniciales (territorios, zonas y administrador) se cargan solos.
- Cuando en la terminal aparezca `web ... Ready`, ya está lista.

Abre en el navegador: **http://localhost:3000**

| Qué | Dirección |
|---|---|
| Aplicación web | http://localhost:3000 |
| Documentación de la API (Swagger) | http://localhost:8000/api/docs |
| Estado de la API | http://localhost:8000/api/v1/health |
| Correos que envía la app (Mailpit) | http://localhost:8025 |

## 5. Primer recorrido

1. **Inicia sesión** con el correo y la contraseña que te mostró el script.
2. Ve a **Zonas** y abre cualquiera de las zonas de los cuatro territorios (Guaviare, Sierra Nevada de Santa Marta, Cundinamarca y Amazonas).
3. En **Nuevo análisis** elige **Temporada seca, año contra año** y pulsa **Lanzar análisis**.
4. Espera a que termine (entre 1 y 10 minutos según la zona). Puedes ver el progreso en **Análisis**.
5. Revisa los resultados:
   - **Centro**: resumen con el globo, indicadores y alertas recientes.
   - **Alertas**: cada cambio detectado, con su área, severidad y ubicación. Desde el detalle puedes ver la imagen de antes y después y **confirmarla o descartarla**.
   - **Explorador**: mapa interactivo para dibujar áreas y ver las detecciones.
   - **Reportes**: descarga en PDF o CSV.
6. Los avisos por correo no salen a internet: llegan a **Mailpit** (http://localhost:8025).

> Consejo: la temporada seca (diciembre a marzo) tiene menos nubes. Con otras fechas el análisis puede terminar como «calidad insuficiente» y sin alertas; eso es normal.

El análisis necesita internet, porque descarga las imágenes de Sentinel-2 desde catálogos públicos.

## 6. Detener, volver a arrancar y borrar

| Acción | Comando |
|---|---|
| Detener | `Ctrl + C` en la terminal y luego `docker compose --profile full down` |
| Volver a arrancar | `docker compose --profile full up` |
| Borrar todo, también los datos | `docker compose --profile full down -v` |

## 7. Actualizar a la última versión

Si lo descargaste con Git:

```bash
git pull
docker compose --profile full up --build
```

Tu `.env` y tus datos se conservan.

## 8. Si algo falla

| Problema | Qué hacer |
|---|---|
| `port is already allocated` o `WinError 10013` | Otro programa usa ese puerto. Cierra ese programa o cambia el puerto en `.env` (`WEB_PORT`, `API_PORT`, etc.). |
| La app usa valores `CHANGE_ME` aunque el `.env` está bien | Hay variables con ese nombre definidas en la terminal; el script te avisa. Ábrela de nuevo después de borrarlas. |
| Error 429 al iniciar sesión | Revisa que el contenedor `redis` esté corriendo (`docker compose ps`). Si fallaste la contraseña varias veces, espera 15 minutos. |
| Cambiaste contraseñas en `.env` y ya no conecta | `docker compose --profile full down -v` y vuelve a arrancar (esto borra los datos). |
| Se me olvidó la contraseña del administrador | Está en tu archivo `.env`, en `BOOTSTRAP_ADMIN_PASSWORD`. |

Hay más casos explicados en la sección **Problemas frecuentes** del [README](README.md#problemas-frecuentes).

## 9. Para seguir aprendiendo

- [Guía de ejecución paso a paso](docs/GUIA_EJECUCION.md)
- [Arquitectura del sistema](docs/ARCHITECTURE.md)
- [Cómo funciona el pipeline satelital](docs/SATELLITE_PIPELINE.md)
- [Modelo de detección y sus límites](docs/AI_MODEL_DOCUMENTATION.md)
- [Cómo contribuir](docs/CONTRIBUTING.md)
