"""Registro de detectores.

``get_detector`` escoge el modelo de deep learning solo cuando existe un archivo de
checkpoint; si no, se devuelve a la línea base por reglas y el resultado queda
etiquetado como ``kind="rule-based"`` hasta llegar a la UI.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import SpectralThresholds
from .base import ChangeDetector, DetectorOutput
from .spectral import SpectralBaselineDetector

log = logging.getLogger(__name__)

__all__ = ["ChangeDetector", "DetectorOutput", "SpectralBaselineDetector", "get_detector"]


def get_detector(
    preferred: str = "auto",
    checkpoint: Path | None = None,
    spectral: SpectralThresholds | None = None,
) -> ChangeDetector:
    if preferred in ("auto", "siamese-unet") and checkpoint is not None and checkpoint.is_file():
        from .unet import SiameseUNetDetector  # torch se importa de forma perezosa

        return SiameseUNetDetector(checkpoint)
    if preferred == "siamese-unet":
        raise FileNotFoundError(f"model checkpoint not found: {checkpoint}")
    if preferred == "auto":
        log.info("no trained checkpoint available, using spectral baseline")
    return SpectralBaselineDetector(spectral)
