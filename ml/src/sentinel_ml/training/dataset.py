"""Arma muestras de entrenamiento bi-temporales con etiquetas reales (débiles).

Entradas por AOI: compuestos por mediana de Sentinel-2 L2A para dos temporadas secas, hechos
con el mismo código que en producción (composite.py), y etiquetas del ``lossyear`` de
Global Forest Change de Hansen et al. (University of Maryland, 30 m, CC BY 4.0).

Política de etiquetas (documentada en AI_MODEL_DOCUMENTATION.md §5):
  1   = año de pérdida == ``positive_year`` (entre los dos compuestos)
  255 = ignorar: año de pérdida == ``positive_year + 1`` (el momento es ambiguo respecto al
        compuesto de observación) o píxeles inválidos (nube)
  0   = todo lo demás
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from ..composite import REFLECTANCE_BANDS, composite_tile
from ..config import PipelineLimits
from ..contracts import BBox, DateWindow
from ..grid import AnalysisGrid, build_grid
from ..raster_io import gdal_env
from ..stac import search_scenes

log = logging.getLogger(__name__)

IGNORE = 255
HANSEN_URL = "https://storage.googleapis.com/earthenginepartners-hansen/{v}/Hansen_{v}_lossyear_{tile}.tif"
HANSEN_HOSTS = frozenset({"storage.googleapis.com"})


@dataclass(frozen=True)
class AOISpec:
    name: str
    bbox: tuple[float, float, float, float]
    split: str  # train | val | test


def hansen_tile(lon: float, lat: float) -> str:
    """Los tiles de Hansen son de 10°×10° y se nombran por su esquina superior izquierda, p. ej. 10N_080W."""
    top = int(np.ceil(lat / 10.0) * 10)
    left = int(np.floor(lon / 10.0) * 10)
    ns = f"{abs(top):02d}{'N' if top >= 0 else 'S'}"
    ew = f"{abs(left):03d}{'E' if left >= 0 else 'W'}"
    return f"{ns}_{ew}"


def read_hansen(grid: AnalysisGrid, bbox: BBox, version: str = "GFC-2024-v1.12") -> np.ndarray:
    tile = hansen_tile((bbox.west + bbox.east) / 2, (bbox.south + bbox.north) / 2)
    url = HANSEN_URL.format(v=version, tile=tile)
    if urlparse(url).hostname not in HANSEN_HOSTS:
        raise ValueError("label host not allowed")
    with (
        gdal_env(),
        rasterio.open(url) as src,
        WarpedVRT(
            src, crs=f"EPSG:{grid.epsg}", transform=grid.transform, width=grid.width, height=grid.height, resampling=Resampling.nearest
        ) as vrt,
    ):
        return vrt.read(1)


def make_labels(lossyear: np.ndarray, valid: np.ndarray, positive_year: int) -> np.ndarray:
    """positive_year es el código de Hansen de 2 dígitos (p. ej. 23 para 2023)."""
    labels = np.zeros(lossyear.shape, np.uint8)
    labels[lossyear == positive_year] = 1
    labels[lossyear == positive_year + 1] = IGNORE
    labels[~valid] = IGNORE
    return labels


def build_sample(
    aoi: AOISpec, reference: DateWindow, observation: DateWindow, positive_year: int, out_dir: Path, max_cloud: float = 60.0
) -> Path:
    """Escribe ``<out_dir>/<name>.npz`` (ref, obs: float16 (6,H,W); label: uint8)."""
    out = out_dir / f"{aoi.name}.npz"
    if out.exists():
        log.info("skip %s (exists)", aoi.name)
        return out
    bbox = BBox(*aoi.bbox)
    grid = build_grid(bbox, PipelineLimits())
    ref_scenes = search_scenes(bbox, reference, max_cloud).scenes[:4]
    obs_scenes = search_scenes(bbox, observation, max_cloud).scenes[:4]
    if not ref_scenes or not obs_scenes:
        raise RuntimeError(f"no scenes for {aoi.name}")
    shape = (len(REFLECTANCE_BANDS), grid.height, grid.width)
    ref = np.full(shape, np.nan, np.float32)
    obs = np.full(shape, np.nan, np.float32)
    valid = np.zeros((grid.height, grid.width), bool)
    for _, _, window in grid.tiles(1024):
        r = composite_tile(ref_scenes, grid, window)
        o = composite_tile(obs_scenes, grid, window)
        sl = (
            slice(int(window.row_off), int(window.row_off + window.height)),
            slice(int(window.col_off), int(window.col_off + window.width)),
        )
        for i, b in enumerate(REFLECTANCE_BANDS):
            ref[(i, *sl)] = r.bands[b]
            obs[(i, *sl)] = o.bands[b]
        valid[sl] = r.valid & o.valid
    labels = make_labels(read_hansen(grid, bbox), valid, positive_year)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, ref=ref.astype(np.float16), obs=obs.astype(np.float16), label=labels)
    meta = {
        "aoi": asdict(aoi),
        "reference": reference.as_interval(),
        "observation": observation.as_interval(),
        "ref_scenes": [s.scene_id for s in ref_scenes],
        "obs_scenes": [s.scene_id for s in obs_scenes],
        "positive_pixels": int((labels == 1).sum()),
        "ignored_pixels": int((labels == IGNORE).sum()),
        "pixels": int(labels.size),
        "label_source": "Hansen/UMD/Google/USGS/NASA Global Forest Change 2000–2024 v1.12 (CC BY 4.0)",
    }
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("built %s: %d positive px", aoi.name, meta["positive_pixels"])
    return out


def parse_window(text: str) -> DateWindow:
    a, b = text.split("/")
    return DateWindow(date.fromisoformat(a), date.fromisoformat(b))
