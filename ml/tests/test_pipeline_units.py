"""Tests unitarios deterministas (sin red) para el pipeline satelital."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest
from rasterio.transform import from_origin

from sentinel_ml.composite import valid_mask_from_scl
from sentinel_ml.config import PipelineLimits, SeverityThresholds, SpectralThresholds, VectorThresholds
from sentinel_ml.contracts import BBox, ChangeSignal, DateWindow, SceneRef, Severity
from sentinel_ml.detectors import SpectralBaselineDetector, get_detector
from sentinel_ml.grid import AnalysisGrid, AOITooLargeError, build_grid, utm_epsg_for
from sentinel_ml.indices import nbr, ndvi
from sentinel_ml.model.metrics import ConfusionMatrix
from sentinel_ml.severity import classify
from sentinel_ml.stac import UntrustedAssetError, dedupe_legacy, validate_asset_href
from sentinel_ml.vectorize import vectorize

FOREST = {"blue": 0.02, "green": 0.05, "red": 0.03, "nir": 0.35, "swir16": 0.15, "swir22": 0.07}
BARE = {"blue": 0.08, "green": 0.11, "red": 0.14, "nir": 0.22, "swir16": 0.30, "swir22": 0.22}
BURN = {"blue": 0.04, "green": 0.05, "red": 0.06, "nir": 0.09, "swir16": 0.16, "swir22": 0.14}


def scene(values: dict[str, float], shape=(64, 64)) -> dict[str, np.ndarray]:
    return {k: np.full(shape, v, np.float32) for k, v in values.items()}


def paste(dst: dict[str, np.ndarray], src: dict[str, float], rows: slice, cols: slice) -> None:
    for k, v in src.items():
        dst[k][rows, cols] = v


# --- índices -------------------------------------------------------------------


def test_ndvi_ranges_and_nan_propagation():
    nir = np.array([0.4, 0.2, np.nan], np.float32)
    red = np.array([0.04, 0.2, 0.1], np.float32)
    out = ndvi(nir, red)
    assert out[0] == pytest.approx(0.818, abs=1e-3)
    assert out[1] == pytest.approx(0.0)
    assert np.isnan(out[2])


def test_index_zero_denominator_is_nan():
    assert np.isnan(nbr(np.zeros(1, np.float32), np.zeros(1, np.float32))[0])


# --- máscara de nubes ----------------------------------------------------------


def test_scl_mask_rejects_clouds_shadows_and_nodata():
    scl = np.array([0, 3, 4, 5, 6, 8, 9, 10, 11], np.uint8)
    assert valid_mask_from_scl(scl).tolist() == [False, False, True, True, True, False, False, False, False]


# --- detector espectral ----------------------------------------------------------


def test_spectral_detector_flags_clearing_not_stable_forest():
    ref, obs = scene(FOREST), scene(FOREST)
    paste(obs, BARE, slice(10, 30), slice(10, 30))
    out = SpectralBaselineDetector().predict(ref, obs, np.ones((64, 64), bool))
    assert np.nanmin(out.score[12:28, 12:28]) > 0.5
    assert np.nanmax(out.score[40:, 40:]) == 0.0
    assert out.signal[20, 20] == 1


def test_spectral_detector_ignores_pixels_that_were_not_forest():
    """Suelo desnudo que queda más desnudo (agricultura) no se puede llamar deforestación."""
    ref, obs = scene(BARE), scene(BARE)
    paste(obs, {k: v * 1.3 for k, v in BARE.items()}, slice(0, 64), slice(0, 64))
    out = SpectralBaselineDetector().predict(ref, obs, np.ones((64, 64), bool))
    assert np.nanmax(out.score) == 0.0


def test_spectral_detector_hints_burn_scars():
    ref, obs = scene(FOREST), scene(FOREST)
    paste(obs, BURN, slice(10, 30), slice(10, 30))
    out = SpectralBaselineDetector().predict(ref, obs, np.ones((64, 64), bool))
    assert out.signal[20, 20] == 2


def test_spectral_detector_respects_invalid_mask():
    ref, obs = scene(FOREST), scene(BARE)
    valid = np.ones((64, 64), bool)
    valid[:, :32] = False
    out = SpectralBaselineDetector().predict(ref, obs, valid)
    assert np.isnan(out.score[:, :30]).all()


def test_detector_registry_falls_back_without_checkpoint(tmp_path):
    det = get_detector("auto", tmp_path / "missing.pt")
    assert det.kind == "rule-based"
    with pytest.raises(FileNotFoundError):
        get_detector("siamese-unet", tmp_path / "missing.pt")


# --- grilla ----------------------------------------------------------------------


def test_utm_zone_selection():
    assert utm_epsg_for(-74.2, 2.2) == 32618
    assert utm_epsg_for(-70.0, -4.0) == 32719


def test_grid_dimensions_and_tiling():
    g = build_grid(BBox(-74.25, 2.15, -74.15, 2.25), PipelineLimits())
    assert 1100 < g.width < 1130 and 1100 < g.height < 1120
    tiles = list(g.tiles(1024))
    assert len(tiles) == 4
    assert sum(int(w.width * w.height) for *_, w in tiles) == g.width * g.height


def test_grid_rejects_oversized_aoi():
    with pytest.raises(AOITooLargeError):
        build_grid(BBox(-75, 0, -72, 3), PipelineLimits())


def test_bbox_and_window_validation():
    with pytest.raises(ValueError):
        BBox(10, 0, 5, 1)
    with pytest.raises(ValueError):
        DateWindow(datetime(2024, 2, 1).date(), datetime(2024, 1, 1).date())


# --- vectorización ---------------------------------------------------------------


def _grid(n=100) -> AnalysisGrid:
    return AnalysisGrid(32618, from_origin(500000, 250000, 10, 10), n, n, 10.0)


def test_vectorize_area_and_minimum_mapping_unit():
    score = np.zeros((100, 100), np.float32)
    score[10:30, 10:30] = 0.8  # 400 px = 4 ha
    score[60:63, 60:63] = 0.9  # 9 px  = 0.09 ha → por debajo de la MMU
    sig = np.where(score > 0, 1, 0).astype(np.uint8)
    findings = vectorize(score, sig, score * 0.5, score * 0.5, _grid(), VectorThresholds(), SeverityThresholds())
    assert len(findings) == 1
    f = findings[0]
    assert f.area_ha == pytest.approx(4.0, rel=0.05)
    assert f.signal == ChangeSignal.VEGETATION_LOSS
    assert f.geometry["type"] in ("Polygon", "MultiPolygon")
    lon, lat = f.centroid
    assert -76 < lon < -74 and 2 < lat < 2.5


def test_vectorize_reports_context_quality():
    score = np.full((100, 100), np.nan, np.float32)
    score[0:40, 0:40] = 0.0
    score[10:30, 10:30] = 0.8
    findings = vectorize(score, np.ones((100, 100), np.uint8), score, score, _grid(), VectorThresholds(), SeverityThresholds())
    assert len(findings) == 1 and 0.5 < findings[0].valid_fraction <= 1.0


def test_severity_levels():
    t = SeverityThresholds()
    assert classify(0.6, 0.9, t) == Severity.LOW
    assert classify(2.0, 0.6, t) == Severity.MODERATE
    assert classify(5.0, 0.7, t) == Severity.HIGH
    assert classify(12.0, 0.8, t) == Severity.PRIORITY
    assert classify(12.0, 0.56, t) == Severity.MODERATE


# --- seguridad de STAC -----------------------------------------------------------


@pytest.mark.parametrize(
    "href",
    [
        "http://sentinel-cogs.s3.us-west-2.amazonaws.com/a/B04.tif",
        "https://169.254.169.254/latest/meta-data.tif",
        "https://evil.example.com/B04.tif",
        "file:///etc/passwd",
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/a/B04.jp2",
    ],
)
def test_untrusted_assets_rejected(href):
    with pytest.raises(UntrustedAssetError):
        validate_asset_href(href)


def test_legacy_dedupe_prefers_original_processing():
    def ref(sid):
        return SceneRef(sid, "earth-search", "sentinel-2-l2a", datetime(2020, 1, 14, tzinfo=UTC), 5.0, 32618, {}, "18NWH")

    kept = dedupe_legacy([ref("S2B_18NWH_20200114_1_L2A"), ref("S2B_18NWH_20200114_0_L2A")])
    assert [s.scene_id for s in kept] == ["S2B_18NWH_20200114_0_L2A"]


# --- métricas --------------------------------------------------------------------


def test_confusion_matrix_metrics():
    cm = ConfusionMatrix()
    pred = np.array([1, 1, 0, 0, 1], bool)
    target = np.array([1, 0, 0, 1, 1], bool)
    cm.update(pred, target)
    r = cm.report()
    assert r["tp"] == 2 and r["fp"] == 1 and r["fn"] == 1 and r["tn"] == 1
    assert r["precision"] == pytest.approx(2 / 3)
    assert r["iou"] == pytest.approx(0.5)
    assert r["f1"] == pytest.approx(2 / 3)


def test_thresholds_are_configurable():
    strict = SpectralThresholds(min_ndvi_drop=0.9)
    ref, obs = scene(FOREST), scene(BARE)
    out = SpectralBaselineDetector(strict).predict(ref, obs, np.ones((64, 64), bool))
    assert np.nanmax(out.score) == 0.0
