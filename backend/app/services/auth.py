"""Autenticación: registro, login con bloqueo por intentos y rotación de refresh tokens."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    hash_identifier,
    hash_password,
    hash_token,
    needs_rehash,
    new_opaque_token,
    verify_password,
)
from app.models import AuthSession, PasswordResetToken, User, UserPreferences
from app.models.enums import Role

from . import audit

GENERIC_LOGIN_ERROR = "Correo o contraseña incorrectos."


@dataclass
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    user: User


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.lower()))


def register(db: Session, email: str, full_name: str, password: str, policy_version: str, ip: str | None) -> User:
    if find_user_by_email(db, email):
        raise ConflictError("Ya existe una cuenta con ese correo.", code="email_taken")
    now = datetime.now(UTC)
    user = User(
        email=email.lower(),
        full_name=full_name,
        password_hash=hash_password(password),
        role=Role.OBSERVER,  # mínimo privilegio; los admins son los que promueven
        privacy_accepted_version=policy_version,
        privacy_accepted_at=now,
    )
    user.preferences = UserPreferences()
    db.add(user)
    db.flush()
    audit.record(db, "user.register", actor_id=user.id, resource_type="user", resource_id=user.id, ip=ip)
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str, ip: str | None) -> User:
    s = get_settings()
    user = find_user_by_email(db, email)
    now = datetime.now(UTC)
    if user and user.locked_until and user.locked_until > now:
        # Mismo mensaje que con credenciales malas; el bloqueo solo se ve por correo o desde el admin.
        verify_password(password, None)
        audit.record(db, "auth.login_locked", actor_id=user.id, ip=ip)
        db.commit()
        raise UnauthorizedError(GENERIC_LOGIN_ERROR, code="invalid_credentials")
    if not user or not verify_password(password, user.password_hash) or not user.is_active:
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= s.login_max_attempts:
                user.locked_until = now + timedelta(minutes=s.login_lockout_minutes)
                user.failed_login_count = 0
                audit.record(db, "auth.lockout", actor_id=user.id, ip=ip)
            audit.record(db, "auth.login_failed", actor_id=user.id, ip=ip)
            db.commit()
        raise UnauthorizedError(GENERIC_LOGIN_ERROR, code="invalid_credentials")
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def issue_session(db: Session, user: User, ip: str | None, user_agent: str | None) -> IssuedTokens:
    s = get_settings()
    refresh = new_opaque_token()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh),
        expires_at=datetime.now(UTC) + timedelta(days=s.refresh_token_days),
        ip_hash=hash_identifier(ip) if ip else None,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    db.flush()
    access, expires = create_access_token(user.id, user.role.value, session.id)
    audit.record(db, "auth.login", actor_id=user.id, resource_type="session", resource_id=session.id, ip=ip)
    db.commit()
    return IssuedTokens(access, expires, refresh, user)


def rotate(db: Session, refresh_token: str, ip: str | None) -> IssuedTokens:
    """Cambia un refresh token por un par nuevo. Si se reutiliza un token que ya
    se rotó se revoca la sesión: eso indica robo (OAuth 2.0 BCP §4.14)."""
    now = datetime.now(UTC)
    token_hash = hash_token(refresh_token)
    session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash).with_for_update())
    if session is None:
        reused = db.scalar(select(AuthSession).where(AuthSession.previous_token_hash == token_hash))
        if reused and reused.revoked_at is None:
            reused.revoked_at = now
            audit.record(db, "auth.refresh_reuse_detected", actor_id=reused.user_id, resource_type="session", resource_id=reused.id, ip=ip)
            db.commit()
        raise UnauthorizedError("La sesión expiró. Inicia sesión de nuevo.", code="session_expired")
    if session.revoked_at or session.expires_at <= now:
        raise UnauthorizedError("La sesión expiró. Inicia sesión de nuevo.", code="session_expired")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        session.revoked_at = now
        db.commit()
        raise UnauthorizedError("La sesión expiró. Inicia sesión de nuevo.", code="session_expired")
    new_refresh = new_opaque_token()
    session.previous_token_hash = token_hash
    session.refresh_token_hash = hash_token(new_refresh)
    session.last_used_at = now
    access, expires = create_access_token(user.id, user.role.value, session.id)
    db.commit()
    return IssuedTokens(access, expires, new_refresh, user)


def revoke_session(db: Session, session_id: uuid.UUID) -> None:
    db.execute(
        update(AuthSession).where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC))
    )
    db.commit()


def revoke_all(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC))
    )


def session_is_active(db: Session, session_id: uuid.UUID) -> bool:
    s = db.get(AuthSession, session_id)
    return bool(s and s.revoked_at is None and s.expires_at > datetime.now(UTC))


def create_password_reset(db: Session, user: User) -> str:
    token = new_opaque_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_minutes),
        )
    )
    db.flush()
    return token


def reset_password(db: Session, token: str, new_password: str, ip: str | None) -> None:
    now = datetime.now(UTC)
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token)).with_for_update())
    if not row or row.used_at or row.expires_at <= now:
        raise UnauthorizedError("El enlace no es válido o ya expiró.", code="invalid_token")
    user = db.get(User, row.user_id)
    if not user:
        raise UnauthorizedError("El enlace no es válido o ya expiró.", code="invalid_token")
    row.used_at = now
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    revoke_all(db, user.id)
    audit.record(db, "auth.password_reset", actor_id=user.id, ip=ip)
    db.commit()


def change_password(db: Session, user: User, current: str, new: str, ip: str | None) -> None:
    if not verify_password(current, user.password_hash):
        raise UnauthorizedError("La contraseña actual no es correcta.", code="invalid_credentials")
    user.password_hash = hash_password(new)
    revoke_all(db, user.id)
    audit.record(db, "auth.password_changed", actor_id=user.id, ip=ip)
    db.commit()
