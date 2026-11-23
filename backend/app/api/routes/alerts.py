from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import DB, Principal, client_ip, require
from app.models import DetectionResult
from app.models.enums import AlertStatus, Severity
from app.schemas.common import Page
from app.schemas.domain import AlertCommentIn, AlertDetail, AlertEventOut, AlertFilters, AlertOut, AlertStatusUpdate
from app.services import alerts as svc
from app.services import serializers
from app.services.geo import geojson

router = APIRouter(prefix="/alerts", tags=["alerts"])
Reader = Annotated[Principal, Depends(require("read"))]


def alert_filters(
    status: Annotated[list[AlertStatus] | None, Query()] = None,
    severity: Annotated[list[Severity] | None, Query()] = None,
    territory: Annotated[str | None, Query(max_length=64, pattern=r"^[a-z0-9-]+$")] = None,
    region_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    bbox: Annotated[str | None, Query(pattern=r"^-?\d+(\.\d+)?(,-?\d+(\.\d+)?){3}$")] = None,
) -> AlertFilters:
    box = tuple(float(v) for v in bbox.split(",")) if bbox else None
    return AlertFilters(
        status=status, severity=severity, territory=territory, region_id=region_id, date_from=date_from, date_to=date_to, bbox=box
    )  # type: ignore[arg-type]


Filters = Annotated[AlertFilters, Depends(alert_filters)]


@router.get("", response_model=Page[AlertOut])
def list_alerts(
    db: DB,
    _: Reader,
    filters: Filters,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    order: Literal["recent", "severity", "area"] = "recent",
) -> Page[AlertOut]:
    rows, total = svc.list_alerts(db, filters, page, page_size, order)
    return Page(items=[serializers.alert_out(a) for a in rows], total=total, page=page, page_size=page_size)


@router.get("/geojson", summary="Alertas como GeoJSON (para el mapa)")
def alerts_geojson(db: DB, _: Reader, filters: Filters) -> dict[str, Any]:
    rows, _total = svc.list_alerts(db, filters, 1, 1000, "severity")
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": str(a.id),
                "geometry": geojson(a.geom),
                "properties": {
                    "code": a.code,
                    "severity": a.severity,
                    "status": a.status,
                    "signal": a.signal,
                    "area_ha": round(a.area_ha, 2),
                    "region": a.region.name,
                },
            }
            for a in rows
        ],
    }


@router.get("/{alert_id}", response_model=AlertDetail)
def get_alert(alert_id: uuid.UUID, db: DB, _: Reader) -> AlertDetail:
    alert = svc.get_alert(db, alert_id)
    result = db.get(DetectionResult, alert.latest_result_id)
    assert result is not None
    ndvi, nbr = svc.polygon_evidence(db, alert)
    return serializers.alert_detail(alert, result, ndvi, nbr)


@router.patch("/{alert_id}/status", response_model=AlertDetail)
def update_status(
    alert_id: uuid.UUID,
    data: AlertStatusUpdate,
    request: Request,
    db: DB,
    principal: Annotated[Principal, Depends(require("alerts:review"))],
) -> AlertDetail:
    svc.change_status(db, svc.get_alert(db, alert_id), principal.id, data.status, data.comment, client_ip(request))
    db.expire_all()
    return get_alert(alert_id, db, principal)


@router.post("/{alert_id}/comments", response_model=AlertEventOut, status_code=201)
def add_comment(
    alert_id: uuid.UUID, data: AlertCommentIn, db: DB, principal: Annotated[Principal, Depends(require("alerts:comment"))]
) -> AlertEventOut:
    ev = svc.add_comment(db, svc.get_alert(db, alert_id), principal.id, data.comment)
    db.refresh(ev)
    return serializers.event_out(ev)
