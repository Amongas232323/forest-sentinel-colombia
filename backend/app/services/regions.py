"""Regiones monitoreadas: tienen que estar dentro de uno de los cuatro territorios del alcance."""

from __future__ import annotations

import uuid

from sentinel_ml.config import PipelineLimits
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, ConflictError, NotFoundError
from app.models import Alert, MonitoredRegion, ProcessingJob, Territory
from app.models.enums import OPEN_ALERT_STATUSES
from app.schemas.domain import RegionCreate, RegionUpdate

from . import audit
from .geo import area_km2, as_multipolygon, from_db, to_db

MIN_INSIDE_FRACTION = 0.95
MIN_AREA_KM2 = 1.0


def get_territory(db: Session, slug: str) -> Territory:
    t = db.scalar(select(Territory).where(Territory.slug == slug))
    if t is None:
        raise NotFoundError("Ese territorio no está dentro del alcance de Forest Sentinel.")
    return t


def create_region(db: Session, data: RegionCreate, actor_id: uuid.UUID, ip: str | None) -> MonitoredRegion:
    territory = get_territory(db, data.territory_slug)
    try:
        geom = data.geometry.to_shape()
    except ValueError as exc:
        raise AppError(f"La geometría no es válida: {exc}", code="invalid_geometry", status_code=422) from None
    terr_shape = from_db(territory.geom)
    inside = geom.intersection(terr_shape)
    if geom.area == 0 or inside.area / geom.area < MIN_INSIDE_FRACTION:
        raise AppError(f"La zona debe estar dentro de {territory.name}.", code="outside_territory", status_code=422)
    clipped = as_multipolygon(inside)
    area = area_km2(clipped)
    limit = PipelineLimits().max_aoi_km2
    if area > limit:
        raise AppError(
            f"La zona mide {area:,.0f} km²; el máximo por zona es {limit:,.0f} km². Divídela en zonas más pequeñas.",
            code="region_too_large",
            status_code=422,
        )
    if area < MIN_AREA_KM2:
        raise AppError("La zona es demasiado pequeña (mínimo 1 km²).", code="region_too_small", status_code=422)
    region = MonitoredRegion(
        territory_id=territory.id,
        name=data.name,
        description=data.description,
        geom=to_db(clipped),
        area_km2=area,
        cadence_days=data.cadence_days,
        created_by_id=actor_id,
    )
    db.add(region)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Ya existe una zona con ese nombre en este territorio.", code="region_name_taken") from None
    audit.record(
        db,
        "region.created",
        actor_id=actor_id,
        resource_type="region",
        resource_id=region.id,
        ip=ip,
        details={"territory": territory.slug, "area_km2": round(area, 2)},
    )
    db.commit()
    db.refresh(region)
    return region


def get_region(db: Session, region_id: uuid.UUID) -> MonitoredRegion:
    r = db.scalar(select(MonitoredRegion).options(joinedload(MonitoredRegion.territory)).where(MonitoredRegion.id == region_id))
    if r is None:
        raise NotFoundError("La zona no existe.")
    return r


def update_region(db: Session, region: MonitoredRegion, data: RegionUpdate, actor_id: uuid.UUID, ip: str | None) -> MonitoredRegion:
    changes = data.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(region, k, v)
    try:
        audit.record(db, "region.updated", actor_id=actor_id, resource_type="region", resource_id=region.id, ip=ip, details=changes)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Ya existe una zona con ese nombre en este territorio.", code="region_name_taken") from None
    return region


def delete_region(db: Session, region: MonitoredRegion, actor_id: uuid.UUID, ip: str | None) -> None:
    audit.record(
        db, "region.deleted", actor_id=actor_id, resource_type="region", resource_id=region.id, ip=ip, details={"name": region.name}
    )
    db.delete(region)
    db.commit()


def list_regions(db: Session, territory: str | None = None) -> list[tuple[MonitoredRegion, int, str | None]]:
    open_alerts = (
        select(Alert.region_id, func.count().label("n")).where(Alert.status.in_(OPEN_ALERT_STATUSES)).group_by(Alert.region_id).subquery()
    )
    last_job = select(
        ProcessingJob.region_id,
        ProcessingJob.status,
        func.row_number().over(partition_by=ProcessingJob.region_id, order_by=ProcessingJob.created_at.desc()).label("rn"),
    ).subquery()
    stmt = (
        select(MonitoredRegion, func.coalesce(open_alerts.c.n, 0), last_job.c.status)
        .options(joinedload(MonitoredRegion.territory))
        .outerjoin(open_alerts, open_alerts.c.region_id == MonitoredRegion.id)
        .outerjoin(last_job, (last_job.c.region_id == MonitoredRegion.id) & (last_job.c.rn == 1))
        .order_by(MonitoredRegion.name)
    )
    if territory:
        stmt = stmt.join(Territory, Territory.id == MonitoredRegion.territory_id).where(Territory.slug == territory)
    return [(r, int(n), s) for r, n, s in db.execute(stmt).unique().all()]
