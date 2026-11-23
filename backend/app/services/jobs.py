"""Trabajos de procesamiento: envío y ejecución del pipeline satelital."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sentinel_ml.composite import RemoteReadTimeoutError
from sentinel_ml.contracts import BBox, DateWindow, PipelineResult, SceneRef
from sentinel_ml.detectors import ChangeDetector, get_detector
from sentinel_ml.grid import AOITooLargeError
from sentinel_ml.pipeline import PipelineTimeoutError, run_pipeline
from shapely.geometry import Point, Polygon, shape
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.logging import log
from app.db.session import get_sessionmaker
from app.models import (
    DetectedPolygon,
    DetectionResult,
    JobScene,
    ModelVersion,
    MonitoredRegion,
    ProcessingJob,
    SatelliteScene,
    SatelliteSource,
)
from app.models.enums import JobStatus
from app.schemas.domain import JobCreate

from . import audit
from .alerts import AlertGenerationReport, generate_alerts
from .evidence import run_dir
from .geo import as_multipolygon, from_db, to_db

COLLECTION_TO_SOURCE = {"sentinel-2-c1-l2a": "earth-search-s2-c1", "sentinel-2-l2a": "earth-search-s2-legacy"}


def submit_job(
    db: Session, region: MonitoredRegion, data: JobCreate, actor_id: uuid.UUID | None, trigger: str = "manual", ip: str | None = None
) -> ProcessingJob:
    if not region.is_active:
        raise AppError("La zona está pausada. Actívala antes de analizarla.", code="region_inactive", status_code=409)
    job = ProcessingJob(
        region_id=region.id,
        reference_start=data.reference_start,
        reference_end=data.reference_end,
        observation_start=data.observation_start,
        observation_end=data.observation_end,
        requested_by_id=actor_id,
        trigger=trigger,
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Ya hay un análisis en curso para esta zona y estas fechas.", code="job_duplicate") from None
    audit.record(
        db,
        "job.submitted",
        actor_id=actor_id,
        resource_type="job",
        resource_id=job.id,
        ip=ip,
        details={"region": str(region.id), "trigger": trigger},
    )
    db.commit()
    return job


def default_windows(today: date | None = None) -> JobCreate:
    """Monitoreo programado: últimos 45 días vs. los 90 días anteriores."""
    today = today or date.today()
    obs_end = today
    obs_start = today - timedelta(days=45)
    ref_end = obs_start - timedelta(days=1)
    ref_start = ref_end - timedelta(days=90)
    return JobCreate(reference_start=ref_start, reference_end=ref_end, observation_start=obs_start, observation_end=obs_end)


def get_job(db: Session, job_id: uuid.UUID) -> ProcessingJob:
    job = db.scalar(
        select(ProcessingJob)
        .options(joinedload(ProcessingJob.region), joinedload(ProcessingJob.model_version), joinedload(ProcessingJob.result))
        .where(ProcessingJob.id == job_id)
    )
    if not job:
        raise NotFoundError("El análisis no existe.")
    return job


def ensure_model_version(db: Session, detector: ChangeDetector, artifact: Path | None) -> ModelVersion:
    mv = db.scalar(select(ModelVersion).where(ModelVersion.detector_id == detector.detector_id, ModelVersion.version == detector.version))
    if mv:
        return mv
    params = detector.parameters()
    mv = ModelVersion(
        detector_id=detector.detector_id,
        version=detector.version,
        kind=detector.kind,
        parameters={k: v for k, v in params.items() if k != "validation_metrics"},
        metrics=params.get("validation_metrics", {}) if isinstance(params.get("validation_metrics"), dict) else {},
        artifact_uri=str(artifact) if artifact and detector.kind == "deep-learning" else None,
    )
    db.add(mv)
    db.flush()
    return mv


class _ProgressWriter:
    """Guarda el progreso del pipeline como mucho cada 2 s usando su propia sesión."""

    def __init__(self, job_id: uuid.UUID) -> None:
        self.job_id = job_id
        self._last = 0.0

    def __call__(self, stage: str, fraction: float) -> None:
        now = time.monotonic()
        if now - self._last < 2 and fraction < 1:
            return
        self._last = now
        with get_sessionmaker()() as db:
            job = db.get(ProcessingJob, self.job_id)
            if job:
                job.stage, job.progress = stage, min(max(fraction, 0.0), 1.0)
                db.commit()


STALE_JOB_MESSAGE = (
    "El análisis se interrumpió porque el proceso que lo ejecutaba se detuvo. "
    "Lánzalo de nuevo: los tiles que ya estaban listos se reutilizan."
)


def stale_job_cutoff_s() -> int:
    """Segundos después de los cuales un trabajo en `running` ya no puede seguir vivo.

    Celery mata la tarea en ``pipeline_max_runtime_s + 300`` (``task_time_limit`` en
    worker/celery_app.py); le damos 5 min más de margen antes de darlo por muerto.
    """
    return get_settings().pipeline_max_runtime_s + 600


def fail_stale_jobs(db: Session, now: datetime | None = None) -> list[uuid.UUID]:
    """Marca como fallidos los trabajos que quedaron en `running` porque el worker murió.

    Si el worker se cae a mitad de un análisis (falta de memoria, reinicio o el límite duro
    de Celery), la tarea se vuelve a entregar pero ``execute_job`` la ignora porque el trabajo
    ya está en `running`. Sin esto el trabajo se quedaba así para siempre y además bloqueaba
    el monitoreo programado de su zona.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(seconds=stale_job_cutoff_s())
    started = func.coalesce(ProcessingJob.started_at, ProcessingJob.created_at)
    stale = db.scalars(
        select(ProcessingJob).where(ProcessingJob.status == JobStatus.RUNNING, started < cutoff).with_for_update(skip_locked=True)
    ).all()
    for job in stale:
        job.status, job.error, job.finished_at = JobStatus.FAILED, STALE_JOB_MESSAGE, now
        log.warning("job_stale_failed", job_id=str(job.id), stage=job.stage, progress=job.progress)
    db.commit()
    return [job.id for job in stale]


