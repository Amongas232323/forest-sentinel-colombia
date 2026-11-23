"""Hash de contraseñas (Argon2id), access tokens JWT y refresh tokens opacos."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import get_settings

# Recomendación de OWASP 2024 para Argon2id: m=19 MiB, t=2, p=1 (mínimo);
# nosotros usamos m=64 MiB, t=3, que sigue por debajo de 100 ms en CPUs normales.
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
# Sirve para igualar los tiempos cuando el usuario no existe (enumeración de usuarios).
_DUMMY_HASH = _hasher.hash("forest-sentinel-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID, role: str, session_id: uuid.UUID) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=s.access_token_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "typ": "access",
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), s.access_token_minutes * 60


def decode_access_token(token: str) -> dict[str, Any]:
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub", "sid"]})
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def new_opaque_token() -> str:
    """Token aleatorio seguro para URL, para los links de refresh / reset / desuscripción."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Los tokens se guardan hasheados (con llave) para que si se filtra la BD no se filtren las sesiones."""
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def hash_identifier(value: str) -> str:
    """Seudonimiza IPs y demás datos para los registros de consentimiento / auditoría."""
    return hash_token(f"id:{value}")[:32]
