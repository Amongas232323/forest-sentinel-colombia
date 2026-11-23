"""Conversión de ORM → contrato de la API (así los routers quedan livianos)."""

from __future__ import annotations

from app.models import Alert, AlertEvent, DetectionResult, ModelVersion, MonitoredRegion, ProcessingJob, Territory
from app.models.enums import ALERT_TRANSITIONS, ChangeSignal
from app.schemas.domain import (
    AlertDetail,
    AlertEventOut,
    AlertOut,
    EvidenceOut,
    JobOut,
    ModelVersionOut,
    RegionOut,
    TerritoryOut,
)

from . import evidence
from .explain import explain
from .geo import bbox_of, centroid_of, geojson


def territory_out(t: Territory, region_count: int = 0, open_alerts: int = 0) -> TerritoryOut:
    return TerritoryOut(
        id=t.id,
        slug=t.slug,
        name=t.name,
        kind=t.kind,
        description=t.description,
        area_km2=t.area_km2,
        attribution=t.attribution,
        license=t.license,
        centroid=centroid_of(t.geom),
        bbox=bbox_of(t.geom),
        region_count=region_count,
        open_alerts=open_alerts,
    )


def region_out(r: MonitoredRegion, open_alerts: int = 0, last_job_status=None) -> RegionOut:  # type: ignore[no-untyped-def]
    return RegionOut(
        id=r.id,
        territory_id=r.territory_id,
        territory_slug=r.territory.slug,
        territory_name=r.territory.name,
        name=r.name,
        description=r.description,
        area_km2=round(r.area_km2, 2),
        is_active=r.is_active,
        cadence_days=r.cadence_days,
        last_run_at=r.last_run_at,
        created_at=r.created_at,
        centroid=centroid_of(r.geom),
        bbox=bbox_of(r.geom),
        geometry=geojson(r.geom),
        open_alerts=open_alerts,
        last_job_status=last_job_status,
    )


def job_out(j: ProcessingJob) -> JobOut:
    mv = j.model_version
    return JobOut(
        id=j.id,
        region_id=j.region_id,
        region_name=j.region.name,
        status=j.status,
        stage=j.stage,
        progress=round(j.progress, 3),
        reference_start=j.reference_start,
        reference_end=j.reference_end,
        observation_start=j.observation_start,
        observation_end=j.observation_end,
        trigger=j.trigger,
        error=j.error,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
        result_id=j.result.id if j.result else None,
        detector=f"{mv.detector_id}@{mv.version}" if mv else None,
    )


def model_out(m: ModelVersion) -> ModelVersionOut:
    return ModelVersionOut.model_validate(m)


def evidence_out(result: DetectionResult) -> EvidenceOut | None:
    art = result.artifacts
    if not art:
        return None
    return EvidenceOut(
        reference_url=evidence.signed_url(result.id, "reference"),
        observation_url=evidence.signed_url(result.id, "observation"),
        overlay_url=evidence.signed_url(result.id, "overlay"),
        corners=art.get("corners", []),
        bounds=art.get("bounds", []),
    )


def alert_out(a: Alert) -> AlertOut:
    return AlertOut(**_alert_fields(a))


def _alert_fields(a: Alert) -> dict:  # type: ignore[type-arg]
    mv = a.model_version
    return {
        "id": a.id,
        "code": a.code,
        "region_id": a.region_id,
        "region_name": a.region.name,
        "territory_slug": a.region.territory.slug,
        "territory_name": a.region.territory.name,
        "status": a.status,
        "severity": a.severity,
        "signal": a.signal,
        "confidence": round(a.confidence, 3),
        "area_ha": round(a.area_ha, 2),
        "centroid": centroid_of(a.centroid),
        "reference_date": a.reference_date,
        "observation_date": a.observation_date,
        "first_detected_at": a.first_detected_at,
        "last_detected_at": a.last_detected_at,
        "detection_count": a.detection_count,
        "image_quality": round(a.image_quality, 3),
        "detector": f"{mv.detector_id}@{mv.version}",
        "detector_kind": mv.kind,
        "explanation": explain(ChangeSignal(a.signal), a.area_ha, a.confidence, a.reference_date, a.observation_date, mv.kind),
    }


def event_out(e: AlertEvent) -> AlertEventOut:
    return AlertEventOut(
        id=e.id,
        type=e.type,
        from_status=e.from_status,
        to_status=e.to_status,
        comment=e.comment,
        actor_name=e.actor.full_name if e.actor else None,
        created_at=e.created_at,
    )


def alert_detail(a: Alert, result: DetectionResult, ndvi_drop: float | None, nbr_drop: float | None) -> AlertDetail:
    return AlertDetail(
        **_alert_fields(a),
        geometry=geojson(a.geom),
        source=a.source,
        evidence=evidence_out(result),
        result_id=result.id,
        mean_ndvi_drop=round(ndvi_drop, 3) if ndvi_drop is not None else None,
        mean_nbr_drop=round(nbr_drop, 3) if nbr_drop is not None else None,
        events=[event_out(e) for e in a.events],
        allowed_transitions=sorted(ALERT_TRANSITIONS[a.status]),
    )
