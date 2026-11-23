"""Generación de alertas (filtro de calidad + deduplicación espacio-temporal) y revisión."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from geoalchemy2.functions import ST_Intersects, ST_MakeEnvelope
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.models import Alert, AlertEvent, DetectedPolygon, DetectionResult, MonitoredRegion, Territory
from app.models.enums import ALERT_TRANSITIONS, OPEN_ALERT_STATUSES, AlertEventType, AlertStatus, Severity
from app.schemas.domain import AlertFilters

from . import audit
from .geo import area_ha, as_multipolygon, from_db, to_db

# Una alerta descartada solo se reabre si la perturbación creció al menos esto.
REOPEN_GROWTH = 1.5


@dataclass
class AlertGenerationReport:
    created: list[Alert]
    updated: list[Alert]
    skipped_low_quality: int
    skipped_below_threshold: int


def generate_alerts(db: Session, result: DetectionResult, region: MonitoredRegion, source: str) -> AlertGenerationReport:
    """Convierte los polígonos detectados en alertas. El commit lo hace quien llama."""
    s = get_settings()
    report = AlertGenerationReport([], [], 0, 0)
    if not result.quality_ok:
        report.skipped_low_quality = len(result.polygons)
        return report
    min_rank = Severity(s.alert_min_severity).rank
    region_shape = from_db(region.geom)
    now = datetime.now(UTC)
    for poly in result.polygons:
        if Severity(poly.severity).rank < min_rank:
            report.skipped_below_threshold += 1
            continue
        if poly.valid_fraction < s.alert_min_valid_fraction:
            report.skipped_low_quality += 1
            continue
        clipped = from_db(poly.geom).intersection(region_shape)
        if clipped.is_empty or clipped.area == 0:
            continue
        geom = as_multipolygon(clipped)
        existing = _find_overlapping(db, region.id, geom, now - timedelta(days=s.alert_dedup_days))
        if existing is None:
            alert = _create(db, result, region, poly, geom, source, now)
            report.created.append(alert)
        else:
            _merge(db, existing, result, poly, geom, now)
            report.updated.append(existing)
            alert = existing
        poly.alert_id = alert.id
    return report


def _find_overlapping(db: Session, region_id: uuid.UUID, geom, since: datetime) -> Alert | None:  # type: ignore[no-untyped-def]
    stmt = (
        select(Alert)
        .where(Alert.region_id == region_id, Alert.last_detected_at >= since, ST_Intersects(Alert.geom, to_db(geom)))
        .order_by(Alert.status.in_(OPEN_ALERT_STATUSES).desc(), Alert.last_detected_at.desc())
        .limit(1)
        .with_for_update()
    )
    return db.scalar(stmt)


def _create(db, result, region, poly: DetectedPolygon, geom, source: str, now: datetime) -> Alert:  # type: ignore[no-untyped-def]
    alert = Alert(
        region_id=region.id,
        territory_id=region.territory_id,
        geom=to_db(geom),
        centroid=to_db(geom.centroid),
        area_ha=area_ha(geom),
        severity=poly.severity,
        confidence=poly.mean_score,
        signal=poly.signal,
        status=AlertStatus.NEW,
        reference_date=result.reference_last,
        observation_date=result.observation_last,
        first_detected_at=now,
        last_detected_at=now,
        image_quality=min(result.reference_valid_fraction, result.observation_valid_fraction, poly.valid_fraction),
        source=source,
        model_version_id=result.model_version_id,
        latest_result_id=result.id,
    )
    db.add(alert)
    db.flush()
    db.add(AlertEvent(alert_id=alert.id, type=AlertEventType.CREATED, to_status=AlertStatus.NEW, result_id=result.id))
    return alert


def _merge(db, alert: Alert, result, poly: DetectedPolygon, geom, now: datetime) -> None:  # type: ignore[no-untyped-def]
    merged = as_multipolygon(from_db(alert.geom).union(geom))
    previous_area = alert.area_ha
    alert.geom = to_db(merged)
    alert.centroid = to_db(merged.centroid)
    alert.area_ha = area_ha(merged)
    if Severity(poly.severity).rank > Severity(alert.severity).rank:
        alert.severity = poly.severity
    alert.confidence = max(alert.confidence, poly.mean_score)
    alert.detection_count += 1
    alert.last_detected_at = now
    alert.observation_date = result.observation_last
    alert.latest_result_id = result.id
    alert.model_version_id = result.model_version_id
    from_status = alert.status
    reopened = alert.status in (AlertStatus.DISMISSED, AlertStatus.CLOSED) and alert.area_ha >= previous_area * REOPEN_GROWTH
    if reopened:
        alert.status = AlertStatus.PENDING_REVIEW
    db.add(
        AlertEvent(
            alert_id=alert.id,
            type=AlertEventType.REDETECTED,
            from_status=from_status if reopened else None,
            to_status=alert.status if reopened else None,
            result_id=result.id,
            comment=(
                f"Nueva detección: el área pasó de {previous_area:.1f} ha a {alert.area_ha:.1f} ha."
                + (" Se reabrió para revisión por crecimiento significativo." if reopened else "")
            ),
        )
    )


def change_status(db: Session, alert: Alert, actor_id: uuid.UUID, new_status: AlertStatus, comment: str | None, ip: str | None) -> Alert:
    if new_status not in ALERT_TRANSITIONS[alert.status]:
        raise AppError("Ese cambio de estado no está permitido desde el estado actual.", code="invalid_transition", status_code=409)
    old = alert.status
    alert.status = new_status
    db.add(
        AlertEvent(
            alert_id=alert.id, actor_id=actor_id, type=AlertEventType.STATUS_CHANGED, from_status=old, to_status=new_status, comment=comment
        )
    )
    audit.record(
        db,
        "alert.status_changed",
        actor_id=actor_id,
        resource_type="alert",
        resource_id=alert.id,
        ip=ip,
        details={"from": old.value, "to": new_status.value},
    )
    db.commit()
    return alert


def add_comment(db: Session, alert: Alert, actor_id: uuid.UUID, comment: str) -> AlertEvent:
    ev = AlertEvent(alert_id=alert.id, actor_id=actor_id, type=AlertEventType.COMMENT, comment=comment)
    db.add(ev)
    db.commit()
    return ev


def _base_query() -> Select[tuple[Alert]]:
    return select(Alert).options(
        joinedload(Alert.region).joinedload(MonitoredRegion.territory),
        joinedload(Alert.model_version),
    )


def apply_filters(stmt: Select, f: AlertFilters) -> Select:  # type: ignore[type-arg]
    if f.status:
        stmt = stmt.where(Alert.status.in_(f.status))
    if f.severity:
        stmt = stmt.where(Alert.severity.in_(f.severity))
    if f.territory:
        stmt = stmt.where(Alert.territory_id == select(Territory.id).where(Territory.slug == f.territory).scalar_subquery())
    if f.region_id:
        stmt = stmt.where(Alert.region_id == f.region_id)
    if f.date_from:
        stmt = stmt.where(Alert.last_detected_at >= datetime.combine(f.date_from, datetime.min.time(), UTC))
    if f.date_to:
        stmt = stmt.where(Alert.first_detected_at < datetime.combine(f.date_to + timedelta(days=1), datetime.min.time(), UTC))
    if f.bbox:
        w, s_, e, n = f.bbox
        stmt = stmt.where(ST_Intersects(Alert.geom, ST_MakeEnvelope(w, s_, e, n, 4326)))
    return stmt


def list_alerts(db: Session, f: AlertFilters, page: int, page_size: int, order: str = "recent") -> tuple[list[Alert], int]:
    stmt = apply_filters(_base_query(), f)
    total = db.scalar(apply_filters(select(func.count(Alert.id)), f)) or 0
    ordering = {
        "recent": [Alert.last_detected_at.desc()],
        "severity": [Alert.severity.desc(), Alert.last_detected_at.desc()],
        "area": [Alert.area_ha.desc()],
    }[order]
    rows = db.scalars(stmt.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return list(rows), int(total)


def get_alert(db: Session, alert_id: uuid.UUID) -> Alert:
    alert = db.scalar(_base_query().options(joinedload(Alert.events).joinedload(AlertEvent.actor)).where(Alert.id == alert_id))
    if alert is None:
        raise NotFoundError("La alerta no existe.")
    return alert


def polygon_evidence(db: Session, alert: Alert) -> tuple[float | None, float | None]:
    row = db.execute(
        select(func.avg(DetectedPolygon.mean_ndvi_drop), func.avg(DetectedPolygon.mean_nbr_drop)).where(
            DetectedPolygon.alert_id == alert.id, DetectedPolygon.result_id == alert.latest_result_id
        )
    ).one()
    return (float(row[0]) if row[0] is not None else None, float(row[1]) if row[1] is not None else None)
