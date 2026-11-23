"""Aplicación de Celery: broker/backend de resultados en Redis y el schedule de beat."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(json=settings.environment != "development")

celery_app = Celery("forest_sentinel", broker=settings.redis_url, backend=settings.redis_url, include=["app.worker.tasks"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],  # nunca usar pickle: los mensajes son entrada no confiable
    result_serializer="json",
    task_acks_late=True,  # si un worker se cae el trabajo se vuelve a entregar; el pipeline retoma los tiles
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=settings.pipeline_max_runtime_s + 60,
    task_time_limit=settings.pipeline_max_runtime_s + 300,
    result_expires=86400,
    timezone="America/Bogota",
    task_always_eager=settings.environment == "test",
    beat_schedule={
        "schedule-due-regions": {"task": "app.worker.tasks.schedule_due_regions", "schedule": crontab(minute=5)},
        "daily-digest": {"task": "app.worker.tasks.send_digests", "schedule": crontab(hour=7, minute=0), "args": ["daily"]},
        "weekly-digest": {
            "task": "app.worker.tasks.send_digests",
            "schedule": crontab(hour=7, minute=30, day_of_week=1),
            "args": ["weekly"],
        },
    },
)
