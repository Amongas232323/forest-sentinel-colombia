from __future__ import annotations

import pytest
from factories import finding_at, ingest
from sqlalchemy import select

from app.models import Alert, AlertEvent, MonitoredRegion, Territory
from app.models.enums import AlertStatus
from sentinel_ml.contracts import Severity


def region_in(db, slug: str = "guaviare") -> MonitoredRegion:  # type: ignore[no-untyped-def]
    t = db.scalar(select(Territory).where(Territory.slug == slug))
    return db.scalar(select(MonitoredRegion).where(MonitoredRegion.territory_id == t.id))


def square(w, s, size):  # type: ignore[no-untyped-def]
    return {"type": "Polygon", "coordinates": [[[w, s], [w + size, s], [w + size, s + size], [w, s + size], [w, s]]]}


# ── Territorios y regiones ────────────────────────────────────────────────────


def test_only_the_four_territories_are_in_scope(client, observer_headers):
    r = client.get("/api/v1/territories", headers=observer_headers)
    assert r.status_code == 200
    assert {t["slug"] for t in r.json()} == {"guaviare", "sierra-nevada-santa-marta", "cundinamarca", "amazonas"}


def test_public_territory_geometries_need_no_login(client):
    r = client.get("/api/v1/territories/geometries")
    assert r.status_code == 200 and len(r.json()) == 4
    assert r.json()[0]["geometry"]["type"] == "MultiPolygon"


def test_analyst_creates_region_inside_territory(client, analyst_headers):
    body = {"territory_slug": "guaviare", "name": "Zona de prueba Calamar", "geometry": square(-72.70, 2.00, 0.1), "cadence_days": 15}
    r = client.post("/api/v1/regions", headers=analyst_headers, json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert 100 < data["area_km2"] < 140
    assert data["territory_slug"] == "guaviare"


def test_region_outside_territory_rejected(client, analyst_headers):
    # Un cuadrado en Antioquia (por fuera de los cuatro territorios).
    body = {"territory_slug": "guaviare", "name": "Fuera de alcance", "geometry": square(-75.6, 6.2, 0.1)}
    r = client.post("/api/v1/regions", headers=analyst_headers, json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "outside_territory"


def test_region_too_large_rejected(client, analyst_headers):
    body = {"territory_slug": "amazonas", "name": "Demasiado grande", "geometry": square(-72.0, -2.0, 0.7)}
    r = client.post("/api/v1/regions", headers=analyst_headers, json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "region_too_large"


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]},  # se cruza consigo mismo
        {"type": "Polygon", "coordinates": [[[500, 0], [501, 0], [501, 1], [500, 0]]]},  # no es WGS84
        {"type": "Point", "coordinates": [0, 0]},
    ],
)
def test_invalid_geometries_rejected(client, analyst_headers, geometry):
    r = client.post(
        "/api/v1/regions", headers=analyst_headers, json={"territory_slug": "guaviare", "name": "Geometría mala", "geometry": geometry}
    )
    assert r.status_code == 422


def test_unknown_territory(client, analyst_headers):
    r = client.post(
        "/api/v1/regions",
        headers=analyst_headers,
        json={"territory_slug": "antioquia", "name": "Zona Antioquia", "geometry": square(-75.6, 6.2, 0.1)},
    )
    assert r.status_code == 404


# ── Trabajos ──────────────────────────────────────────────────────────────────

WINDOWS = {
    "reference_start": "2024-01-01",
    "reference_end": "2024-03-15",
    "observation_start": "2025-01-01",
    "observation_end": "2025-03-15",
}


def test_submit_job_is_idempotent_per_window(client, db, analyst_headers, enqueued):
    region = region_in(db)
    r1 = client.post(f"/api/v1/regions/{region.id}/jobs", headers=analyst_headers, json=WINDOWS)
    assert r1.status_code == 202 and r1.json()["status"] == "queued"
    assert len(enqueued) == 1
    r2 = client.post(f"/api/v1/regions/{region.id}/jobs", headers=analyst_headers, json=WINDOWS)
    assert r2.status_code == 409


