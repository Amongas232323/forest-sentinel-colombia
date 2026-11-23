"""Contrato de salida del pipeline.

El backend valida esta estructura con Pydantic
(``backend/app/schemas/pipeline.py``) y el JSON Schema de
``contracts/pipeline_result.schema.json`` se genera a partir de los mismos campos.
OJO: cambiar un campo aquí rompe compatibilidad, toca subir ``CONTRACT_VERSION``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum, StrEnum
from typing import Any

CONTRACT_VERSION = "1.0"


class Severity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    PRIORITY = "priority"


class ChangeSignal(StrEnum):
    """Pista heurística sobre el *tipo* de cambio. Nunca es una confirmación."""

    VEGETATION_LOSS = "vegetation_loss"
    POSSIBLE_BURN = "possible_burn"
    POSSIBLE_FLOODING = "possible_flooding"


@dataclass(frozen=True)
class BBox:
    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        if not (-180 <= self.west < self.east <= 180):
            raise ValueError("invalid longitude range")
        if not (-90 <= self.south < self.north <= 90):
            raise ValueError("invalid latitude range")

    def as_list(self) -> list[float]:
        return [self.west, self.south, self.east, self.north]


@dataclass(frozen=True)
class DateWindow:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("window start must be <= end")

    def as_interval(self) -> str:
        return f"{self.start.isoformat()}/{self.end.isoformat()}"


@dataclass(frozen=True)
class SceneRef:
    scene_id: str
    source: str
    collection: str
    acquired_at: datetime
    cloud_cover: float | None
    epsg: int
    assets: dict[str, str]
    tile_id: str | None = None


@dataclass
class CompositeInfo:
    period: str  # "reference" | "observation"
    scene_ids: list[str]
    first_acquired: datetime
    last_acquired: datetime
    valid_fraction: float


@dataclass
class Finding:
    geometry: dict[str, Any]  # GeoJSON Polygon o MultiPolygon en EPSG:4326
    centroid: tuple[float, float]  # (lon, lat)
    area_ha: float
    mean_score: float
    max_score: float
    severity: Severity
    signal: ChangeSignal
    mean_ndvi_drop: float
    mean_nbr_drop: float
    valid_fraction: float  # calidad de los píxeles dentro del polígono


@dataclass
class Artifacts:
    """Rutas relativas (dentro del directorio de la ejecución) de la evidencia generada."""

    reference_rgb: str
    observation_rgb: str
    change_overlay: str
    evidence: str  # GeoTIFF int16 de 4 bandas: score, signal, dNDVI, dNBR (×1000)
    bounds: list[float]  # [w, s, e, n] en EPSG:4326 de los rásters de arriba
    # Esquinas de la imagen en EPSG:4326, en orden TL, TR, BR, BL (lo que espera MapLibre).
    corners: list[list[float]] = field(default_factory=list)


@dataclass
class PipelineResult:
    contract_version: str
    detector_id: str
    detector_version: str
    detector_kind: str  # "rule-based" | "deep-learning"
    aoi: list[float]
    reference: CompositeInfo
    observation: CompositeInfo
    quality_ok: bool
    quality_notes: list[str]
    analysed_area_ha: float
    changed_area_ha: float
    findings: list[Finding]
    artifacts: Artifacts | None
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float):
        return round(value, 6)
    return value
