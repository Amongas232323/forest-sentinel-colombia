"""Tareas en segundo plano. Cada tarea abre su propia sesión de BD."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.logging import log
from app.db.session import get_sessionmaker
from app.models import MonitoredRegion, ProcessingJob
from app.models.enums import JobStatus, NotificationFrequency
from app.services import jobs, notifications

from .celery_app import celery_app


@celery_app.task(name="app.worker.tasks.run_job", bind=True, max_retries=2, default_retry_delay=300)
def run_job(self, job_id: str) -> dict[str, int]:  # type: ignore[no-untyped-def]
    report = jobs.execute_job(uuid.UUID(job_id))
    if report is None:
        return {"created": 0, "updated": 0}
    if report.created:
        notify_alerts.delay([str(a.id) for a in report.created])
    return {"created": len(report.created), "updated": len(report.updated)}


@celery_app.task(name="app.worker.tasks.notify_alerts")
def notify_alerts(alert_ids: list[str]) -> int:
    with get_sessionmaker()() as db:
        return notifications.notify_new_alerts(db, [uuid.UUID(a) for a in alert_ids])


@celery_app.task(name="app.worker.tasks.send_digests")
def send_digests(frequency: str) -> int:
    with get_sessionmaker()() as db:
        return notifications.send_digests(db, NotificationFrequency(frequency))


@celery_app.task(name="app.worker.tasks.retry_failed_notifications")
def retry_failed_notifications() -> int:
    with get_sessionmaker()() as db:
        return notifications.retry_failed(db)


@celery_app.task(name="app.worker.tasks.recover_stale_jobs")
def recover_stale_jobs() -> int:
    """Marca como fallidos los análisis que quedaron en `running` porque el worker murió."""
    with get_sessionmaker()() as db:
        return len(jobs.fail_stale_jobs(db))


@celery_app.task(name="app.worker.tasks.schedule_due_regions")
def schedule_due_regions() -> int:
    """Crea trabajos programados para las regiones activas a las que ya les tocó según su frecuencia."""
    created = 0
    now = datetime.now(UTC)
    with get_sessionmaker()() as db:
        active_job = (
            select(ProcessingJob.id)
            .where(ProcessingJob.region_id == MonitoredRegion.id, ProcessingJob.status.in_((JobStatus.QUEUED, JobStatus.RUNNING)))
            .exists()
        )
        regions = db.scalars(select(MonitoredRegion).where(MonitoredRegion.is_active.is_(True), ~active_job)).all()
        for region in regions:
            if region.last_run_at and region.last_run_at > now - timedelta(days=region.cadence_days):
                continue
            try:
                job = jobs.submit_job(db, region, jobs.default_windows(), actor_id=None, trigger="scheduled")
            except Exception:  # noqa: BLE001 — que falle una región no puede bloquear a las demás
                log.exception("schedule_failed", region=str(region.id))
                db.rollback()
                continue
            run_job.delay(str(job.id))
            created += 1
    return created
