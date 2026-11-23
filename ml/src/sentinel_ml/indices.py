"""Índices espectrales. Todas las entradas son arreglos float de reflectancia de superficie (0..1).

El NaN se propaga donde cualquier entrada sea NaN (píxeles inválidos / nublados).
"""

from __future__ import annotations

import numpy as np


def _normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = a + b
        out = (a - b) / denom
    out[~np.isfinite(out)] = np.nan
    return out.astype(np.float32)


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index — qué tan verde está el dosel."""
    return _normalized_difference(nir, red)


def nbr(nir: np.ndarray, swir22: np.ndarray) -> np.ndarray:
    """Normalized Burn Ratio — sensible a la estructura del dosel y a las cicatrices de quema."""
    return _normalized_difference(nir, swir22)


def ndmi(nir: np.ndarray, swir16: np.ndarray) -> np.ndarray:
    """Normalized Difference Moisture Index — contenido de agua en la vegetación."""
    return _normalized_difference(nir, swir16)


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI de McFeeters — agua abierta."""
    return _normalized_difference(green, nir)
