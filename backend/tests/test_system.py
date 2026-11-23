from __future__ import annotations

from conftest import login, make_user
from factories import finding_at, ingest
from test_monitoring import region_in

from app.services.reports import _safe_cell


# ── Matriz de autorización ────────────────────────────────────────────────────


def test_observer_cannot_write(client, db, observer_headers, enqueued):
    region = region_in(db)
    assert client.post("/api/v1/regions", headers=observer_headers, json={}).status_code in (403, 422)
    assert (
        client.post(
            f"/api/v1/regions/{region.id}/jobs",
            headers=observer_headers,
            json={
                "reference_start": "2024-01-01",
                "reference_end": "2024-03-01",
                "observation_start": "2025-01-01",
                "observation_end": "2025-03-01",
            },
        ).status_code
        == 403
    )
    assert client.delete(f"/api/v1/regions/{region.id}", headers=observer_headers).status_code == 403
    assert client.get("/api/v1/users", headers=observer_headers).status_code == 403
    assert client.get("/api/v1/audit", headers=observer_headers).status_code == 403


def test_analyst_cannot_manage_users(client, analyst_headers):
    assert client.get("/api/v1/users", headers=analyst_headers).status_code == 403


def test_admin_manages_roles_but_not_itself(client, db, admin_headers):
    target = make_user(db, "observer")
    r = client.patch(f"/api/v1/users/{target.id}", headers=admin_headers, json={"role": "analyst"})
    assert r.status_code == 200 and r.json()["role"] == "analyst"
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    assert client.patch(f"/api/v1/users/{me['id']}", headers=admin_headers, json={"role": "observer"}).status_code == 409


def test_deactivated_user_loses_access(client, db, admin_headers):
    target = make_user(db, "analyst")
    headers = login(client, target.email)
    client.patch(f"/api/v1/users/{target.id}", headers=admin_headers, json={"is_active": False})
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


# ── Reportes ──────────────────────────────────────────────────────────────────


def test_csv_report_and_idor_protection(client, db, analyst_headers, observer_headers):
    region = region_in(db)
    ingest(db, region, [finding_at(region)])
    r = client.post("/api/v1/reports", headers=analyst_headers, json={"format": "csv", "filters": {"territory": "guaviare"}})
    assert r.status_code == 201 and r.json()["alert_count"] == 1
    dl = client.get(r.json()["download_url"], headers=analyst_headers)
    assert dl.status_code == 200
    text = dl.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("codigo,estado,prioridad")
    assert "Guaviare" in text
    # Otro usuario no puede descargar el reporte de alguien más.
    assert client.get(r.json()["download_url"], headers=observer_headers).status_code == 404


def test_pdf_report_contains_evidence(client, db, analyst_headers):
    region = region_in(db)
    ingest(db, region, [finding_at(region)])
    r = client.post("/api/v1/reports", headers=analyst_headers, json={"format": "pdf", "title": "Informe Guaviare"})
    assert r.status_code == 201
    pdf = client.get(r.json()["download_url"], headers=analyst_headers).content
    assert pdf.startswith(b"%PDF") and len(pdf) > 3000


def test_csv_injection_neutralised():
    assert _safe_cell('=HYPERLINK("x")') == '\'=HYPERLINK("x")'
    assert _safe_cell("+1") == "'+1" and _safe_cell("Guaviare") == "Guaviare"


def test_email_report(client, db, analyst_headers, sent_emails):
    region = region_in(db)
    ingest(db, region, [finding_at(region)])
    rep = client.post("/api/v1/reports", headers=analyst_headers, json={"format": "csv"}).json()
    r = client.post(f"/api/v1/reports/{rep['id']}/email", headers=analyst_headers, json={"to": ["equipo@example.org"]})
    assert r.status_code == 200 and r.json()[0]["status"] == "sent"
    assert sent_emails[0].attachments[0].filename.endswith(".csv")


# ── Notificaciones ────────────────────────────────────────────────────────────