USER_ERRORS = {
    AOITooLargeError: "La zona es demasiado grande o pequeña para analizarla en una sola ejecución.",
    PipelineTimeoutError: "El análisis superó el tiempo máximo permitido. Se reanudará en el próximo intento.",
    RemoteReadTimeoutError: "El servidor de imágenes satelitales no respondió a tiempo. Vuelve a lanzar el análisis más tarde.",
}


def execute_job(
    job_id: uuid.UUID, detector: ChangeDetector | None = None, scenes: tuple[list[SceneRef], list[SceneRef]] | None = None
) -> AlertGenerationReport | None:
    """Corre el pipeline para ``job_id``. Se puede reintentar sin problema: los tiles terminados se reutilizan."""
    s = get_settings()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None or job.status not in (JobStatus.QUEUED, JobStatus.FAILED):
            log.info("job_skip", job_id=str(job_id), status=getattr(job, "status", None))
            return None
        region = db.get(MonitoredRegion, job.region_id)
        assert region is not None
        detector = detector or get_detector("auto", s.model_checkpoint)
        mv = ensure_model_version(db, detector, s.model_checkpoint)
        job.status, job.stage, job.progress, job.error = JobStatus.RUNNING, "starting", 0.0, None
        job.started_at = datetime.now(UTC)
        job.model_version_id = mv.id
        db.commit()
        minx, miny, maxx, maxy = from_db(region.geom).bounds
        windows = (
            DateWindow(job.reference_start, job.reference_end),
            DateWindow(job.observation_start, job.observation_end),
        )

    try:
        result = run_pipeline(
            BBox(minx, miny, maxx, maxy),
            windows[0],
            windows[1],
            run_dir(job_id),
            detector,
            reference_scenes=scenes[0] if scenes else None,
            observation_scenes=scenes[1] if scenes else None,
            progress=_ProgressWriter(job_id),
            max_runtime_s=s.pipeline_max_runtime_s,
        )
    except Exception as exc:  # noqa: BLE001 — cualquier fallo tiene que quedar registrado en el trabajo
        message = next(
            (m for t, m in USER_ERRORS.items() if isinstance(exc, t)),
            "El análisis falló por un error interno. El equipo técnico puede revisar los registros.",
        )
        log.exception("job_failed", job_id=str(job_id))
        with SessionLocal() as db:
            job = db.get(ProcessingJob, job_id)
            if job:
                job.status, job.error, job.finished_at = JobStatus.FAILED, message, datetime.now(UTC)
                db.commit()
        return None

    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        region = db.get(MonitoredRegion, job.region_id) if job else None
        assert job is not None and region is not None
        stored = persist_result(db, job, region, mv.id, result)
        source = COLLECTION_TO_SOURCE.get(_collection_of(db, stored.job_id), "earth-search")
        report = generate_alerts(db, stored, region, source)
        job.status, job.stage, job.progress, job.finished_at = JobStatus.SUCCEEDED, "done", 1.0, datetime.now(UTC)
        region.last_run_at = job.finished_at
        db.commit()
        log.info(
            "job_succeeded",
            job_id=str(job_id),
            findings=len(result.findings),
            alerts_created=len(report.created),
            alerts_updated=len(report.updated),
        )
        return report


