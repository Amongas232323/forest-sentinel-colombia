from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.geometry import shape
from shapely.validation import explain_validity

T = TypeVar("T")


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


class Page(Schema, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


MAX_VERTICES = 5000


class PolygonGeometry(Schema):
    """GeoJSON Polygon/MultiPolygon en EPSG:4326, validado en el servidor."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]

    @field_validator("coordinates")
    @classmethod
    def _bounded(cls, v: list[Any]) -> list[Any]:
        flat = str(v).count("[")
        if flat > MAX_VERTICES * 2:
            raise ValueError(f"geometry exceeds {MAX_VERTICES} vertices")
        return v

    def to_shape(self):  # type: ignore[no-untyped-def]
        try:
            geom = shape(self.model_dump())
        except Exception as exc:  # shapely lanza excepciones de varios tipos cuando la entrada está mal formada
            raise ValueError("malformed geometry") from exc
        if geom.is_empty or not geom.is_valid:
            raise ValueError(f"invalid geometry: {explain_validity(geom)}")
        minx, miny, maxx, maxy = geom.bounds
        if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
            raise ValueError("coordinates must be WGS84 longitude/latitude")
        return geom


class BBoxIn(Schema):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)


class Message(Schema):
    message: str
