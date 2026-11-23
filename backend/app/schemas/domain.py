"""Contrato de la API para el dominio de monitoreo.

Estos modelos se exportan a OpenAPI (``/api/v1/openapi.json``) y los
tipos del frontend en ``frontend/src/lib/api/types.ts`` los copian 1:1.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import EmailStr, Field, model_validator

from app.models.enums import (
    AlertEventType,
    AlertStatus,
    ChangeSignal,
    JobStatus,
    NotificationFrequency,
    NotificationKind,
    NotificationStatus,
    ReportFormat,
    Severity,
)

from .common import PolygonGeometry, Schema

# ── Territorios y regiones ────────────────────────────────────────────────────


class TerritoryOut(Schema):
    id: uuid.UUID
    slug: str
    name: str
    kind: str
    description: str
    area_km2: float
    attribution: str
    license: str
    centroid: tuple[float, float]
    bbox: tuple[float, float, float, float]
    region_count: int = 0
    open_alerts: int = 0


class TerritoryGeometryOut(Schema):
    slug: str
    geometry: dict[str, Any]


class RegionCreate(Schema):
    territory_slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=2000)
    geometry: PolygonGeometry
    cadence_days: int = Field(default=30, ge=5, le=365)


class RegionUpdate(Schema):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    cadence_days: int | None = Field(default=None, ge=5, le=365)
    is_active: bool | None = None


class RegionOut(Schema):
    id: uuid.UUID
    territory_id: uuid.UUID
    territory_slug: str
    territory_name: str
    name: str
    description: str
    area_km2: float
    is_active: bool
    cadence_days: int
    last_run_at: datetime | None
    created_at: datetime
    centroid: tuple[float, float]
    bbox: tuple[float, float, float, float]
    geometry: dict[str, Any]
    open_alerts: int = 0
    last_job_status: JobStatus | None = None


# ── Escenas, trabajos, resultados ─────────────────────────────────────────────

EARLIEST_DATE = date(2017, 1, 1)
MAX_WINDOW_DAYS = 180


class SceneOut(Schema):
    scene_id: str
    collection: str
    acquired_at: datetime
    cloud_cover: float | None
    tile_id: str | None


class JobCreate(Schema):
    reference_start: date
    reference_end: date
    observation_start: date
    observation_end: date

    @model_validator(mode="after")
    def _windows(self) -> JobCreate:
        today = date.today()
        if self.reference_start > self.reference_end or self.observation_start > self.observation_end:
            raise ValueError("Cada periodo debe empezar antes de terminar.")
        if self.reference_end >= self.observation_start:
            raise ValueError("El periodo de referencia debe ser anterior al de observación.")
        if self.reference_start < EARLIEST_DATE:
            raise ValueError("No hay imágenes Sentinel-2 L2A homogéneas antes de 2017.")
        if self.observation_end > today:
            raise ValueError("El periodo de observación no puede terminar en el futuro.")
        for start, end in ((self.reference_start, self.reference_end), (self.observation_start, self.observation_end)):
            if end - start > timedelta(days=MAX_WINDOW_DAYS):
                raise ValueError(f"Cada periodo puede abarcar como máximo {MAX_WINDOW_DAYS} días.")
        return self


class JobOut(Schema):
    id: uuid.UUID
    region_id: uuid.UUID
    region_name: str
    status: JobStatus
    stage: str
    progress: float
    reference_start: date
    reference_end: date
    observation_start: date
    observation_end: date
    trigger: str
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result_id: uuid.UUID | None
    detector: str | None


class ModelVersionOut(Schema):
    id: uuid.UUID
    detector_id: str
    version: str
    kind: str
    metrics: dict[str, Any]
    created_at: datetime


class EvidenceOut(Schema):
    reference_url: str
    observation_url: str
    overlay_url: str
    corners: list[list[float]]
    bounds: list[float]


class ResultOut(Schema):
    id: uuid.UUID
    job_id: uuid.UUID
    region_id: uuid.UUID
    quality_ok: bool
    quality_notes: list[str]
    analysed_area_ha: float
    changed_area_ha: float
    reference_valid_fraction: float
    observation_valid_fraction: float
    reference_first: datetime
    reference_last: datetime
    observation_first: datetime
    observation_last: datetime
    created_at: datetime
    model: ModelVersionOut
    evidence: EvidenceOut | None
    polygon_count: int
    scenes: list[SceneOut]


# ── Alertas ───────────────────────────────────────────────────────────────────


class Explanation(Schema):
    """Textos en lenguaje sencillo que comparten la UI y los correos (services/explain.py)."""

    headline: str
    summary: str
    area_text: str
    confidence_text: str
    caveat: str


class AlertOut(Schema):
    id: uuid.UUID
    code: str
    region_id: uuid.UUID
    region_name: str
    territory_slug: str
    territory_name: str
    status: AlertStatus
    severity: Severity
    signal: ChangeSignal
    confidence: float
    area_ha: float
    centroid: tuple[float, float]
    reference_date: datetime
    observation_date: datetime
    first_detected_at: datetime
    last_detected_at: datetime
    detection_count: int
    image_quality: float
    detector: str
    detector_kind: str
    explanation: Explanation


class AlertEventOut(Schema):
    id: uuid.UUID
    type: AlertEventType
    from_status: AlertStatus | None
    to_status: AlertStatus | None
    comment: str | None
    actor_name: str | None
    created_at: datetime


class AlertDetail(AlertOut):
    geometry: dict[str, Any]
    source: str
    evidence: EvidenceOut | None
    result_id: uuid.UUID
    mean_ndvi_drop: float | None
    mean_nbr_drop: float | None
    events: list[AlertEventOut]
    allowed_transitions: list[AlertStatus]


class AlertStatusUpdate(Schema):
    status: AlertStatus
    comment: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _comment_required(self) -> AlertStatusUpdate:
        if self.status in (AlertStatus.CONFIRMED, AlertStatus.DISMISSED) and not (self.comment or "").strip():
            raise ValueError("Explica brevemente por qué confirmas o descartas el hallazgo.")
        return self


class AlertCommentIn(Schema):
    comment: str = Field(min_length=1, max_length=4000)


class AlertFilters(Schema):
    status: list[AlertStatus] | None = None
    severity: list[Severity] | None = None
    territory: str | None = None
    region_id: uuid.UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    bbox: tuple[float, float, float, float] | None = None


# ── Estadísticas ──────────────────────────────────────────────────────────────


class OverviewOut(Schema):
    monitored_area_km2: float
    region_count: int
    active_region_count: int
    changed_area_ha: float
    alerts_pending: int
    alerts_confirmed: int
    alerts_total: int
    images_processed: int
    jobs_running: int
    last_update: datetime | None
    by_severity: dict[str, int]
    by_territory: list[dict[str, Any]]
    monthly_changed_ha: list[dict[str, Any]]


# ── Notificaciones, reportes, privacidad ──────────────────────────────────────


class PreferencesIn(Schema):
    notify_email: EmailStr | None = None
    notifications_enabled: bool
    min_severity: Severity
    frequency: NotificationFrequency
    region_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    signals: list[ChangeSignal] = Field(default_factory=list)


class PreferencesOut(PreferencesIn):
    effective_email: str


class NotificationOut(Schema):
    id: uuid.UUID
    kind: NotificationKind
    status: NotificationStatus
    subject: str
    to_email: str
    created_at: datetime
    sent_at: datetime | None
    alert_id: uuid.UUID | None


class ReportCreate(Schema):
    format: ReportFormat
    title: str = Field(default="Informe de hallazgos", min_length=3, max_length=200)
    filters: AlertFilters = Field(default_factory=AlertFilters)


class ReportOut(Schema):
    id: uuid.UUID
    format: ReportFormat
    title: str
    filters: dict[str, Any]
    size_bytes: int
    alert_count: int
    created_at: datetime
    download_url: str


class ReportEmailIn(Schema):
    to: list[EmailStr] = Field(min_length=1, max_length=10)


class ConsentIn(Schema):
    subject_id: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    functional: bool
    analytics: bool


class ConsentOut(Schema):
    subject_id: str
    necessary: Literal[True] = True
    functional: bool
    analytics: bool
    policy_version: str
    created_at: datetime


class PrivacyInfoOut(Schema):
    controller_name: str
    controller_id: str
    contact_email: str
    policy_version: str


class AuditOut(Schema):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    details: dict[str, Any]
    created_at: datetime


class SourceOut(Schema):
    slug: str
    name: str
    provider: str
    collection: str
    license: str
    requires_credentials: bool
    enabled: bool
    notes: str
