"""Indicadores del dashboard — cada número se calcula a partir de datos guardados."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alert, DetectionResult, JobScene, MonitoredRegion, ProcessingJob, Territory
from app.models.enums import AlertStatus, JobStatus
from app.schemas.domain import OverviewOut


def overview(db: Session) -> OverviewOut:
    region_count, active, area = db.execute(
        select(
            func.count(MonitoredRegion.id),
            func.count().filter(MonitoredRegion.is_active),
            func.coalesce(func.sum(MonitoredRegion.area_km2), 0.0),
        )
    ).one()
    pending_statuses = (AlertStatus.NEW, AlertStatus.PENDING_REVIEW, AlertStatus.IN_REVIEW)
    total, pending, confirmed, changed = db.execute(
        select(
            func.count(Alert.id),
            func.count().filter(Alert.status.in_(pending_statuses)),
            func.count().filter(Alert.status == AlertStatus.CONFIRMED),
            func.coalesce(func.sum(Alert.area_ha).filter(Alert.status.notin_((AlertStatus.DISMISSED,))), 0.0),
        )
    ).one()
    images = db.scalar(select(func.count(func.distinct(JobScene.scene_id)))) or 0
    running = db.scalar(select(func.count(ProcessingJob.id)).where(ProcessingJob.status.in_((JobStatus.QUEUED, JobStatus.RUNNING)))) or 0
    last_update = db.scalar(select(func.max(ProcessingJob.finished_at)).where(ProcessingJob.status == JobStatus.SUCCEEDED))
    by_severity = {
        str(sev.value if hasattr(sev, "value") else sev): n
        for sev, n in db.execute(select(Alert.severity, func.count()).group_by(Alert.severity))
    }

    regions_per = dict(db.execute(select(MonitoredRegion.territory_id, func.count()).group_by(MonitoredRegion.territory_id)).all())
    alerts_per = {
        tid: (n, area_)
        for tid, n, area_ in db.execute(
            select(
                Alert.territory_id,
                func.count().filter(Alert.status.in_(pending_statuses)),
                func.coalesce(func.sum(Alert.area_ha).filter(Alert.status != AlertStatus.DISMISSED), 0.0),
            ).group_by(Alert.territory_id)
        ).all()
    }
    territories = db.execute(select(Territory.id, Territory.slug, Territory.name).order_by(Territory.name)).all()
    by_territory = [
        {
            "slug": slug,
            "name": name,
            "regions": int(regions_per.get(tid, 0)),
            "open_alerts": int(alerts_per.get(tid, (0, 0.0))[0]),
            "alert_area_ha": round(float(alerts_per.get(tid, (0, 0.0))[1]), 2),
        }
        for tid, slug, name in territories
    ]

    month = func.date_trunc("month", DetectionResult.observation_last)
    monthly = db.execute(
        select(month, func.sum(DetectionResult.changed_area_ha)).where(DetectionResult.quality_ok.is_(True)).group_by(month).order_by(month)
    ).all()

    return OverviewOut(
        monitored_area_km2=round(float(area), 1),
        region_count=int(region_count),
        active_region_count=int(active),
        changed_area_ha=round(float(changed), 2),
        alerts_pending=int(pending),
        alerts_confirmed=int(confirmed),
        alerts_total=int(total),
        images_processed=int(images),
        jobs_running=int(running),
        last_update=last_update,
        by_severity=by_severity,
        by_territory=by_territory,
        monthly_changed_ha=[{"month": m.date().isoformat()[:7], "changed_ha": round(float(v or 0), 2)} for m, v in monthly],
    )
