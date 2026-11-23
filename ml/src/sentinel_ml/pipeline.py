"""Pipeline de detección de cambios de punta a punta.

Etapas (ver docs/SATELLITE_PIPELINE.md):

  grilla → búsqueda de escenas → por tile [leer ventanas COG → máscara de nubes → compuesto
  por mediana → detector] → rásters de evidencia → vectorización → quicklooks →
  filtro de calidad → PipelineResult

Reanudación: cada tile terminado escribe ``tiles/<row>_<col>.json``. Si se vuelve a correr
con el mismo ``out_dir`` y los mismos parámetros se saltan los tiles terminados; el manifiesto
garantiza que los parámetros coincidan, si no, se rechaza el directorio de la ejecución.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling

from .composite import composite_tile, to_rgb8
from .config import DEFAULT_CONFIG, PipelineConfig
from .contracts import (
    CONTRACT_VERSION,
    Artifacts,
    BBox,
    CompositeInfo,
    DateWindow,
    PipelineResult,
    SceneRef,
)
from .detectors import ChangeDetector
from .grid import AnalysisGrid, build_grid, grid_bounds_wgs84
from .raster_io import gdal_env
from .stac import search_scenes
from .vectorize import vectorize

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, float], None]
INVALID_I16 = -32768
QUICKLOOK_MAX_SIDE = 1600


class PipelineTimeoutError(RuntimeError):
    pass


class ManifestMismatchError(RuntimeError):
    pass


def _noop(stage: str, fraction: float) -> None:
    return None


def run_pipeline(
    aoi: BBox,
    reference: DateWindow,
    observation: DateWindow,
    out_dir: Path,
    detector: ChangeDetector,
    config: PipelineConfig = DEFAULT_CONFIG,
    reference_scenes: list[SceneRef] | None = None,
    observation_scenes: list[SceneRef] | None = None,
    progress: ProgressFn = _noop,
    max_runtime_s: float | None = None,
) -> PipelineResult:
    started = time.monotonic()
    out_dir.mkdir(parents=True, exist_ok=True)
    grid = build_grid(aoi, config.limits)
    progress("grid", 0.02)

    max_n = config.limits.max_scenes_per_period
    max_cc = config.quality.max_scene_cloud_cover
    notes: list[str] = []
    ref_scenes = _select(reference_scenes, aoi, reference, max_cc, max_n, "referencia", notes)
    obs_scenes = _select(observation_scenes, aoi, observation, max_cc, max_n, "observación", notes)
    progress("search", 0.05)

    _check_manifest(out_dir, aoi, reference, observation, grid, ref_scenes, obs_scenes, detector, config)
    _write_scene_inventory(out_dir, ref_scenes + obs_scenes)

    if not ref_scenes or not obs_scenes:
        missing = "referencia" if not ref_scenes else "observación"
        notes.append(f"Sin imágenes disponibles para el periodo de {missing}.")
        return _empty_result(aoi, grid, detector, config, ref_scenes, obs_scenes, notes)

    work = out_dir / "work"
    work.mkdir(exist_ok=True)
    tiles_dir = out_dir / "tiles"
    tiles_dir.mkdir(exist_ok=True)
    evidence_path, ref_rgb_path, obs_rgb_path = work / "evidence.tif", work / "reference_rgb.tif", work / "observation_rgb.tif"
    _ensure_raster(evidence_path, grid, 4, "int16", INVALID_I16)
    _ensure_raster(ref_rgb_path, grid, 3, "uint8", None)
    _ensure_raster(obs_rgb_path, grid, 3, "uint8", None)

    tiles = list(grid.tiles(config.limits.tile_size))
    with gdal_env():
        for i, (r, c, window) in enumerate(tiles):
            marker = tiles_dir / f"{r}_{c}.json"
            if marker.exists():
                continue
            if max_runtime_s is not None and time.monotonic() - started > max_runtime_s:
                raise PipelineTimeoutError("pipeline exceeded its runtime budget")
            ref = composite_tile(ref_scenes, grid, window)
            obs = composite_tile(obs_scenes, grid, window)
            valid = ref.valid & obs.valid
            out = detector.predict(ref.bands, obs.bands, valid)
            ev = np.stack(
                [
                    _to_i16(out.score, valid),
                    out.signal.astype(np.int16),
                    _to_i16(out.ndvi_drop, valid),
                    _to_i16(out.nbr_drop, valid),
                ]
            )
            with rasterio.open(evidence_path, "r+") as dst:
                dst.write(ev, window=window)
            with rasterio.open(ref_rgb_path, "r+") as dst:
                dst.write(np.moveaxis(to_rgb8(ref.bands), -1, 0), window=window)
            with rasterio.open(obs_rgb_path, "r+") as dst:
                dst.write(np.moveaxis(to_rgb8(obs.bands), -1, 0), window=window)
            marker.write_text(
                json.dumps(
                    {
                        "pixels": int(valid.size),
                        "ref_valid": int(ref.valid.sum()),
                        "obs_valid": int(obs.valid.sum()),
                        "ref_scenes": ref.contributing,
                        "obs_scenes": obs.contributing,
                    }
                )
            )
            progress("tiles", 0.05 + 0.80 * (i + 1) / len(tiles))

    stats = [json.loads((tiles_dir / f"{r}_{c}.json").read_text(encoding="utf-8")) for r, c, _ in tiles]
    total = sum(s["pixels"] for s in stats)
    ref_frac = sum(s["ref_valid"] for s in stats) / total
    obs_frac = sum(s["obs_valid"] for s in stats) / total
    ref_used = sorted({sid for s in stats for sid in s["ref_scenes"]})
    obs_used = sorted({sid for s in stats for sid in s["obs_scenes"]})

    with rasterio.open(evidence_path) as src:
        ev = src.read()
    invalid = ev[0] == INVALID_I16
    score = np.where(invalid, np.nan, ev[0] / 1000.0).astype(np.float32)
    signal = ev[1].astype(np.uint8)
    d_ndvi = np.where(invalid, np.nan, ev[2] / 1000.0).astype(np.float32)
    d_nbr = np.where(invalid, np.nan, ev[3] / 1000.0).astype(np.float32)
    del ev
    findings = vectorize(score, signal, d_ndvi, d_nbr, grid, config.vector, config.severity)
    progress("vectorize", 0.92)

    artifacts = _write_quicklooks(out_dir, grid, ref_rgb_path, obs_rgb_path, score, config.vector.score_threshold)
    changed_px = int(np.sum(np.nan_to_num(score) >= config.vector.score_threshold))
    progress("quicklooks", 0.97)

    q = config.quality
    quality_blocking = False
    if ref_frac < q.min_valid_fraction:
        quality_blocking = True
        notes.append(f"Solo el {ref_frac:.0%} del área de referencia está libre de nubes (mínimo {q.min_valid_fraction:.0%}).")
    if obs_frac < q.min_valid_fraction:
        quality_blocking = True
        notes.append(f"Solo el {obs_frac:.0%} del área observada está libre de nubes (mínimo {q.min_valid_fraction:.0%}).")

    by_id = {s.scene_id: s for s in ref_scenes + obs_scenes}
    result = PipelineResult(
        contract_version=CONTRACT_VERSION,
        detector_id=detector.detector_id,
        detector_version=detector.version,
        detector_kind=detector.kind,
        aoi=aoi.as_list(),
        reference=_composite_info("reference", ref_used or [s.scene_id for s in ref_scenes], by_id, ref_frac),
        observation=_composite_info("observation", obs_used or [s.scene_id for s in obs_scenes], by_id, obs_frac),
        quality_ok=not quality_blocking,
        quality_notes=notes,
        analysed_area_ha=round(grid.area_ha, 3),
        changed_area_ha=round(changed_px * grid.pixel_area_ha, 3),
        findings=findings,
        artifacts=artifacts,
        parameters={"detector": detector.parameters(), "pipeline": asdict(config), "grid": grid.cache_key()},
    )
    (out_dir / "result.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    progress("done", 1.0)
    return result


def _select(
    given: list[SceneRef] | None,
    aoi: BBox,
    window: DateWindow,
    max_cloud: float,
    max_n: int,
    label: str,
    notes: list[str],
) -> list[SceneRef]:
    if given is not None:
        return given[:max_n]
    found = search_scenes(aoi, window, max_cloud)
    if found.legacy and found.scenes:
        notes.append(
            f"El periodo de {label} no tiene imágenes Collection-1; se usó la colección heredada "
            "(la radiometría puede diferir ligeramente)."
        )
    return found.scenes[:max_n]


def _write_scene_inventory(out_dir: Path, scenes: list[SceneRef]) -> None:
    """Metadatos de cada escena candidata, los usa el inventario del backend."""
    inventory = {
        s.scene_id: {
            "collection": s.collection,
            "acquired_at": s.acquired_at.isoformat(),
            "cloud_cover": s.cloud_cover,
            "epsg": s.epsg,
            "tile_id": s.tile_id,
            "assets": {k: v for k, v in s.assets.items() if ":" not in k},
        }
        for s in scenes
    }
    (out_dir / "scenes.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")


def _to_i16(arr: np.ndarray, valid: np.ndarray) -> np.ndarray:
    out = np.clip(np.nan_to_num(arr, nan=0.0) * 1000, -32000, 32000).astype(np.int16)
    out[~valid] = INVALID_I16
    return out


def _ensure_raster(path: Path, grid: AnalysisGrid, count: int, dtype: str, nodata: float | None) -> None:
    if path.exists():
        return
    profile = {
        "driver": "GTiff",
        "width": grid.width,
        "height": grid.height,
        "count": count,
        "dtype": dtype,
        "crs": f"EPSG:{grid.epsg}",
        "transform": grid.transform,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile):
        pass


def _composite_info(period: str, ids: list[str], by_id: dict[str, SceneRef], frac: float) -> CompositeInfo:
    times = [by_id[i].acquired_at for i in ids if i in by_id]
    return CompositeInfo(period=period, scene_ids=ids, first_acquired=min(times), last_acquired=max(times), valid_fraction=round(frac, 4))


def _write_quicklooks(out_dir: Path, grid: AnalysisGrid, ref_rgb: Path, obs_rgb: Path, score: np.ndarray, thr: float) -> Artifacts:
    scale = min(1.0, QUICKLOOK_MAX_SIDE / max(grid.width, grid.height))
    w, h = max(1, int(grid.width * scale)), max(1, int(grid.height * scale))
    for src_path, name in ((ref_rgb, "reference.png"), (obs_rgb, "observation.png")):
        with rasterio.open(src_path) as src:
            rgb = src.read(out_shape=(3, h, w), resampling=Resampling.average)
        Image.fromarray(np.moveaxis(rgb, 0, -1)).save(out_dir / name, optimize=True)

    # Superposición: ámbar (#E7AA43) para puntajes moderados, rojo (#D95D50) para los fuertes.
    s = np.nan_to_num(score)
    rgba = np.zeros((*s.shape, 4), np.uint8)
    hit = s >= thr
    strong = s >= 0.75
    rgba[hit] = (231, 170, 67, 200)
    rgba[strong] = (217, 93, 80, 220)
    Image.fromarray(rgba).resize((w, h), Image.NEAREST).save(out_dir / "change_overlay.png", optimize=True)

    t = grid.transform
    corners_utm = [
        (t.c, t.f),
        (t.c + grid.width * t.a, t.f),
        (t.c + grid.width * t.a, t.f + grid.height * t.e),
        (t.c, t.f + grid.height * t.e),
    ]
    tr = Transformer.from_crs(grid.epsg, 4326, always_xy=True)
    corners = [[round(v, 7) for v in tr.transform(x, y)] for x, y in corners_utm]
    return Artifacts(
        reference_rgb="reference.png",
        observation_rgb="observation.png",
        change_overlay="change_overlay.png",
        evidence="work/evidence.tif",
        bounds=[round(v, 7) for v in grid_bounds_wgs84(grid)],
        corners=corners,
    )


def _check_manifest(
    out_dir: Path,
    aoi: BBox,
    reference: DateWindow,
    observation: DateWindow,
    grid: AnalysisGrid,
    ref_scenes: list[SceneRef],
    obs_scenes: list[SceneRef],
    detector: ChangeDetector,
    config: PipelineConfig,
) -> None:
    payload = {
        "aoi": aoi.as_list(),
        "reference": reference.as_interval(),
        "observation": observation.as_interval(),
        "grid": grid.cache_key(),
        "ref_scenes": [s.scene_id for s in ref_scenes],
        "obs_scenes": [s.scene_id for s in obs_scenes],
        "detector": f"{detector.detector_id}@{detector.version}",
        "config": hashlib.sha256(json.dumps(asdict(config), sort_keys=True).encode()).hexdigest(),
    }
    path = out_dir / "manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != payload:
            raise ManifestMismatchError(f"run directory {out_dir} belongs to a different run")
        log.info("resuming run in %s", out_dir)
        return
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _empty_result(
    aoi: BBox,
    grid: AnalysisGrid,
    detector: ChangeDetector,
    config: PipelineConfig,
    ref_scenes: list[SceneRef],
    obs_scenes: list[SceneRef],
    notes: list[str],
) -> PipelineResult:
    def info(period: str, scenes: list[SceneRef]) -> CompositeInfo:
        if not scenes:
            now = datetime.now(UTC)
            return CompositeInfo(period, [], now, now, 0.0)
        return CompositeInfo(
            period, [s.scene_id for s in scenes], min(s.acquired_at for s in scenes), max(s.acquired_at for s in scenes), 0.0
        )

    return PipelineResult(
        contract_version=CONTRACT_VERSION,
        detector_id=detector.detector_id,
        detector_version=detector.version,
        detector_kind=detector.kind,
        aoi=aoi.as_list(),
        reference=info("reference", ref_scenes),
        observation=info("observation", obs_scenes),
        quality_ok=False,
        quality_notes=notes,
        analysed_area_ha=round(grid.area_ha, 3),
        changed_area_ha=0.0,
        findings=[],
        artifacts=None,
        parameters={"detector": detector.parameters(), "pipeline": asdict(config)},
    )
