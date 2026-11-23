"""Notificaciones por correo: alertas inmediatas, resúmenes periódicos, reportes y resets.

Garantías:
* un correo por (usuario, alerta) — lo asegura un índice parcial único;
* solo si el usuario lo activa (``notifications_enabled`` viene en False por defecto);
* desuscripción con un clic usando un token HMAC sin estado.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.logging import log
from app.models import Alert, MonitoredRegion, Notification, Report, User, UserPreferences
from app.models.enums import NotificationFrequency, NotificationKind, NotificationStatus, Severity

from . import mailer
from .explain import SEVERITY_LABELS
from .serializers import alert_out


def unsubscribe_token(user_id: uuid.UUID) -> str:
    key = get_settings().jwt_secret.encode()
    sig = hmac.new(key, f"unsubscribe:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{user_id}.{sig}"


def parse_unsubscribe_token(token: str) -> uuid.UUID | None:
    try:
        raw_id, _sig = token.split(".", 1)
        user_id = uuid.UUID(raw_id)
    except ValueError:
        return None
    return user_id if hmac.compare_digest(unsubscribe_token(user_id), token) else None


def unsubscribe_url(user_id: uuid.UUID) -> str:
    return f"{get_settings().public_web_url}/unsubscribe?token={unsubscribe_token(user_id)}"


def _recipient(user: User) -> str:
    prefs = user.preferences
    return (prefs.notify_email if prefs and prefs.notify_email else user.email).lower()


def _matches(prefs: UserPreferences, alert: Alert) -> bool:
    if Severity(alert.severity).rank < Severity(prefs.min_severity).rank:
        return False
    if prefs.region_ids and alert.region_id not in prefs.region_ids:
        return False
    return not (prefs.signals and alert.signal not in prefs.signals)


def _subscribers(db: Session, frequency: NotificationFrequency) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(UserPreferences)
            .options(joinedload(User.preferences))
            .where(User.is_active.is_(True), UserPreferences.notifications_enabled.is_(True), UserPreferences.frequency == frequency)
            .execution_options(populate_existing=True)  # nunca confiamos en preferencias cacheadas
        ).unique()
    )


def _load_alerts(db: Session, ids: Iterable[uuid.UUID]) -> list[Alert]:
    return list(
        db.scalars(
            select(Alert)
            .options(joinedload(Alert.region).joinedload(MonitoredRegion.territory), joinedload(Alert.model_version))
            .where(Alert.id.in_(list(ids)))
        ).unique()
    )


def _deliver(db: Session, row: Notification, mail: mailer.OutgoingEmail) -> bool:
    row.attempts += 1
    try:
        mailer.send(mail)
    except Exception as exc:  # noqa: BLE001 — los errores de SMTP son muchísimos; los registramos y seguimos
        row.status, row.error = NotificationStatus.FAILED, type(exc).__name__
        log.warning("email_failed", notification=str(row.id), error=type(exc).__name__)
        db.commit()
        return False
    row.status, row.sent_at, row.error = NotificationStatus.SENT, datetime.now(UTC), None
    db.commit()
    return True


def notify_new_alerts(db: Session, alert_ids: list[uuid.UUID]) -> int:
    """Manda los correos inmediatos de las alertas recién creadas. Devuelve cuántos correos se enviaron."""
    alerts = _load_alerts(db, alert_ids)
    sent = 0
    for user in _subscribers(db, NotificationFrequency.IMMEDIATE):
        assert user.preferences is not None
        for alert in alerts:
            if not _matches(user.preferences, alert):
                continue
            payload = alert_out(alert)
            subject = f"{SEVERITY_LABELS[alert.severity]} en {payload.region_name}: {payload.explanation.headline.lower()}"
            stmt = (
                insert(Notification)
                .values(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    alert_id=alert.id,
                    kind=NotificationKind.ALERT,
                    to_email=_recipient(user),
                    subject=subject[:255],
                    status=NotificationStatus.PENDING,
                    attempts=0,
                )
                # Predicado literal: PostgreSQL solo usa un índice parcial si el WHERE es literal.
                .on_conflict_do_nothing(index_elements=["user_id", "alert_id"], index_where=text("kind = 'alert'"))
                .returning(Notification.id)
            )
            new_id = db.scalar(stmt)
            db.commit()
            if new_id is None:
                continue  # ya se le notificó sobre esta alerta
            row = db.get(Notification, new_id)
            assert row is not None
            mail = mailer.OutgoingEmail(
                to=row.to_email,
                subject=row.subject,
                template="alert",
                context={
                    "alert": payload.model_dump(mode="json"),
                    "severity_label": SEVERITY_LABELS[alert.severity],
                    "unsubscribe_url": unsubscribe_url(user.id),
                    "subject": row.subject,
                },
                list_unsubscribe=unsubscribe_url(user.id),
            )
            sent += _deliver(db, row, mail)
    return sent


def send_digests(db: Session, frequency: NotificationFrequency, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    span = timedelta(days=1 if frequency == NotificationFrequency.DAILY else 7)
    sent = 0
    for user in _subscribers(db, frequency):
        prefs = user.preferences
        assert prefs is not None
        since = prefs.last_digest_at or (now - span)
        if now - since < span * 0.9:
            continue
        candidates = db.scalars(select(Alert.id).where(Alert.first_detected_at >= since, Alert.first_detected_at < now))
        alerts = [a for a in _load_alerts(db, candidates) if _matches(prefs, a)]
        prefs.last_digest_at = now
        if not alerts:
            db.commit()
            continue
        label = "diario" if frequency == NotificationFrequency.DAILY else "semanal"
        row = Notification(
            user_id=user.id,
            kind=NotificationKind.DIGEST,
            to_email=_recipient(user),
            subject=f"Resumen {label}: {len(alerts)} hallazgo(s) en tus zonas",
        )
        db.add(row)
        db.commit()
        mail = mailer.OutgoingEmail(
            to=row.to_email,
            subject=row.subject,
            template="digest",
            context={
                "alerts": [alert_out(a).model_dump(mode="json") for a in alerts],
                "period_label": label,
                "since": f"{since:%d/%m/%Y}",
                "unsubscribe_url": unsubscribe_url(user.id),
            },
            list_unsubscribe=unsubscribe_url(user.id),
        )
        sent += _deliver(db, row, mail)
    return sent


def send_password_reset(db: Session, user: User, token: str) -> None:
    s = get_settings()
    row = Notification(
        user_id=user.id, kind=NotificationKind.PASSWORD_RESET, to_email=user.email, subject="Restablece tu contraseña de Forest Sentinel"
    )
    db.add(row)
    db.commit()
    mail = mailer.OutgoingEmail(
        to=user.email,
        subject=row.subject,
        template="password_reset",
        context={
            "name": user.full_name,
            "reset_url": f"{s.public_web_url}/reset-password?token={token}",
            "minutes": s.password_reset_minutes,
        },
    )
    _deliver(db, row, mail)


def send_report(db: Session, report: Report, recipients: list[str], sender: User, content: bytes) -> list[Notification]:
    rows: list[Notification] = []
    subtype = "pdf" if report.format.value == "pdf" else "csv"
    maintype = "application" if subtype == "pdf" else "text"
    for to in recipients:
        row = Notification(
            user_id=sender.id,
            report_id=report.id,
            kind=NotificationKind.REPORT,
            to_email=to.lower(),
            subject=f"Informe Forest Sentinel: {report.title}"[:255],
        )
        db.add(row)
        db.commit()
        mail = mailer.OutgoingEmail(
            to=row.to_email,
            subject=row.subject,
            template="report",
            context={"title": report.title, "sender": sender.full_name, "alert_count": report.alert_count},
            attachments=[mailer.Attachment(report.file_name, content, maintype, subtype)],
        )
        _deliver(db, row, mail)
        rows.append(row)
    return rows


def unsubscribe(db: Session, token: str) -> bool:
    user_id = parse_unsubscribe_token(token)
    if user_id is None:
        return False
    prefs = db.get(UserPreferences, user_id)
    if prefs is None:
        return False
    prefs.notifications_enabled = False
    db.commit()
    return True
