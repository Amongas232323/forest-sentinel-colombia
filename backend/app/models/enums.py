from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    OBSERVER = "observer"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Severity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    PRIORITY = "priority"

    @property
    def rank(self) -> int:
        return ["low", "moderate", "high", "priority"].index(self.value)


class ChangeSignal(StrEnum):
    VEGETATION_LOSS = "vegetation_loss"
    POSSIBLE_BURN = "possible_burn"
    POSSIBLE_FLOODING = "possible_flooding"


class AlertStatus(StrEnum):
    NEW = "new"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    CLOSED = "closed"


OPEN_ALERT_STATUSES = (AlertStatus.NEW, AlertStatus.PENDING_REVIEW, AlertStatus.IN_REVIEW, AlertStatus.CONFIRMED)

# Transiciones permitidas en el flujo de revisión (se validan en el servidor).
ALERT_TRANSITIONS: dict[AlertStatus, frozenset[AlertStatus]] = {
    AlertStatus.NEW: frozenset({AlertStatus.PENDING_REVIEW, AlertStatus.IN_REVIEW, AlertStatus.DISMISSED}),
    AlertStatus.PENDING_REVIEW: frozenset({AlertStatus.IN_REVIEW, AlertStatus.DISMISSED}),
    AlertStatus.IN_REVIEW: frozenset({AlertStatus.CONFIRMED, AlertStatus.DISMISSED, AlertStatus.PENDING_REVIEW}),
    AlertStatus.CONFIRMED: frozenset({AlertStatus.CLOSED, AlertStatus.IN_REVIEW}),
    AlertStatus.DISMISSED: frozenset({AlertStatus.IN_REVIEW, AlertStatus.CLOSED}),
    AlertStatus.CLOSED: frozenset({AlertStatus.IN_REVIEW}),
}


class AlertEventType(StrEnum):
    CREATED = "created"
    REDETECTED = "redetected"
    STATUS_CHANGED = "status_changed"
    COMMENT = "comment"
    NOTIFIED = "notified"


class NotificationFrequency(StrEnum):
    IMMEDIATE = "immediate"
    DAILY = "daily"
    WEEKLY = "weekly"


class NotificationKind(StrEnum):
    ALERT = "alert"
    DIGEST = "digest"
    REPORT = "report"
    PASSWORD_RESET = "password_reset"  # noqa: S105 — es la etiqueta del enum, no un secreto


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReportFormat(StrEnum):
    CSV = "csv"
    PDF = "pdf"
