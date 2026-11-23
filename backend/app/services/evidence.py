"""URLs firmadas y con vencimiento para las imágenes de evidencia (sirven en <img> / fuentes del mapa).

Las imágenes no pueden mandar el header Bearer, entonces la API mete una firma HMAC
atada a (id del resultado, nombre del artefacto, vencimiento). Solo los nombres de
artefacto de la lista blanca apuntan a archivos, así que el endpoint no se puede usar para path traversal.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from pathlib import Path

from app.core.config import get_settings

ARTIFACTS = {"reference": "reference.png", "observation": "observation.png", "overlay": "change_overlay.png"}
TTL_SECONDS = 3600


def _sig(result_id: uuid.UUID, name: str, exp: int) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"evidence:{result_id}:{name}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def signed_url(result_id: uuid.UUID, name: str) -> str:
    exp = (int(time.time()) // 600) * 600 + TTL_SECONDS  # agrupado en buckets → URLs que se pueden cachear
    return f"/api/v1/results/{result_id}/evidence/{name}?exp={exp}&sig={_sig(result_id, name, exp)}"


def verify(result_id: uuid.UUID, name: str, exp: int, sig: str) -> bool:
    if name not in ARTIFACTS or exp < time.time():
        return False
    return hmac.compare_digest(_sig(result_id, name, exp), sig)


def run_dir(job_id: uuid.UUID) -> Path:
    return get_settings().runs_dir / str(job_id)


def artifact_path(job_id: uuid.UUID, name: str) -> Path:
    base = run_dir(job_id).resolve()
    path = (base / ARTIFACTS[name]).resolve()
    if base not in path.parents:
        raise ValueError("artifact outside run directory")
    return path
