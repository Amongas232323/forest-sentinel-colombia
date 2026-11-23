"""Territorios, regiones monitoreadas, inventario satelital, trabajos y detecciones."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk, pg_enum

from .enums import ChangeSignal, JobStatus, Severity

# Los índices GiST los crea GeoAlchemy2 automáticamente (spatial_index=True).
MULTIPOLYGON = Geometry("MULTIPOLYGON", srid=4326, spatial_index=True)
POLYGON = Geometry("POLYGON", srid=4326, spatial_index=True)
POINT = Geometry("POINT", srid=4326, spatial_index=True)


class Territory(UUIDPk, Base):
    """Uno de los cuatro territorios del alcance (departamento o área protegida)."""

    __tablename__ = "territories"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # department | protected_area
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    geom: Mapped[Any] = mapped_column(MULTIPOLYGON, nullable=False)
    area_km2: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    license: Mapped[str] = mapped_column(String(64), nullable=False)
    attribution: Mapped[str] = mapped_column(String(255), nullable=False)

    regions: Mapped[list[MonitoredRegion]] = relationship(back_populates="territory")


class MonitoredRegion(UUIDPk, Timestamps, Base):
    """Una zona de monitoreo (≤ límite de AOI del pipeline) que cabe completa dentro de un territorio."""

    __tablename__ = "monitored_regions"

    territory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("territories.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    geom: Mapped[Any] = mapped_column(MULTIPOLYGON, nullable=False)
    area_km2: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cadence_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    territory: Mapped[Territory] = relationship(back_populates="regions")

    __table_args__ = (
        CheckConstraint("cadence_days BETWEEN 5 AND 365", name="cadence_range"),
        CheckConstraint("area_km2 > 0", name="area_positive"),
        UniqueConstraint("territory_id", "name", name="uq_region_name_per_territory"),
    )


class SatelliteSource(UUIDPk, Base):
    __tablename__ = "satellite_sources"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    collection: Mapped[str] = mapped_column(String(120), nullable=False)
    catalog_url: Mapped[str] = mapped_column(String(255), nullable=False)
    license: Mapped[str] = mapped_column(String(255), nullable=False)
    requires_credentials: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class SatelliteScene(UUIDPk, Base):
    __tablename__ = "satellite_scenes"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("satellite_sources.id", ondelete="RESTRICT"), nullable=False)
    scene_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    collection: Mapped[str] = mapped_column(String(64), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    cloud_cover: Mapped[float | None] = mapped_column(Float)
    epsg: Mapped[int] = mapped_column(Integer, nullable=False)
    tile_id: Mapped[str | None] = mapped_column(String(16))
    assets: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)  # solo referencias remotas, nunca píxeles
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelVersion(UUIDPk, Base):
    """Registro de detectores (por reglas o deep learning) y sus métricas."""

    __tablename__ = "model_versions"

    detector_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # rule-based | deep-learning
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    artifact_uri: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("detector_id", "version", name="uq_model_version"),
        CheckConstraint("kind IN ('rule-based', 'deep-learning')", name="kind_values"),
    )


class ProcessingJob(UUIDPk, Base):
    __tablename__ = "processing_jobs"

    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitored_regions.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(pg_enum(JobStatus, "job_status"), nullable=False, default=JobStatus.QUEUED, index=True)
    reference_start: Mapped[date] = mapped_column(Date, nullable=False)
    reference_end: Mapped[date] = mapped_column(Date, nullable=False)
    observation_start: Mapped[date] = mapped_column(Date, nullable=False)
    observation_end: Mapped[date] = mapped_column(Date, nullable=False)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    task_id: Mapped[str | None] = mapped_column(String(64))
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")  # manual | scheduled
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_versions.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    region: Mapped[MonitoredRegion] = relationship()
    model_version: Mapped[ModelVersion | None] = relationship()
    result: Mapped[DetectionResult | None] = relationship(back_populates="job", uselist=False)

    __table_args__ = (
        CheckConstraint("reference_start <= reference_end AND observation_start <= observation_end", name="windows_ordered"),
        CheckConstraint("reference_end < observation_start", name="reference_before_observation"),
        CheckConstraint("progress >= 0 AND progress <= 1", name="progress_range"),
        # Máximo un trabajo activo por región y par de periodos (envíos idempotentes).
        Index(
            "uq_active_job_per_window",
            "region_id",
            "reference_start",
            "reference_end",
            "observation_start",
            "observation_end",
            unique=True,
            postgresql_where="status IN ('queued', 'running')",
        ),
    )


class JobScene(Base):
    __tablename__ = "job_scenes"

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_jobs.id", ondelete="CASCADE"), primary_key=True)
    scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("satellite_scenes.id", ondelete="RESTRICT"), primary_key=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False)  # reference | observation

    scene: Mapped[SatelliteScene] = relationship()


class DetectionResult(UUIDPk, Base):
    __tablename__ = "detection_results"

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitored_regions.id", ondelete="CASCADE"), nullable=False, index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id", ondelete="RESTRICT"), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(8), nullable=False)
    quality_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality_notes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    analysed_area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    changed_area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    reference_valid_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    observation_valid_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    reference_first: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference_last: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_first: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_last: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Rutas relativas dentro de DATA_DIR/runs/<job_id>/ — los rásters viven en disco/almacenamiento de objetos.
    artifacts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    extent: Mapped[Any | None] = mapped_column(POLYGON)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    job: Mapped[ProcessingJob] = relationship(back_populates="result")
    model_version: Mapped[ModelVersion] = relationship()
    polygons: Mapped[list[DetectedPolygon]] = relationship(back_populates="result", cascade="all, delete-orphan")


class DetectedPolygon(UUIDPk, Base):
    __tablename__ = "detected_polygons"

    result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("detection_results.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alerts.id", ondelete="SET NULL"), index=True)
    geom: Mapped[Any] = mapped_column(MULTIPOLYGON, nullable=False)
    centroid: Mapped[Any] = mapped_column(POINT, nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    mean_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[Severity] = mapped_column(pg_enum(Severity, "severity"), nullable=False)
    signal: Mapped[ChangeSignal] = mapped_column(pg_enum(ChangeSignal, "change_signal"), nullable=False)
    mean_ndvi_drop: Mapped[float] = mapped_column(Float, nullable=False)
    mean_nbr_drop: Mapped[float] = mapped_column(Float, nullable=False)
    valid_fraction: Mapped[float] = mapped_column(Float, nullable=False)

    result: Mapped[DetectionResult] = relationship(back_populates="polygons")

    __table_args__ = (
        CheckConstraint("area_ha > 0", name="area_positive"),
        CheckConstraint("mean_score BETWEEN 0 AND 1 AND max_score BETWEEN 0 AND 1", name="score_range"),
    )
