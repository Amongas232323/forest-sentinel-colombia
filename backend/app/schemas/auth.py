from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.models.enums import Role

from .common import Schema

_COMMON = {"password", "contraseña", "123456789012", "qwertyuiopas", "forestsentinel"}


def validate_password_strength(v: str) -> str:
    """NIST SP 800-63B: mejor longitud que reglas de composición, y bloqueamos las contraseñas obvias."""
    if len(v) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres.")
    if len(v) > 128:
        raise ValueError("La contraseña no puede superar 128 caracteres.")
    if v.lower() in _COMMON or len(set(v)) < 5:
        raise ValueError("La contraseña es demasiado predecible.")
    return v


class RegisterIn(Schema):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str
    accept_privacy: Literal[True] = Field(description="Aceptación explícita de la política de tratamiento de datos")

    @field_validator("password")
    @classmethod
    def _strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        if re.search(r"[<>{}\\]", v):
            raise ValueError("El nombre contiene caracteres no permitidos.")
        return v


class LoginIn(Schema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(Schema):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class TokenOut(Schema):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — tipo de token de OAuth, no es un secreto
    expires_in: int
    user: UserOut


class ForgotPasswordIn(Schema):
    email: EmailStr


class ResetPasswordIn(Schema):
    token: str = Field(min_length=20, max_length=128)
    password: str

    @field_validator("password")
    @classmethod
    def _strength(cls, v: str) -> str:
        return validate_password_strength(v)


class ChangePasswordIn(Schema):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _strength(cls, v: str) -> str:
        return validate_password_strength(v)


class UserAdminUpdate(Schema):
    role: Role | None = None
    is_active: bool | None = None