@pytest.mark.parametrize(
    "windows",
    [
        {**WINDOWS, "reference_end": "2025-02-01"},  # se solapa con la observación
        {**WINDOWS, "reference_start": "2015-01-01"},  # antes de que existiera Sentinel-2 L2A
        {**WINDOWS, "observation_end": "2099-01-01"},  # en el futuro
        {**WINDOWS, "reference_start": "2023-01-01"},  # ventana de más de 180 días
    ],
)
def test_job_window_validation(client, db, analyst_headers, enqueued, windows):
    region = region_in(db)
    assert client.post(f"/api/v1/regions/{region.id}/jobs", headers=analyst_headers, json=windows).status_code == 422
    assert enqueued == []


# ── Resultado del pipeline → PostGIS → alertas ────────────────────────────────


def test_result_persistence_and_alert_generation(db):
    region = region_in(db)
    stored, report = ingest(db, region, [finding_at(region), finding_at(region, dx=0.03, severity=Severity.LOW)])
    assert len(stored.polygons) == 2
    assert len(report.created) == 1  # LOW está por debajo de ALERT_MIN_SEVERITY=moderate
    assert report.skipped_below_threshold == 1
    alert = report.created[0]
    assert alert.status == AlertStatus.NEW and alert.area_ha > 0
    assert db.scalar(select(AlertEvent.type).where(AlertEvent.alert_id == alert.id)) == "created"


def test_low_quality_run_generates_no_alerts(db):
    region = region_in(db)
    stored, report = ingest(db, region, [finding_at(region)], quality_ok=False)
    assert len(stored.polygons) == 1 and report.created == [] and report.skipped_low_quality == 1


def test_cloudy_polygon_generates_no_alert(db):
    region = region_in(db)
    _, report = ingest(db, region, [finding_at(region, valid=0.3)])
    assert report.created == [] and report.skipped_low_quality == 1


def test_spatiotemporal_deduplication_merges_overlaps(db):
    region = region_in(db)
    _, r1 = ingest(db, region, [finding_at(region, size=0.01)])
    _, r2 = ingest(db, region, [finding_at(region, dx=0.005, size=0.01)])  # se solapa con la primera
    assert len(r1.created) == 1 and r2.created == [] and len(r2.updated) == 1
    alerts = db.scalars(select(Alert)).all()
    assert len(alerts) == 1 and alerts[0].detection_count == 2
    _, r3 = ingest(db, region, [finding_at(region, dx=0.05)])  # lejos → alerta nueva
    assert len(r3.created) == 1


def test_dismissed_alert_reopens_only_if_it_grows(db):
    region = region_in(db)
    _, r1 = ingest(db, region, [finding_at(region, size=0.01)])
    alert = r1.created[0]
    alert.status = AlertStatus.DISMISSED
    db.commit()
    ingest(db, region, [finding_at(region, size=0.01)])
    db.refresh(alert)
    assert alert.status == AlertStatus.DISMISSED
    ingest(db, region, [finding_at(region, size=0.03)])
    db.refresh(alert)
    assert alert.status == AlertStatus.PENDING_REVIEW


def test_alerts_are_clipped_to_the_region(db):
    region = region_in(db)
    from app.services.geo import from_db

    b = from_db(region.geom).bounds
    f = finding_at(region, dx=(b[2] - b[0]) / 2 - 0.005, size=0.01)  # la mitad queda por fuera de la zona
    _, report = ingest(db, region, [f])
    alert = report.created[0]
    assert from_db(region.geom).buffer(1e-9).contains(from_db(alert.geom))


# ── API de alertas ────────────────────────────────────────────────────────────