def test_alert_email_once_per_alert_and_respects_preferences(client, db, sent_emails):
    from app.services.notifications import notify_new_alerts

    subscriber = make_user(db, "observer")
    other = make_user(db, "observer")
    h = login(client, subscriber.email)
    client.put(
        "/api/v1/me/preferences",
        headers=h,
        json={"notifications_enabled": True, "min_severity": "moderate", "frequency": "immediate", "region_ids": [], "signals": []},
    )
    oh = login(client, other.email)
    client.put(
        "/api/v1/me/preferences",
        headers=oh,
        json={"notifications_enabled": True, "min_severity": "priority", "frequency": "immediate", "region_ids": [], "signals": []},
    )

    region = region_in(db)
    _, report = ingest(db, region, [finding_at(region)])
    ids = [a.id for a in report.created]
    assert notify_new_alerts(db, ids) == 1  # `other` solo quiere las prioritarias
    assert notify_new_alerts(db, ids) == 0  # nunca dos veces por la misma alerta
    mail = sent_emails[0]
    assert mail.to == subscriber.email and "Cambio importante" in mail.subject
    assert mail.list_unsubscribe and "unsubscribe?token=" in mail.list_unsubscribe
    hist = client.get("/api/v1/me/notifications", headers=h).json()
    assert hist["total"] == 1 and hist["items"][0]["status"] == "sent"


def test_unsubscribe_link(client, db):
    from app.services.notifications import unsubscribe_token

    u = make_user(db)
    u.preferences.notifications_enabled = True
    db.commit()
    assert client.post("/api/v1/notifications/unsubscribe?token=" + "x" * 50).status_code == 404
    assert client.post(f"/api/v1/notifications/unsubscribe?token={unsubscribe_token(u.id)}").status_code == 200
    db.refresh(u.preferences)
    assert u.preferences.notifications_enabled is False


def test_daily_digest(db, sent_emails):
    from app.models.enums import NotificationFrequency
    from app.services.notifications import send_digests

    u = make_user(db)
    u.preferences.notifications_enabled = True
    u.preferences.frequency = NotificationFrequency.DAILY
    u.preferences.min_severity = "moderate"
    db.commit()
    region = region_in(db)
    ingest(db, region, [finding_at(region)])
    assert send_digests(db, NotificationFrequency.DAILY) == 1
    assert send_digests(db, NotificationFrequency.DAILY) == 0  # no otra vez dentro del mismo periodo
    assert "Resumen diario" in sent_emails[0].subject


def test_preferences_reject_unknown_regions(client, observer_headers):
    r = client.put(
        "/api/v1/me/preferences",
        headers=observer_headers,
        json={
            "notifications_enabled": True,
            "min_severity": "high",
            "frequency": "daily",
            "region_ids": ["00000000-0000-0000-0000-000000000000"],
            "signals": [],
        },
    )
    assert r.status_code == 422


# ── Privacidad, headers, límites ─────────────────────────────────────────────


def test_cookie_consent_is_recorded(client):
    sid = "a" * 24
    r = client.post("/api/v1/privacy/consent", json={"subject_id": sid, "functional": True, "analytics": False})
    assert r.status_code == 201 and r.json()["necessary"] is True
    got = client.get(f"/api/v1/privacy/consent/{sid}").json()
    assert got["analytics"] is False and got["policy_version"]


def test_security_headers(client):
    r = client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]


def test_payload_size_limit(client):
    r = client.post("/api/v1/auth/login", content=b"x" * 2_000_000, headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_errors_do_not_leak_internals(client, observer_headers):
    r = client.get("/api/v1/alerts/not-a-uuid", headers=observer_headers)
    assert r.status_code == 422 and "Traceback" not in r.text


def test_audit_log_records_actions(client, db, admin_headers):
    target = make_user(db)
    client.patch(f"/api/v1/users/{target.id}", headers=admin_headers, json={"role": "analyst"})
    r = client.get("/api/v1/audit?action=user.updated", headers=admin_headers)
    assert r.status_code == 200 and r.json()["total"] == 1
