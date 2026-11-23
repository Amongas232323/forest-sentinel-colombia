"""Estadísticas, reportes, preferencias personales, usuarios, privacidad, auditoría y salud."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, text

from app.api.deps import DB, CurrentUser, Principal, client_ip, require
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import get_limiter
from app.core.security import hash_identifier
from app.models import AuditLog, CookieConsent, MonitoredRegion, Notification, User, UserPreferences
from app.schemas.auth import UserAdminUpdate, UserOut
from app.schemas.common import Message, Page
from app.schemas.domain import (
    AuditOut,
    ConsentIn,
    ConsentOut,
    NotificationOut,
    OverviewOut,
    PreferencesIn,
    PreferencesOut,
    PrivacyInfoOut,
    ReportCreate,
    ReportEmailIn,
    ReportOut,
)
from app.services import audit, notifications, reports, stats
from app.services.auth import revoke_all

router = APIRouter()
Reader = Annotated[Principal, Depends(require("read"))]


# ── Salud ─────────────────────────────────────────────────────────────────────


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", tags=["system"])
def ready(db: DB) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


# ── Estadísticas ──────────────────────────────────────────────────────────────


@router.get("/stats/overview", response_model=OverviewOut, tags=["stats"])
def overview(db: DB, _: Reader) -> OverviewOut:
    return stats.overview(db)


# ── Reportes ──────────────────────────────────────────────────────────────────


def _report_out(r) -> ReportOut:  # type: ignore[no-untyped-def]
    return ReportOut(
        id=r.id,
        format=r.format,
        title=r.title,
        filters=r.filters,
        size_bytes=r.size_bytes,
        alert_count=r.alert_count,
        created_at=r.created_at,
        download_url=f"/api/v1/reports/{r.id}/download",
    )


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED, tags=["reports"])
def create_report(
    data: ReportCreate, request: Request, db: DB, principal: Annotated[Principal, Depends(require("reports:create"))]
) -> ReportOut:
    get_limiter().check("reports", str(principal.id), limit=20, window_s=3600)
    report, _content = reports.create_report(db, principal.user, data.format, data.title, data.filters, client_ip(request))
    return _report_out(report)


@router.get("/reports", response_model=list[ReportOut], tags=["reports"])
def list_reports(db: DB, principal: Reader) -> list[ReportOut]:
    return [_report_out(r) for r in reports.list_reports(db, principal.user)]


@router.get("/reports/{report_id}/download", tags=["reports"])
def download_report(report_id: uuid.UUID, db: DB, principal: Reader) -> FileResponse:
    report, path = reports.get_report_for(db, report_id, principal.user)
    media = "application/pdf" if report.format.value == "pdf" else "text/csv; charset=utf-8"
    return FileResponse(path, media_type=media, filename=report.file_name)


@router.post("/reports/{report_id}/email", response_model=list[NotificationOut], tags=["reports"])
def email_report(
    report_id: uuid.UUID, data: ReportEmailIn, request: Request, db: DB, principal: Annotated[Principal, Depends(require("reports:email"))]
) -> list[NotificationOut]:
    get_limiter().check("reports:email", str(principal.id), limit=20, window_s=3600)
    report, path = reports.get_report_for(db, report_id, principal.user)
    rows = notifications.send_report(db, report, [str(t) for t in data.to], principal.user, path.read_bytes())
    audit.record(
        db,
        "report.emailed",
        actor_id=principal.id,
        resource_type="report",
        resource_id=report.id,
        ip=client_ip(request),
        details={"recipients": len(rows)},
    )
    db.commit()
    return [NotificationOut.model_validate(r) for r in rows]


# ── Yo: preferencias y notificaciones ────────────────────────────────────────


def _prefs_out(user: User, prefs: UserPreferences) -> PreferencesOut:
    return PreferencesOut(
        notify_email=prefs.notify_email,
        notifications_enabled=prefs.notifications_enabled,
        min_severity=prefs.min_severity,
        frequency=prefs.frequency,
        region_ids=list(prefs.region_ids or []),
        signals=list(prefs.signals or []),
        effective_email=prefs.notify_email or user.email,
    )


def _ensure_prefs(db: DB, user: User) -> UserPreferences:
    prefs = db.get(UserPreferences, user.id)
    if prefs is None:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)
        db.flush()
    return prefs


@router.get("/me/preferences", response_model=PreferencesOut, tags=["me"])
def get_preferences(db: DB, principal: CurrentUser) -> PreferencesOut:
    return _prefs_out(principal.user, _ensure_prefs(db, principal.user))


@router.put("/me/preferences", response_model=PreferencesOut, tags=["me"])
def put_preferences(data: PreferencesIn, request: Request, db: DB, principal: CurrentUser) -> PreferencesOut:
    if data.region_ids:
        known = set(db.scalars(select(MonitoredRegion.id).where(MonitoredRegion.id.in_(data.region_ids))))
        if known != set(data.region_ids):
            raise AppError("Alguna de las zonas seleccionadas no existe.", code="unknown_region", status_code=422)
    prefs = _ensure_prefs(db, principal.user)
    prefs.notify_email = str(data.notify_email).lower() if data.notify_email else None
    prefs.notifications_enabled = data.notifications_enabled
    prefs.min_severity = data.min_severity
    prefs.frequency = data.frequency
    prefs.region_ids = list(data.region_ids)
    prefs.signals = [s.value for s in data.signals]
    audit.record(db, "preferences.updated", actor_id=principal.id, ip=client_ip(request), details={"enabled": data.notifications_enabled})
    db.commit()
    return _prefs_out(principal.user, prefs)


@router.get("/me/notifications", response_model=Page[NotificationOut], tags=["me"])
def my_notifications(
    db: DB, principal: CurrentUser, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)
) -> Page[NotificationOut]:
    base = select(Notification).where(Notification.user_id == principal.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return Page(items=[NotificationOut.model_validate(n) for n in rows], total=total, page=page, page_size=page_size)


@router.post("/notifications/unsubscribe", response_model=Message, tags=["me"])
def unsubscribe(request: Request, db: DB, token: str = Query(min_length=40, max_length=100)) -> Message:
    get_limiter().check("unsubscribe", client_ip(request), limit=30, window_s=3600)
    if not notifications.unsubscribe(db, token):
        raise NotFoundError("El enlace no es válido.")
    return Message(message="Listo. Ya no recibirás notificaciones por correo.")


# ── Usuarios (admin) ──────────────────────────────────────────────────────────


@router.get("/users", response_model=list[UserOut], tags=["users"])
def list_users(db: DB, _: Annotated[Principal, Depends(require("users:manage"))]) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in db.scalars(select(User).order_by(User.created_at))]


@router.patch("/users/{user_id}", response_model=UserOut, tags=["users"])
def update_user(
    user_id: uuid.UUID, data: UserAdminUpdate, request: Request, db: DB, principal: Annotated[Principal, Depends(require("users:manage"))]
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("El usuario no existe.")
    if user.id == principal.id and (data.role is not None or data.is_active is False):
        raise AppError("No puedes cambiar tu propio rol ni desactivar tu cuenta.", code="self_modification", status_code=409)
    changes = data.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(user, k, v)
    if data.is_active is False:
        revoke_all(db, user.id)
    audit.record(
        db,
        "user.updated",
        actor_id=principal.id,
        resource_type="user",
        resource_id=user.id,
        ip=client_ip(request),
        details={k: str(v) for k, v in changes.items()},
    )
    db.commit()
    return UserOut.model_validate(user)


# ── Privacidad ────────────────────────────────────────────────────────────────


@router.get("/privacy/info", response_model=PrivacyInfoOut, tags=["privacy"])
def privacy_info() -> PrivacyInfoOut:
    s = get_settings()
    return PrivacyInfoOut(
        controller_name=s.privacy_controller_name,
        controller_id=s.privacy_controller_id,
        contact_email=s.privacy_contact_email,
        policy_version=s.privacy_policy_version,
    )


@router.post("/privacy/consent", response_model=ConsentOut, status_code=status.HTTP_201_CREATED, tags=["privacy"])
def record_consent(data: ConsentIn, request: Request, db: DB) -> ConsentOut:
    get_limiter().check("consent", client_ip(request), limit=30, window_s=3600)
    row = CookieConsent(
        subject_id=data.subject_id,
        necessary=True,
        functional=data.functional,
        analytics=data.analytics,
        policy_version=get_settings().privacy_policy_version,
        ip_hash=hash_identifier(client_ip(request)),
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
    )
    db.add(row)
    db.commit()
    return ConsentOut(
        subject_id=row.subject_id,
        functional=row.functional,
        analytics=row.analytics,
        policy_version=row.policy_version,
        created_at=row.created_at,
    )


@router.get("/privacy/consent/{subject_id}", response_model=ConsentOut, tags=["privacy"])
def latest_consent(subject_id: str, db: DB) -> ConsentOut:
    row = db.scalar(select(CookieConsent).where(CookieConsent.subject_id == subject_id).order_by(CookieConsent.created_at.desc()).limit(1))
    if row is None:
        raise NotFoundError("Sin consentimiento registrado.")
    return ConsentOut(
        subject_id=row.subject_id,
        functional=row.functional,
        analytics=row.analytics,
        policy_version=row.policy_version,
        created_at=row.created_at,
    )


# ── Auditoría (admin) ─────────────────────────────────────────────────────────


@router.get("/audit", response_model=Page[AuditOut], tags=["audit"])
def audit_log(
    db: DB,
    _: Annotated[Principal, Depends(require("audit:read"))],
    action: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[AuditOut]:
    base = select(AuditLog)
    if action:
        base = base.where(AuditLog.action == action)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return Page(items=[AuditOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)
