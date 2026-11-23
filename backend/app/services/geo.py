"""Utilidades de geometría (Shapely ↔ PostGIS) y medidas geodésicas."""

from __future__ import annotations

from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from pyproj import Geod
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.geometry.base import BaseGeometry

_GEOD = Geod(ellps="WGS84")


def as_multipolygon(geom: BaseGeometry) -> MultiPolygon:
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, (Polygon, MultiPolygon))]
    parts: list[Polygon] = []
    for p in polys:
        parts.extend(p.geoms if isinstance(p, MultiPolygon) else [p])
    if not parts:
        raise ValueError("geometry has no polygonal parts")
    return MultiPolygon(parts)


def to_db(geom: BaseGeometry) -> Any:
    return from_shape(geom, srid=4326)


def from_db(value: Any) -> BaseGeometry:
    return to_shape(value)


def geojson(value: Any) -> dict[str, Any]:
    return dict(mapping(from_db(value)))


def area_km2(geom: BaseGeometry) -> float:
    return abs(_GEOD.geometry_area_perimeter(geom)[0]) / 1e6


def area_ha(geom: BaseGeometry) -> float:
    return abs(_GEOD.geometry_area_perimeter(geom)[0]) / 1e4


def centroid_of(value: Any) -> tuple[float, float]:
    c = from_db(value).centroid
    return (round(c.x, 6), round(c.y, 6))


def bbox_of(value: Any) -> tuple[float, float, float, float]:
    b = from_db(value).bounds
    return (round(b[0], 6), round(b[1], 6), round(b[2], 6), round(b[3], 6))
