"""Lecturas por ventanas y reproyectadas de Cloud-Optimised GeoTIFFs remotos.

Solo se descargan los bloques que se solapan con la ventana pedida (peticiones HTTP
por rangos), así que un tile de Sentinel-2 de 110×110 km nunca se carga completo.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window

from .grid import AnalysisGrid
from .stac import validate_asset_href

log = logging.getLogger(__name__)

GDAL_ENV: dict[str, str | int] = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "AWS_NO_SIGN_REQUEST": "YES",
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_RETRY_DELAY": "1",
    "GDAL_HTTP_TIMEOUT": "60",
    "VSI_CACHE": "TRUE",
    "GDAL_CACHEMAX": 256,
}


@contextmanager
def gdal_env() -> Iterator[None]:
    with rasterio.Env(**GDAL_ENV):
        yield


def read_window(
    href: str,
    grid: AnalysisGrid,
    window: Window,
    resampling: Resampling,
    dtype: str = "float32",
) -> np.ndarray:
    """Lee la ``window`` de ``grid`` desde ``href``, reproyectando sobre la marcha.

    Los píxeles por fuera de la huella de la fuente se devuelven como 0 (nodata).
    """
    validate_asset_href(href)
    # rasterio.Env es thread-local, así que se abre en cada llamada (las lecturas corren en un pool).
    with gdal_env(), rasterio.open(href) as src:
        if src.count != 1:
            raise ValueError("expected single-band asset")
        with WarpedVRT(
            src,
            crs=f"EPSG:{grid.epsg}",
            transform=grid.transform,
            width=grid.width,
            height=grid.height,
            resampling=resampling,
            nodata=0,
        ) as vrt:
            return vrt.read(1, window=window, out_dtype=dtype, boundless=False)
