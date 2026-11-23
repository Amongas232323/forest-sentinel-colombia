"""Arma salidas del pipeline que siguen el contrato real de ML (sentinel_ml.contracts).

Al usar las dataclasses de verdad nos aseguramos de que si cambia el contrato en el
paquete de ML se rompan estos tests del backend (test de compatibilidad entre módulos).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import numpy as np
from PIL import Image
from shapely.geometry import box, mapping

from app.models import MonitoredRegion, ProcessingJob
from app.models.enums import JobStatus
from app.services.evidence import run_dir
from app.services.geo import from_db
from sentinel_ml.contracts import (
    CONTRACT_VERSION,
    Artifacts,
    ChangeSignal,
    CompositeInfo,
    Finding,
    PipelineResult,
    Severity,
)


def finding_at(
    region: MonitoredRegion,
    dx: float = 0.0,
    size: float = 0.01,
    severity: Severity = Severity.HIGH,
    valid: float = 0.95,
    score: float = 0.7,
) -> Finding:
    c = from_db(region.geom).centroid
    geom = box(c.x + dx, c.y, c.x + dx + size, c.y + size)
    return Finding(
        geometry=mapping(geom),
        centroid=(geom.centroid.x, geom.centroid.y),
        area_ha=round(size * 111 * size * 111 * 100, 2),
        mean_score=score,
        max_score=min(1.0, score + 0.2),
        severity=severity,
        signal=ChangeSignal.VEGETATION_LOSS,
        mean_ndvi_drop=0.35,
        mean_nbr_drop=0.42,
        valid_fraction=valid,
    )


def pipeline_result(region: MonitoredRegion, findings: list[Finding], quality_ok: bool = True) -> PipelineResult:
    b = from_db(region.geom).bounds
    t0, t1 = datetime(2024, 2, 10, 15, tzinfo=UTC), datetime(2025, 2, 20, 15, tzinfo=UTC)
    return PipelineResult(
        contract_version=CONTRACT_VERSION,
        detector_id="spectral-baseline",
        detector_version="1.0.0",
        detector_kind="rule-based",
        aoi=list(b),
        reference=CompositeInfo("reference", ["S2B_T18NXH_20240210T152639_L2A"], t0, t0, 0.97),
        observation=CompositeInfo("observation", ["S2A_T18NXH_20250220T152641_L2A"], t1, t1, 0.95 if quality_ok else 0.2),
        quality_ok=quality_ok,
        quality_notes=[] if quality_ok else ["Solo el 20% del área observada está libre de nubes (mínimo 40%)."],
        analysed_area_ha=50_000.0,
        changed_area_ha=sum(f.area_ha for f in findings),
        findings=findings,
        artifacts=Artifacts(
            "reference.png",
            "observation.png",
            "change_overlay.png",
            "work/evidence.tif",
            list(b),
            [[b[0], b[3]], [b[2], b[3]], [b[2], b[1]], [b[0], b[1]]],
        ),
        parameters={"test": True},
    )


def make_job(db, region: MonitoredRegion) -> ProcessingJob:  # type: ignore[no-untyped-def]
    job = ProcessingJob(
        region_id=region.id,
        status=JobStatus.RUNNING,
        reference_start=date(2024, 1, 1),
        reference_end=date(2024, 3, 15),
        observation_start=date(2025, 1, 1),
        observation_end=date(2025, 3, 15),
    )
    db.add(job)
    db.commit()
    d = run_dir(job.id)
    d.mkdir(parents=True, exist_ok=True)
    inventory = {
        sid: {
            "collection": "sentinel-2-c1-l2a",
            "acquired_at": ts,
            "cloud_cover": 4.2,
            "epsg": 32618,
            "tile_id": "18NXH",
            "assets": {"red": f"https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/{sid}/B04.tif"},
        }
        for sid, ts in (
            ("S2B_T18NXH_20240210T152639_L2A", "2024-02-10T15:00:00+00:00"),
            ("S2A_T18NXH_20250220T152641_L2A", "2025-02-20T15:00:00+00:00"),
        )
    }
    (d / "scenes.json").write_text(json.dumps(inventory), encoding="utf-8")
    for name, color in (
        ("reference.png", (40, 90, 50, 255)),
        ("observation.png", (120, 100, 70, 255)),
        ("change_overlay.png", (217, 93, 80, 200)),
    ):
        Image.fromarray(np.full((32, 32, 4), color, np.uint8)).save(d / name)
    return job


def ingest(db, region: MonitoredRegion, findings: list[Finding], quality_ok: bool = True):  # type: ignore[no-untyped-def]
    """Persiste una ejecución sintética igualito a como lo hace execute_job después del pipeline."""
    from app.services.alerts import generate_alerts
    from app.services.jobs import ensure_model_version, persist_result
    from sentinel_ml.detectors import SpectralBaselineDetector

    job = make_job(db, region)
    mv = ensure_model_version(db, SpectralBaselineDetector(), None)
    stored = persist_result(db, job, region, mv.id, pipeline_result(region, findings, quality_ok))
    report = generate_alerts(db, stored, region, "earth-search-s2-c1")
    job.status = JobStatus.SUCCEEDED
    db.commit()
    return stored, report
