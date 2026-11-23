"""Enmascarado de nubes y composición por mediana para cada periodo."""

from __future__ import annotations

import logging
import warnings
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass

import numpy as np
from rasterio.enums import Resampling
from rasterio.windows import Window

from .contracts import SceneRef
from .grid import AnalysisGrid
from .raster_io import read_window

log = logging.getLogger(__name__)

REFLECTANCE_BANDS = ("blue", "green", "red", "nir", "swir16", "swir22")

# Valores de la Scene Classification Layer de Sentinel-2 que consideramos *inválidos*:
# 0 sin datos, 1 saturado/defectuoso, 3 sombra de nube, 8 nube prob. media,
# 9 nube prob. alta, 10 cirros delgados, 11 nieve/hielo.
SCL_INVALID = np.array([0, 1, 3, 8, 9, 10, 11], dtype=np.uint8)


def valid_mask_from_scl(scl: np.ndarray) -> np.ndarray:
    return ~np.isin(scl.astype(np.uint8), SCL_INVALID)


@dataclass
class TileComposite:
    bands: dict[str, np.ndarray]  # reflectancia con NaN donde es inválido
    valid: np.ndarray  # bool
    contributing: list[str]  # ids de escenas que aportaron al menos un píxel


IO_WORKERS = 8
# Tope para una lectura remota; el timeout HTTP de GDAL cubre los sockets colgados,
# y esto cubre también bloqueos dentro del proceso, para que la ejecución falle en vez de quedarse pegada para siempre.
READ_TIMEOUT_S = 240


class RemoteReadTimeoutError(TimeoutError):
    pass


def read_scene_tile(
    scene: SceneRef, grid: AnalysisGrid, window: Window, pool: ThreadPoolExecutor | None = None
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    scl = read_window(scene.assets["scl"], grid, window, Resampling.nearest, dtype="uint8")
    valid = valid_mask_from_scl(scl)
    bands: dict[str, np.ndarray] = {}
    if not valid.any():
        return bands, valid

    def fetch(name: str) -> np.ndarray:
        return read_window(scene.assets[name], grid, window, Resampling.bilinear, dtype="float32")

    if pool is None:
        raws = [fetch(n) for n in REFLECTANCE_BANDS]
    else:
        futures = [pool.submit(fetch, n) for n in REFLECTANCE_BANDS]
        try:
            raws = [f.result(timeout=READ_TIMEOUT_S) for f in futures]
        except FuturesTimeout as exc:
            raise RemoteReadTimeoutError(f"band read timed out for {scene.scene_id}") from exc
    for name, dn in zip(REFLECTANCE_BANDS, raws, strict=True):
        scale = float(scene.assets.get(f"{name}:scale", 0.0001))
        offset = float(scene.assets.get(f"{name}:offset", 0.0))
        refl = dn * scale + offset
        refl[(dn == 0) | ~valid] = np.nan
        # La reflectancia por fuera de un rango físicamente posible se toma como inválida.
        refl[(refl < -0.05) | (refl > 1.5)] = np.nan
        bands[name] = refl.astype(np.float32)
    return bands, valid


def composite_tile(scenes: list[SceneRef], grid: AnalysisGrid, window: Window) -> TileComposite:
    """Mediana por píxel de todas las observaciones válidas en ``scenes``."""
    shape = (int(window.height), int(window.width))
    stacks: dict[str, list[np.ndarray]] = {b: [] for b in REFLECTANCE_BANDS}
    contributing: list[str] = []
    # Dos pools: las tareas de escena esperan a las de banda, entonces compartir un solo pool podría causar deadlock.
    band_pool, scene_pool = ThreadPoolExecutor(IO_WORKERS), ThreadPoolExecutor(len(scenes) or 1)
    try:
        futures = [scene_pool.submit(read_scene_tile, sc, grid, window, band_pool) for sc in scenes]
        results = [f.result(timeout=READ_TIMEOUT_S * 2) for f in futures]
    except FuturesTimeout as exc:
        raise RemoteReadTimeoutError("scene read timed out") from exc
    finally:
        # Nunca nos quedamos bloqueados por un hilo pegado: retornamos (o lanzamos) y dejamos que muera solo.
        band_pool.shutdown(wait=False, cancel_futures=True)
        scene_pool.shutdown(wait=False, cancel_futures=True)
    for scene, (bands, _valid) in zip(scenes, results, strict=True):
        if not bands:
            continue
        contributing.append(scene.scene_id)
        for name in REFLECTANCE_BANDS:
            stacks[name].append(bands[name])
    if not contributing:
        empty = np.full(shape, np.nan, dtype=np.float32)
        return TileComposite({b: empty.copy() for b in REFLECTANCE_BANDS}, np.zeros(shape, bool), [])
    out: dict[str, np.ndarray] = {}
    with warnings.catch_warnings():
        # nanmedian lanza warnings con píxeles todo-NaN; esos se quedan en NaN a propósito.
        warnings.simplefilter("ignore", category=RuntimeWarning)
        for name in REFLECTANCE_BANDS:
            out[name] = np.nanmedian(np.stack(stacks[name]), axis=0).astype(np.float32)
    valid = np.all([np.isfinite(out[b]) for b in ("red", "nir", "swir22")], axis=0)
    return TileComposite(out, valid, contributing)


def to_rgb8(bands: dict[str, np.ndarray], gain: float = 3.5) -> np.ndarray:
    """Render en color verdadero a 8 bits con ganancia fija (para poder comparar entre fechas)."""
    rgb = np.stack([bands["red"], bands["green"], bands["blue"]], axis=-1)
    rgb = np.nan_to_num(rgb, nan=0.0) * gain
    rgb = np.clip(rgb, 0, 1) ** (1 / 1.2)
    return (rgb * 255).astype(np.uint8)
