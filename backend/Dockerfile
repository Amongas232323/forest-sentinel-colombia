# syntax=docker/dockerfile:1.7
# Contexto de build: la raíz del repo (necesitamos backend/ y ml/).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Los wheels de rasterio/pyproj ya traen GDAL/PROJ; solo hacen falta las librerías de runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 curl && rm -rf /var/lib/apt/lists/*

# PyTorch solo CPU (únicamente se usa cuando hay un checkpoint entrenado configurado).
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.5.1"

COPY ml/pyproject.toml /app/ml/pyproject.toml
COPY ml/src /app/ml/src
RUN pip install opencv-python-headless==4.10.0.84 && pip install --no-deps /app/ml \
    && pip install "numpy>=1.26" "rasterio>=1.3.9" "shapely>=2.0" "pyproj>=3.6" "pystac-client>=0.8" "pillow>=10"

COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN pip install /app/backend --no-deps || true
RUN pip install "fastapi>=0.115" "uvicorn[standard]>=0.30" "sqlalchemy>=2.0.30" "geoalchemy2>=0.15" "alembic>=1.13" \
    "psycopg[binary]>=3.2" "pydantic>=2.7" "pydantic-settings>=2.3" "email-validator>=2.1" "argon2-cffi>=23.1" "pyjwt>=2.8" \
    "celery[redis]>=5.4" "redis>=5.0" "jinja2>=3.1" "reportlab>=4.2" "structlog>=24.1" "python-multipart>=0.0.9"

COPY backend /app/backend
WORKDIR /app/backend

# Mínimo privilegio: usuario propio sin privilegios; /data es el único volumen donde se puede escribir.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sentinel && mkdir -p /data && chown sentinel:sentinel /data
USER sentinel
ENV DATA_DIR=/data HOME=/home/sentinel
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
