"""Configuración centralizada que se carga desde las variables de entorno (.env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Severity = Literal["low", "moderate", "high", "priority"]

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(_REPO_ROOT / ".env",), extra="ignore")

    environment: Literal["development", "staging", "production", "test"] = "development"

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    password_reset_minutes: int = 30

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    public_web_url: str = "http://localhost:3000"
    max_request_bytes: int = 1_000_000

    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = False
    smtp_ssl: bool = False
    mail_from: str = "Forest Sentinel <alertas@example.org>"

    data_dir: Path = _REPO_ROOT / "data"
    model_checkpoint: Path | None = None
    pipeline_max_runtime_s: int = 1800
    alert_min_severity: Severity = "moderate"
    alert_min_valid_fraction: float = 0.6
    alert_dedup_days: int = 120

    privacy_controller_name: str = "No configurado"
    privacy_controller_id: str = "No configurado"
    privacy_contact_email: str = "privacidad@example.org"
    privacy_policy_version: str = "2026-11-12"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("model_checkpoint", mode="before")
    @classmethod
    def _empty_path(cls, v: object) -> object:
        return None if v in ("", None) else v

    @field_validator("data_dir", "model_checkpoint", mode="after")
    @classmethod
    def _anchor_relative(cls, v: Path | None) -> Path | None:
        """Las rutas relativas se resuelven desde la raíz del repo, no desde el CWD."""
        return v if v is None or v.is_absolute() else (_REPO_ROOT / v).resolve()

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.environment == "production":
            if "CHANGE_ME" in self.jwt_secret:
                raise ValueError("JWT_SECRET must be set in production")
            if any(o.startswith("http://") for o in self.cors_origins):
                raise ValueError("CORS origins must use https in production")
            # Mailpit captura los correos y los marca como enviados, pero no le llegan a nadie.
            if self.smtp_host.strip().lower() == "mailpit":
                raise ValueError(
                    "SMTP_HOST points to Mailpit in production: set DOCKER_SMTP_HOST (Docker) or SMTP_HOST to a real SMTP server"
                )
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.environment in ("production", "staging")

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
