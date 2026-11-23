"""Notificaciones, reportes, log de auditoría y registros de consentimiento de cookies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk, pg_enum

from .enums import NotificationKind, NotificationStatus, ReportFormat


class Notification(UUIDPk, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    alert_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"))
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"))
    kind: Mapped[NotificationKind] = mapped_column(pg_enum(NotificationKind, "notification_kind"), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        pg_enum(NotificationStatus, "notification_status"), nullable=False, default=NotificationStatus.PENDING
    )
    to_email: Mapped[str] = mapped_column(String(254), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Nunca le mandamos dos correos al mismo usuario por la misma alerta.
        Index("uq_notification_user_alert", "user_id", "alert_id", unique=True, postgresql_where="kind = 'alert'"),
    )


class Report(UUIDPk, Base):
    __tablename__ = "reports"

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    format: Mapped[ReportFormat] = mapped_column(pg_enum(ReportFormat, "report_format"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    file_name: Mapped[str] = mapped_column(String(128), nullable=False)  # dentro de DATA_DIR/reports
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    alert_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(String(32))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CookieConsent(UUIDPk, Base):
    """Prueba del consentimiento (Ley 1581/2012 art. 9: el responsable tiene que guardar evidencia)."""

    __tablename__ = "cookie_consents"

    subject_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # id anónimo del navegador
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    necessary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    functional: Mapped[bool] = mapped_column(Boolean, nullable=False)
    analytics: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(32))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