def _collection_of(db: Session, job_id: uuid.UUID) -> str:
    scene = db.scalar(
        select(SatelliteScene).join(JobScene, JobScene.scene_id == SatelliteScene.id).where(JobScene.job_id == job_id).limit(1)
    )
    return scene.collection if scene else ""


def persist_result(
    db: Session, job: ProcessingJob, region: MonitoredRegion, model_version_id: uuid.UUID, result: PipelineResult
) -> DetectionResult:
    _store_scenes(db, job, result)
    art = result.artifacts
    extent = Polygon(art.corners) if art and art.corners else None
    stored = DetectionResult(
        job_id=job.id,
        region_id=region.id,
        model_version_id=model_version_id,
        contract_version=result.contract_version,
        quality_ok=result.quality_ok,
        quality_notes=result.quality_notes,
        analysed_area_ha=result.analysed_area_ha,
        changed_area_ha=result.changed_area_ha,
        reference_valid_fraction=result.reference.valid_fraction,
        observation_valid_fraction=result.observation.valid_fraction,
        reference_first=result.reference.first_acquired,
        reference_last=result.reference.last_acquired,
        observation_first=result.observation.first_acquired,
        observation_last=result.observation.last_acquired,
        artifacts={"bounds": art.bounds, "corners": art.corners, "files": [art.reference_rgb, art.observation_rgb, art.change_overlay]}
        if art
        else None,
        extent=to_db(extent) if extent else None,
        parameters=result.parameters,
    )
    db.add(stored)
    db.flush()
    for f in result.findings:
        geom = as_multipolygon(shape(f.geometry))
        stored.polygons.append(
            DetectedPolygon(
                geom=to_db(geom),
                centroid=to_db(Point(f.centroid)),
                area_ha=f.area_ha,
                mean_score=min(max(f.mean_score, 0.0), 1.0),
                max_score=min(max(f.max_score, 0.0), 1.0),
                severity=f.severity.value,
                signal=f.signal.value,
                mean_ndvi_drop=f.mean_ndvi_drop,
                mean_nbr_drop=f.mean_nbr_drop,
                valid_fraction=f.valid_fraction,
            )
        )
    db.flush()
    return stored


def _store_scenes(db: Session, job: ProcessingJob, result: PipelineResult) -> None:
    """Hace upsert de las escenas usadas en la ejecución dentro del inventario satelital."""
    inventory_path = run_dir(job.id) / "scenes.json"
    inventory: dict[str, dict] = json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.exists() else {}  # type: ignore[type-arg]
    sources = {src.slug: src for src in db.scalars(select(SatelliteSource))}
    for period, info in (("reference", result.reference), ("observation", result.observation)):
        for sid in info.scene_ids:
            scene = db.scalar(select(SatelliteScene).where(SatelliteScene.scene_id == sid))
            if scene is None:
                meta = inventory.get(sid)
                source = sources.get(COLLECTION_TO_SOURCE.get(meta["collection"], "")) if meta else None
                if meta is None or source is None:
                    log.warning("scene_without_inventory", scene_id=sid)
                    continue
                scene = SatelliteScene(
                    source_id=source.id,
                    scene_id=sid,
                    collection=meta["collection"],
                    acquired_at=datetime.fromisoformat(meta["acquired_at"]),
                    cloud_cover=meta.get("cloud_cover"),
                    epsg=int(meta["epsg"]),
                    tile_id=meta.get("tile_id"),
                    assets=meta.get("assets", {}),
                )
                db.add(scene)
                db.flush()
            db.merge(JobScene(job_id=job.id, scene_id=scene.id, period=period))
