"""Grilla de análisis: un ráster UTM fijo sobre el que se remuestrea cada escena.

Usar la misma grilla para los dos periodos garantiza alineación píxel a píxel, que es
obligatoria para detectar cambios (si quedan mal registradas aparecen bordes falsos).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass

from pyproj import Transformer
from rasterio.transform import Affine, from_origin
from rasterio.windows import Window

from .config import PipelineLimits
from .contracts import BBox


class AOITooLargeError(ValueError):
    pass


def utm_epsg_for(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    zone = min(max(zone, 1), 60)
    return (32600 if lat >= 0 else 32700) + zone


@dataclass(frozen=True)
class AnalysisGrid:
    epsg: int
    transform: Affine
    width: int
    height: int
    resolution: float

    @property
    def pixel_area_ha(self) -> float:
        return (self.resolution * self.resolution) / 10_000.0

    @property
    def area_ha(self) -> float:
        return self.width * self.height * self.pixel_area_ha

    def tiles(self, size: int) -> Iterator[tuple[int, int, Window]]:
        for row in range(0, self.height, size):
            for col in range(0, self.width, size):
                yield (
                    row // size,
                    col // size,
                    Window(col, row, min(size, self.width - col), min(size, self.height - row)),
                )

    def cache_key(self) -> str:
        t = self.transform
        return f"{self.epsg}_{t.c:.1f}_{t.f:.1f}_{self.width}x{self.height}_{self.resolution:g}"


def build_grid(bbox: BBox, limits: PipelineLimits) -> AnalysisGrid:
    lon_c = (bbox.west + bbox.east) / 2
    lat_c = (bbox.south + bbox.north) / 2
    epsg = utm_epsg_for(lon_c, lat_c)
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = tr.transform(
        [bbox.west, bbox.east, bbox.west, bbox.east],
        [bbox.south, bbox.south, bbox.north, bbox.north],
    )
    res = limits.resolution_m
    minx = math.floor(min(xs) / res) * res
    maxx = math.ceil(max(xs) / res) * res
    miny = math.floor(min(ys) / res) * res
    maxy = math.ceil(max(ys) / res) * res
    width = int(round((maxx - minx) / res))
    height = int(round((maxy - miny) / res))
    area_km2 = (maxx - minx) * (maxy - miny) / 1e6
    if area_km2 > limits.max_aoi_km2:
        raise AOITooLargeError(f"AOI {area_km2:.0f} km² exceeds limit {limits.max_aoi_km2:.0f} km²")
    if width > limits.max_pixels_per_side or height > limits.max_pixels_per_side:
        raise AOITooLargeError("AOI exceeds maximum raster dimensions")
    if width < 8 or height < 8:
        raise AOITooLargeError("AOI is too small to analyse")
    return AnalysisGrid(epsg, from_origin(minx, maxy, res, res), width, height, res)


def grid_bounds_wgs84(grid: AnalysisGrid) -> list[float]:
    t = grid.transform
    minx, maxy = t.c, t.f
    maxx = minx + grid.width * t.a
    miny = maxy + grid.height * t.e
    tr = Transformer.from_crs(grid.epsg, 4326, always_xy=True)
    lons, lats = tr.transform([minx, maxx, minx, maxx], [miny, miny, maxy, maxy])
    return [min(lons), min(lats), max(lons), max(lats)]
