from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, Sequence, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk, pg_enum

from .enums import AlertEventType, AlertStatus, ChangeSignal, Severity
from .geo import MULTIPOLYGON, POINT, ModelVersion, MonitoredRegion

alert_number_seq = Sequence("alert_number_seq")


class Alert(UUIDPk, Timestamps, Base):
    """Un hallazgo geolocalizado que está esperando revisión humana.

    Una alerta agrupa todas las detecciones de la misma perturbación (la
    deduplicación espacial y temporal está en services/alerts.py).
    """

    __tablename__ = "alerts"

    number: Mapped[int] = mapped_column(Integer, alert_number_seq, server_default=alert_number_seq.next_value(), unique=True)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("monitored_regions.id", ondelete="CASCADE"), nullable=False, index=True)
    territory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("territories.id", ondelete="RESTRICT"), nullable=False, index=True)
    geom: Mapped[Any] = mapped_column(MULTIPOLYGON, nullable=False)
    centroid: Mapped[Any] = mapped_column(POINT, nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[Severity] = mapped_column(pg_enum(Severity, "severity"), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # ordinal de 0..1, OJO: NO está calibrado
    signal: Mapped[ChangeSignal] = mapped_column(pg_enum(ChangeSignal, "change_signal"), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(pg_enum(AlertStatus, "alert_status"), nullable=False, default=AlertStatus.NEW, index=True)
    reference_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    detection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    image_quality: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id", ondelete="RESTRICT"), nullable=False)
    latest_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("detection_results.id", ondelete="RESTRICT"), nullable=False)

    region: Mapped[MonitoredRegion] = relationship()
    model_version: Mapped[ModelVersion] = relationship()
    events: Mapped[list[AlertEvent]] = relationship(back_populates="alert", order_by="AlertEvent.created_at", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("area_ha > 0", name="area_positive"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        Index("ix_alerts_status_severity", "status", "severity"),
    )

    @property
    def code(self) -> str:
        return f"FS-{self.first_detected_at:%Y}-{self.number:05d}" if self.number and self.first_detected_at else "FS-pendiente"


class AlertEvent(UUIDPk, Base):
    """Historial inmutable de una alerta (el rastro de auditoría "alert_reviews")."""

    __tablename__ = "alert_events"

    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[AlertEventType] = mapped_column(pg_enum(AlertEventType, "alert_event_type"), nullable=False)
    from_status: Mapped[AlertStatus | None] = mapped_column(pg_enum(AlertStatus, "alert_status"))
    to_status: Mapped[AlertStatus | None] = mapped_column(pg_enum(AlertStatus, "alert_status"))
    comment: Mapped[str | None] = mapped_column(Text)
    result_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("detection_results.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    alert: Mapped[Alert] = relationship(back_populates="events")
    actor = relationship("User")

    __table_args__ = (CheckConstraint("char_length(comment) <= 4000", name="comment_length"),)
