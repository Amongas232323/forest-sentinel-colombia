"""Ráster de cambio → polígonos georreferenciados con evidencia por polígono."""

from __future__ import annotations

from collections import defaultdict

import cv2
import numpy as np
from pyproj import Transformer
from rasterio import features
from shapely.geometry import mapping, shape
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union

from .config import SeverityThresholds, VectorThresholds
from .contracts import ChangeSignal, Finding
from .detectors.base import SIGNAL_BURN, SIGNAL_FLOOD
from .grid import AnalysisGrid
from .severity import classify

_SIGNAL_MAP = {SIGNAL_BURN: ChangeSignal.POSSIBLE_BURN, SIGNAL_FLOOD: ChangeSignal.POSSIBLE_FLOODING}
_CONTEXT_MARGIN_PX = 10


def vectorize(
    score: np.ndarray,
    signal: np.ndarray,
    ndvi_drop: np.ndarray,
    nbr_drop: np.ndarray,
    grid: AnalysisGrid,
    vt: VectorThresholds,
    st: SeverityThresholds,
) -> list[Finding]:
    """``score`` es float32 0..1 con NaN en los píxeles inválidos."""
    valid = np.isfinite(score)
    binary = (np.nan_to_num(score) >= vt.score_threshold).astype(np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n <= 1:
        return []

    pixel_ha = grid.pixel_area_ha
    min_px = max(1, int(np.ceil(vt.min_area_ha / pixel_ha)))
    keep = np.zeros(n, dtype=bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_px
    if not keep.any():
        return []
    labels[~keep[labels]] = 0

    flat = labels.ravel()
    counts = np.bincount(flat, minlength=n).astype(np.float64)
    safe = np.maximum(counts, 1)
    s = np.nan_to_num(score).ravel()
    mean_score = np.bincount(flat, weights=s, minlength=n) / safe
    mean_dndvi = np.bincount(flat, weights=np.nan_to_num(ndvi_drop).ravel(), minlength=n) / safe
    mean_dnbr = np.bincount(flat, weights=np.nan_to_num(nbr_drop).ravel(), minlength=n) / safe
    max_score = np.zeros(n)
    np.maximum.at(max_score, flat, s)
    sig_counts = np.zeros((n, 4), dtype=np.int64)
    np.add.at(sig_counts, (flat, np.clip(signal.ravel(), 0, 3)), 1)

    polys: dict[int, list] = defaultdict(list)
    for geom, value in features.shapes(labels.astype(np.int32), mask=labels > 0, transform=grid.transform, connectivity=8):
        polys[int(value)].append(shape(geom))

    to_wgs84 = Transformer.from_crs(grid.epsg, 4326, always_xy=True).transform
    findings: list[Finding] = []
    for label, parts in polys.items():
        geom_utm = unary_union(parts).simplify(vt.simplify_tolerance_m, preserve_topology=True)
        if geom_utm.is_empty:
            continue
        area_ha = float(counts[label] * pixel_ha)
        x, y, w, h = stats[label, :4]
        m = _CONTEXT_MARGIN_PX
        ctx = valid[max(0, y - m) : y + h + m, max(0, x - m) : x + w + m]
        geom = shp_transform(to_wgs84, geom_utm)  # Polygon o MultiPolygon
        c = geom.centroid
        dominant = int(np.argmax(sig_counts[label, 1:]) + 1)
        score_mean = float(mean_score[label])
        findings.append(
            Finding(
                geometry=mapping(geom),
                centroid=(round(c.x, 6), round(c.y, 6)),
                area_ha=round(area_ha, 3),
                mean_score=score_mean,
                max_score=float(max_score[label]),
                severity=classify(area_ha, score_mean, st),
                signal=_SIGNAL_MAP.get(dominant, ChangeSignal.VEGETATION_LOSS),
                mean_ndvi_drop=float(mean_dndvi[label]),
                mean_nbr_drop=float(mean_dnbr[label]),
                valid_fraction=float(ctx.mean()) if ctx.size else 0.0,
            )
        )
    findings.sort(key=lambda f: f.area_ha, reverse=True)
    return findings
