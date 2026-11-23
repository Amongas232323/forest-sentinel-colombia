"""Dependencias de las peticiones: sesión de BD, autenticación y acceso por roles."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.models.enums import Role
from app.services import auth as auth_service

DB = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user: User
    session_id: uuid.UUID

    @property
    def id(self) -> uuid.UUID:
        return self.user.id

    @property
    def role(self) -> Role:
        return self.user.role


def client_ip(request: Request) -> str:
    # uvicorn --proxy-headers ya resuelve X-Forwarded-For desde los proxies de confianza.
    return request.client.host if request.client else "unknown"


def get_principal(
    db: DB,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise UnauthorizedError("Inicia sesión para continuar.")
    try:
        payload = decode_access_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["sid"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise UnauthorizedError("La sesión no es válida o expiró.", code="invalid_token") from None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("La sesión no es válida o expiró.", code="invalid_token")
    # Las sesiones revocadas (logout, cambio de contraseña) invalidan los access tokens de una.
    if not auth_service.session_is_active(db, session_id):
        raise UnauthorizedError("La sesión fue cerrada.", code="session_revoked")
    return Principal(user, session_id)


CurrentUser = Annotated[Principal, Depends(get_principal)]

# Matriz de permisos — la única fuente de verdad (está documentada en SECURITY.md §3).
PERMISSIONS: dict[str, frozenset[Role]] = {
    "read": frozenset({Role.ADMIN, Role.ANALYST, Role.OBSERVER}),
    "regions:write": frozenset({Role.ADMIN, Role.ANALYST}),
    "regions:delete": frozenset({Role.ADMIN}),
    "jobs:run": frozenset({Role.ADMIN, Role.ANALYST}),
    "alerts:review": frozenset({Role.ADMIN, Role.ANALYST}),
    "alerts:comment": frozenset({Role.ADMIN, Role.ANALYST}),
    "reports:create": frozenset({Role.ADMIN, Role.ANALYST, Role.OBSERVER}),
    "reports:email": frozenset({Role.ADMIN, Role.ANALYST}),
    "users:manage": frozenset({Role.ADMIN}),
    "audit:read": frozenset({Role.ADMIN}),
}


def require(permission: str) -> Callable[[Principal], Principal]:
    allowed = PERMISSIONS[permission]

    def _check(principal: CurrentUser) -> Principal:
        if principal.role not in allowed:
            raise ForbiddenError("No tienes permisos para realizar esta acción.")
        return principal

    return _check
