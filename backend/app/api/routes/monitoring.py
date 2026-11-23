"""Territorios, regiones monitoreadas, escenas satelitales, trabajos y resultados."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse
from sentinel_ml.contracts import BBox, DateWindow
from sentinel_ml.stac import search_scenes
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.api.deps import DB, Principal, client_ip, require
from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import get_limiter
from app.models import Alert, DetectedPolygon, DetectionResult, JobScene, MonitoredRegion, ProcessingJob, SatelliteSource, Territory
from app.models.enums import OPEN_ALERT_STATUSES
from app.schemas.common import Message, Page
from app.schemas.domain import (
    JobCreate,
    JobOut,
    RegionCreate,
    RegionOut,
    RegionUpdate,
    ResultOut,
    SceneOut,
    SourceOut,
    TerritoryGeometryOut,
    TerritoryOut,
)
from app.services import evidence, jobs, regions, serializers
from app.services.geo import from_db, geojson
from app.worker.dispatch import enqueue_job

router = APIRouter(tags=["monitoring"])
Reader = Annotated[Principal, Depends(require("read"))]


# ── Territorios ───────────────────────────────────────────────────────────────


@router.get("/territories", response_model=list[TerritoryOut])
def list_territories(db: DB, _: Reader) -> list[TerritoryOut]:
    region_counts = dict(db.execute(select(MonitoredRegion.territory_id, func.count()).group_by(MonitoredRegion.territory_id)).all())
    alert_counts = dict(
        db.execute(select(Alert.territory_id, func.count()).where(Alert.status.in_(OPEN_ALERT_STATUSES)).group_by(Alert.territory_id)).all()
    )
    return [
        serializers.territory_out(t, region_counts.get(t.id, 0), alert_counts.get(t.id, 0))
        for t in db.scalars(select(Territory).order_by(Territory.name))
    ]


@router.get("/territories/public", response_model=list[TerritoryOut], summary="Territorios en alcance (sin autenticación, para la portada)")
def public_territories(db: DB) -> list[TerritoryOut]:
    return [serializers.territory_out(t) for t in db.scalars(select(Territory).order_by(Territory.name))]


@router.get("/territories/geometries", response_model=list[TerritoryGeometryOut])
def territory_geometries(db: DB) -> list[TerritoryGeometryOut]:
    """Límites públicos simplificados (ODbL) que usan el mapa y el globo 3D."""
    return [TerritoryGeometryOut(slug=t.slug, geometry=geojson(t.geom)) for t in db.scalars(select(Territory))]


# ── Regiones ──────────────────────────────────────────────────────────────────


@router.get("/regions", response_model=list[RegionOut])
def list_regions(db: DB, _: Reader, territory: str | None = Query(default=None, max_length=64)) -> list[RegionOut]:
    return [serializers.region_out(r, n, s) for r, n, s in regions.list_regions(db, territory)]


@router.post("/regions", response_model=RegionOut, status_code=status.HTTP_201_CREATED)
def create_region(
    data: RegionCreate, request: Request, db: DB, principal: Annotated[Principal, Depends(require("regions:write"))]
) -> RegionOut:
    region = regions.create_region(db, data, principal.id, client_ip(request))
    return serializers.region_out(regions.get_region(db, region.id))


@router.get("/regions/{region_id}", response_model=RegionOut)
def get_region(region_id: uuid.UUID, db: DB, _: Reader) -> RegionOut:
    region = regions.get_region(db, region_id)
    n = db.scalar(select(func.count(Alert.id)).where(Alert.region_id == region_id, Alert.status.in_(OPEN_ALERT_STATUSES))) or 0
    last = db.scalar(
        select(ProcessingJob.status).where(ProcessingJob.region_id == region_id).order_by(ProcessingJob.created_at.desc()).limit(1)
    )
    return serializers.region_out(region, n, last)


@router.patch("/regions/{region_id}", response_model=RegionOut)
def update_region(
    region_id: uuid.UUID, data: RegionUpdate, request: Request, db: DB, principal: Annotated[Principal, Depends(require("regions:write"))]
) -> RegionOut:
    region = regions.update_region(db, regions.get_region(db, region_id), data, principal.id, client_ip(request))
    return serializers.region_out(region)


@router.delete("/regions/{region_id}", response_model=Message)
def delete_region(
    region_id: uuid.UUID, request: Request, db: DB, principal: Annotated[Principal, Depends(require("regions:delete"))]
) -> Message:
    regions.delete_region(db, regions.get_region(db, region_id), principal.id, client_ip(request))
    return Message(message="Zona eliminada.")


@router.get(
    "/regions/{region_id}/scenes",
    response_model=list[SceneOut],
    summary="Imágenes Sentinel-2 disponibles (consulta en vivo al catálogo STAC)",
)
def available_scenes(
    region_id: uuid.UUID,
    db: DB,
    principal: Reader,
    start: date = Query(),
    end: date = Query(),
    max_cloud: float = Query(default=60, ge=0, le=100),
) -> list[SceneOut]:
    get_limiter().check("stac", str(principal.id), limit=20, window_s=60)
    if start > end or (end - start).days > 366:
        raise AppError("El rango de fechas debe ser válido y de máximo un año.", code="invalid_range", status_code=422)
    region = regions.get_region(db, region_id)
    minx, miny, maxx, maxy = from_db(region.geom).bounds
    try:
        found = search_scenes(BBox(minx, miny, maxx, maxy), DateWindow(start, end), max_cloud, limit=100)
    except Exception:  # noqa: BLE001 — los fallos del catálogo externo se reportan de forma genérica
        raise AppError(
            "El catálogo satelital no respondió. Inténtalo de nuevo en unos minutos.", code="stac_unavailable", status_code=502
        ) from None
    return [
        SceneOut(scene_id=s.scene_id, collection=s.collection, acquired_at=s.acquired_at, cloud_cover=s.cloud_cover, tile_id=s.tile_id)
        for s in found.scenes
    ]


# ── Trabajos ──────────────────────────────────────────────────────────────────


@router.post("/regions/{region_id}/jobs", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def submit_job(
    region_id: uuid.UUID, data: JobCreate, request: Request, db: DB, principal: Annotated[Principal, Depends(require("jobs:run"))]
) -> JobOut:
    get_limiter().check("jobs", str(principal.id), limit=10, window_s=3600)
    region = regions.get_region(db, region_id)
    job = jobs.submit_job(db, region, data, principal.id, ip=client_ip(request))
    enqueue_job(job.id)
    return serializers.job_out(jobs.get_job(db, job.id))


@router.get("/jobs", response_model=Page[JobOut])
def list_jobs(
    db: DB,
    _: Reader,
    region_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[JobOut]:
    base = select(ProcessingJob)
    if region_id:
        base = base.where(ProcessingJob.region_id == region_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.options(joinedload(ProcessingJob.region), joinedload(ProcessingJob.model_version), joinedload(ProcessingJob.result))
        .order_by(ProcessingJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique()
    return Page(items=[serializers.job_out(j) for j in rows], total=total, page=page, page_size=page_size)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: DB, _: Reader) -> JobOut:
    return serializers.job_out(jobs.get_job(db, job_id))


# ── Resultados y evidencia ────────────────────────────────────────────────────


def _get_result(db: DB, result_id: uuid.UUID) -> DetectionResult:
    r = db.scalar(select(DetectionResult).options(joinedload(DetectionResult.model_version)).where(DetectionResult.id == result_id))
    if r is None:
        raise NotFoundError("El resultado no existe.")
    return r


@router.get("/results/{result_id}", response_model=ResultOut)
def get_result(result_id: uuid.UUID, db: DB, _: Reader) -> ResultOut:
    r = _get_result(db, result_id)
    scenes = db.execute(select(JobScene).options(joinedload(JobScene.scene)).where(JobScene.job_id == r.job_id)).scalars().all()
    count = db.scalar(select(func.count(DetectedPolygon.id)).where(DetectedPolygon.result_id == r.id)) or 0
    return ResultOut(
        id=r.id,
        job_id=r.job_id,
        region_id=r.region_id,
        quality_ok=r.quality_ok,
        quality_notes=r.quality_notes,
        analysed_area_ha=r.analysed_area_ha,
        changed_area_ha=r.changed_area_ha,
        reference_valid_fraction=r.reference_valid_fraction,
        observation_valid_fraction=r.observation_valid_fraction,
        reference_first=r.reference_first,
        reference_last=r.reference_last,
        observation_first=r.observation_first,
        observation_last=r.observation_last,
        created_at=r.created_at,
        model=serializers.model_out(r.model_version),
        evidence=serializers.evidence_out(r),
        polygon_count=count,
        scenes=[
            SceneOut(
                scene_id=js.scene.scene_id,
                collection=js.scene.collection,
                acquired_at=js.scene.acquired_at,
                cloud_cover=js.scene.cloud_cover,
                tile_id=js.scene.tile_id,
            )
            for js in scenes
        ],
    )


@router.get("/results/{result_id}/polygons", summary="Polígonos de cambio (GeoJSON FeatureCollection)")
def result_polygons(result_id: uuid.UUID, db: DB, _: Reader) -> dict[str, Any]:
    _get_result(db, result_id)
    features = [
        {
            "type": "Feature",
            "id": str(p.id),
            "geometry": geojson(p.geom),
            "properties": {
                "area_ha": round(p.area_ha, 3),
                "severity": p.severity,
                "signal": p.signal,
                "mean_score": round(p.mean_score, 3),
                "alert_id": str(p.alert_id) if p.alert_id else None,
            },
        }
        for p in db.scalars(select(DetectedPolygon).where(DetectedPolygon.result_id == result_id))
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/results/{result_id}/evidence/{name}", include_in_schema=False)
def result_evidence(result_id: uuid.UUID, name: str, db: DB, exp: int = Query(), sig: str = Query(max_length=64)) -> FileResponse:
    if not evidence.verify(result_id, name, exp, sig):
        raise NotFoundError("Recurso no disponible.")
    r = _get_result(db, result_id)
    path = evidence.artifact_path(r.job_id, name)
    if not path.is_file():
        raise NotFoundError("Recurso no disponible.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=3000"})


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: DB) -> list[SourceOut]:
    return [SourceOut.model_validate(s) for s in db.scalars(select(SatelliteSource).order_by(SatelliteSource.name))]
