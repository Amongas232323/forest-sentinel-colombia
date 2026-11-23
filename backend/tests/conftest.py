"""Fixtures de los tests: una base de datos PostGIS dedicada, migrada con Alembic.

Necesita el servicio ``db`` de docker-compose. La base de test se llama igual que la
configurada pero con el sufijo ``_test``; se borra y se vuelve a crear en cada sesión.
"""

from __future__ import annotations

import os

os.environ["ENVIRONMENT"] = "test"

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

_base = get_settings()
_test_url = make_url(_base.database_url).set(database=f"{make_url(_base.database_url).database}_test")
os.environ["DATABASE_URL"] = _test_url.render_as_string(hide_password=False)
get_settings.cache_clear()


def _admin_conn() -> psycopg.Connection:
    url = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql", database="postgres")
    return psycopg.connect(url.render_as_string(hide_password=False), autocommit=True)


@pytest.fixture(scope="session", autouse=True)
def database(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    name = _test_url.database
    with _admin_conn() as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{name}"')
    data_dir = tmp_path_factory.mktemp("data")
    os.environ["DATA_DIR"] = str(data_dir)
    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(cfg, "head")

    from app.db.session import get_sessionmaker
    from app.seed import seed_sources, seed_territories

    with get_sessionmaker()() as db:
        seed_territories(db)
        seed_sources(db)
        db.commit()
    yield
    from app.db.session import get_engine

    get_engine().dispose()


MUTABLE_TABLES = [
    "alert_events",
    "notifications",
    "detected_polygons",
    "alerts",
    "detection_results",
    "job_scenes",
    "processing_jobs",
    "satellite_scenes",
    "model_versions",
    "reports",
    "audit_logs",
    "cookie_consents",
    "password_reset_tokens",
    "auth_sessions",
    "user_preferences",
]


@pytest.fixture(autouse=True)
def clean_db() -> Iterator[None]:
    yield
    from app.core import rate_limit
    from app.db.session import get_engine

    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(MUTABLE_TABLES)} RESTART IDENTITY CASCADE"))
        # Dejamos las zonas sembradas (created_by_id NULL); un truncate CASCADE de users las borraría.
        conn.execute(text("DELETE FROM monitored_regions WHERE created_by_id IS NOT NULL"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("ALTER SEQUENCE alert_number_seq RESTART"))
    rate_limit._limiter = None


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app(), base_url="http://testserver") as c:
        yield c


@pytest.fixture
def db():  # type: ignore[no-untyped-def]
    from app.db.session import get_sessionmaker

    with get_sessionmaker()() as session:
        yield session


@pytest.fixture
def sent_emails(monkeypatch: pytest.MonkeyPatch) -> list:  # type: ignore[type-arg]
    """Captura los correos salientes en vez de usar SMTP."""
    from app.services import mailer

    outbox: list = []  # type: ignore[type-arg]

    def fake_send(mail: mailer.OutgoingEmail) -> None:
        mailer.build_message(mail)  # igual renderiza las plantillas → así detectamos errores en ellas
        outbox.append(mail)

    monkeypatch.setattr(mailer, "send", fake_send)
    return outbox


@pytest.fixture
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    jobs: list[uuid.UUID] = []
    monkeypatch.setattr("app.api.routes.monitoring.enqueue_job", lambda job_id: jobs.append(job_id))
    return jobs


PASSWORD = "bosque-andino-2026"


def make_user(db, role: str = "observer", email: str | None = None):  # type: ignore[no-untyped-def]
    from app.core.security import hash_password
    from app.models import User, UserPreferences
    from app.models.enums import Role

    user = User(
        email=email or f"{role}-{uuid.uuid4().hex[:6]}@example.org",
        full_name=f"Usuario {role}",
        password_hash=hash_password(PASSWORD),
        role=Role(role),
    )
    user.preferences = UserPreferences()
    db.add(user)
    db.commit()
    return user


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers(client: TestClient, db) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return login(client, make_user(db, "admin").email)


@pytest.fixture
def analyst_headers(client: TestClient, db) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return login(client, make_user(db, "analyst").email)


@pytest.fixture
def observer_headers(client: TestClient, db) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return login(client, make_user(db, "observer").email)


def now() -> datetime:
    return datetime.now(UTC)
