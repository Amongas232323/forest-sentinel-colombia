"""Indirección que usa la API para que los tests puedan interceptar la ejecución de trabajos."""

from __future__ import annotations

import uuid


def enqueue_job(job_id: uuid.UUID) -> None:
    from .tasks import run_job  # se importa de forma perezosa: así el arranque de la API queda liviano

    run_job.delay(str(job_id))