def test_alert_api_list_detail_and_plain_language(client, db, observer_headers):
    region = region_in(db)
    _, report = ingest(db, region, [finding_at(region)])
    lst = client.get("/api/v1/alerts", headers=observer_headers)
    assert lst.status_code == 200 and lst.json()["total"] == 1
    item = lst.json()["items"][0]
    assert item["explanation"]["headline"] == "Se detectó una posible pérdida de vegetación"
    assert "20 de febrero de 2025" in item["explanation"]["summary"]
    assert "no IA" in item["explanation"]["confidence_text"]  # honestos sobre cuál detector se usó
    detail = client.get(f"/api/v1/alerts/{item['id']}", headers=observer_headers).json()
    assert detail["geometry"]["type"] == "MultiPolygon"
    assert detail["evidence"]["overlay_url"].startswith("/api/v1/results/")
    img = client.get(detail["evidence"]["overlay_url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert detail["mean_ndvi_drop"] == pytest.approx(0.35)


def test_alert_filters_and_geojson(client, db, observer_headers):
    region = region_in(db)
    ingest(db, region, [finding_at(region)])
    assert client.get("/api/v1/alerts?territory=amazonas", headers=observer_headers).json()["total"] == 0
    assert client.get("/api/v1/alerts?territory=guaviare&severity=high", headers=observer_headers).json()["total"] == 1
    assert client.get("/api/v1/alerts?bbox=0,0,1,1", headers=observer_headers).json()["total"] == 0
    gj = client.get("/api/v1/alerts/geojson", headers=observer_headers).json()
    assert gj["type"] == "FeatureCollection" and len(gj["features"]) == 1


def test_review_workflow(client, db, analyst_headers, observer_headers):
    region = region_in(db)
    _, report = ingest(db, region, [finding_at(region)])
    aid = report.created[0].id
    url = f"/api/v1/alerts/{aid}/status"
    assert client.patch(url, headers=observer_headers, json={"status": "in_review"}).status_code == 403
    assert client.patch(url, headers=analyst_headers, json={"status": "closed"}).status_code == 409  # no se permite desde new
    assert client.patch(url, headers=analyst_headers, json={"status": "in_review"}).status_code == 200
    assert client.patch(url, headers=analyst_headers, json={"status": "confirmed"}).status_code == 422  # el comentario es obligatorio
    r = client.patch(url, headers=analyst_headers, json={"status": "confirmed", "comment": "Verificado con imagen de alta resolución."})
    assert r.status_code == 200
    events = r.json()["events"]
    assert [e["type"] for e in events] == ["created", "status_changed", "status_changed"]
    c = client.post(f"/api/v1/alerts/{aid}/comments", headers=analyst_headers, json={"comment": "<script>alert(1)</script>"})
    assert c.status_code == 201 and c.json()["comment"] == "<script>alert(1)</script>"  # se guarda tal cual, se escapa al renderizar


def test_evidence_requires_valid_signature(client, db, observer_headers):
    region = region_in(db)
    stored, _ = ingest(db, region, [finding_at(region)])
    assert client.get(f"/api/v1/results/{stored.id}/evidence/overlay?exp=9999999999&sig=deadbeef").status_code == 404
    assert client.get(f"/api/v1/results/{stored.id}/evidence/..%2F..%2Fsecret?exp=9999999999&sig=x").status_code == 404


def test_overview_counts_come_from_data(client, db, observer_headers):
    empty = client.get("/api/v1/stats/overview", headers=observer_headers).json()
    assert empty["alerts_total"] == 0 and empty["images_processed"] == 0
    region = region_in(db)
    ingest(db, region, [finding_at(region)])
    data = client.get("/api/v1/stats/overview", headers=observer_headers).json()
    assert data["alerts_total"] == 1 and data["alerts_pending"] == 1
    assert data["images_processed"] == 2
    assert {t["slug"]: t["open_alerts"] for t in data["by_territory"]}["guaviare"] == 1


# ── Recuperación de análisis colgados ─────────────────────────────────────────


def test_stale_running_job_is_marked_failed(db):
    from datetime import UTC, datetime, timedelta

    from factories import make_job

    from app.models.enums import JobStatus
    from app.services.jobs import STALE_JOB_MESSAGE, fail_stale_jobs, stale_job_cutoff_s

    region = region_in(db)
    job = make_job(db, region)  # make_job lo deja en running
    job.started_at = datetime.now(UTC) - timedelta(seconds=60)
    db.commit()
    assert fail_stale_jobs(db) == []  # todavía puede estar corriendo de verdad

    job.started_at = datetime.now(UTC) - timedelta(seconds=stale_job_cutoff_s() + 60)
    db.commit()
    assert fail_stale_jobs(db) == [job.id]
    db.refresh(job)
    assert job.status == JobStatus.FAILED and job.error == STALE_JOB_MESSAGE and job.finished_at is not None
    assert fail_stale_jobs(db) == []  # no se toca dos veces
