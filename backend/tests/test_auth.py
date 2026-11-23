from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import PASSWORD, login, make_user

REG = {"email": "Ana@Example.org", "full_name": "Ana Pérez", "password": "selva-guaviare-2026", "accept_privacy": True}


def test_register_creates_observer_with_privacy_record(client, db):
    r = client.post("/api/v1/auth/register", json=REG)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["role"] == "observer" and body["email"] == "ana@example.org"
    assert "password" not in str(body)
    from app.models import User

    u = db.query(User).one()
    assert u.password_hash.startswith("$argon2id$")
    assert u.privacy_accepted_version


def test_register_requires_explicit_privacy_acceptance(client):
    r = client.post("/api/v1/auth/register", json={**REG, "accept_privacy": False})
    assert r.status_code == 422


def test_register_rejects_weak_and_duplicate(client):
    assert client.post("/api/v1/auth/register", json={**REG, "password": "corta"}).status_code == 422
    assert client.post("/api/v1/auth/register", json={**REG, "password": "aaaaaaaaaaaaaaa"}).status_code == 422
    assert client.post("/api/v1/auth/register", json=REG).status_code == 201
    assert client.post("/api/v1/auth/register", json={**REG, "email": "ANA@example.org"}).status_code == 409


def test_register_rejects_unknown_fields(client):
    r = client.post("/api/v1/auth/register", json={**REG, "role": "admin"})
    assert r.status_code == 422  # asignación masiva bloqueada


def test_login_and_me(client, db):
    u = make_user(db, "analyst")
    headers = login(client, u.email.upper())
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["role"] == "analyst"


def test_login_errors_are_generic(client, db):
    u = make_user(db)
    wrong = client.post("/api/v1/auth/login", json={"email": u.email, "password": "incorrecta-123456"})
    missing = client.post("/api/v1/auth/login", json={"email": "nadie@example.org", "password": "incorrecta-123456"})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]


def test_account_lockout_after_repeated_failures(client, db):
    u = make_user(db)
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": u.email, "password": "incorrecta-123456"})
    r = client.post("/api/v1/auth/login", json={"email": u.email, "password": PASSWORD})
    assert r.status_code == 401
    db.refresh(u)
    assert u.locked_until and u.locked_until > datetime.now(UTC)


def test_login_rate_limit(client, db):
    u = make_user(db)
    codes = [client.post("/api/v1/auth/login", json={"email": u.email, "password": "x" * 13}).status_code for _ in range(12)]
    assert 429 in codes


def test_refresh_rotation_and_reuse_detection(client, db):
    u = make_user(db)
    login(client, u.email)
    first = client.cookies.get("fs_refresh")
    r = client.post("/api/v1/auth/refresh", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200
    second = client.cookies.get("fs_refresh")
    assert first and second and first != second
    # Si se reutiliza el token viejo se revoca toda la familia de la sesión.
    client.cookies.set("fs_refresh", first, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    client.cookies.set("fs_refresh", second, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_refresh_rejects_foreign_origin(client, db):
    u = make_user(db)
    login(client, u.email)
    assert client.post("/api/v1/auth/refresh", headers={"Origin": "https://evil.example"}).status_code == 403


def test_refresh_cookie_flags(client, db):
    u = make_user(db)
    r = client.post("/api/v1/auth/login", json={"email": u.email, "password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/v1/auth" in cookie


def test_logout_revokes_access_token_immediately(client, db):
    u = make_user(db)
    headers = login(client, u.email)
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_tampered_or_missing_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_password_reset_flow_without_enumeration(client, db, sent_emails):
    u = make_user(db)
    ok = client.post("/api/v1/auth/password/forgot", json={"email": u.email})
    unknown = client.post("/api/v1/auth/password/forgot", json={"email": "nadie@example.org"})
    assert ok.status_code == unknown.status_code == 202
    assert ok.json() == unknown.json()
    assert len(sent_emails) == 1
    token = sent_emails[0].context["reset_url"].split("token=")[1]
    r = client.post("/api/v1/auth/password/reset", json={"token": token, "password": "nueva-clave-segura-1"})
    assert r.status_code == 200
    assert client.post("/api/v1/auth/password/reset", json={"token": token, "password": "otra-clave-segura-2"}).status_code == 401
    login(client, u.email, "nueva-clave-segura-1")


def test_expired_reset_token(client, db, sent_emails):
    u = make_user(db)
    client.post("/api/v1/auth/password/forgot", json={"email": u.email})
    token = sent_emails[0].context["reset_url"].split("token=")[1]
    from app.models import PasswordResetToken

    row = db.query(PasswordResetToken).one()
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert client.post("/api/v1/auth/password/reset", json={"token": token, "password": "nueva-clave-segura-1"}).status_code == 401


def test_change_password_revokes_sessions(client, db):
    u = make_user(db)
    headers = login(client, u.email)
    r = client.post(
        "/api/v1/auth/password/change", headers=headers, json={"current_password": PASSWORD, "new_password": "cambio-de-clave-2026"}
    )
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_refresh_without_cookie_is_anonymous_not_error(client):
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 204
