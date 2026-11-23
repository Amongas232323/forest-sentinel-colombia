"""Detector de cambios espectral por reglas (línea base, NO es machine learning).

Lógica (documentada en docs/AI_MODEL_DOCUMENTATION.md §3):

1. Elegibilidad: el píxel era vegetación densa en el compuesto de referencia
   (NDVI_ref >= min_reference_ndvi).
2. Evidencia: tanto el NDVI como el NBR cayeron al menos su umbral mínimo.
3. Puntaje: promedio de las dos caídas, cada una escalada a 0..1 con un valor de saturación.
4. Pista de señal: NBR post-evento muy negativo → posible quema;
   NDWI post-evento positivo → posible inundación; si no, pérdida de vegetación.

El puntaje es una *intensidad ordinal de cambio*, no una probabilidad calibrada.
"""

from __future__ import annotations

from dataclasses import asdict

import cv2
import numpy as np

from ..config import SpectralThresholds
from ..indices import nbr, ndvi, ndwi
from .base import SIGNAL_BURN, SIGNAL_FLOOD, SIGNAL_LOSS, SIGNAL_NONE, DetectorOutput


class SpectralBaselineDetector:
    detector_id = "spectral-baseline"
    version = "1.0.0"
    kind = "rule-based"

    def __init__(self, thresholds: SpectralThresholds | None = None) -> None:
        self.t = thresholds or SpectralThresholds()

    def parameters(self) -> dict[str, object]:
        return asdict(self.t)

    def predict(
        self,
        reference: dict[str, np.ndarray],
        observation: dict[str, np.ndarray],
        valid: np.ndarray,
    ) -> DetectorOutput:
        t = self.t
        ndvi_ref = ndvi(reference["nir"], reference["red"])
        ndvi_obs = ndvi(observation["nir"], observation["red"])
        nbr_ref = nbr(reference["nir"], reference["swir22"])
        nbr_obs = nbr(observation["nir"], observation["swir22"])
        ndwi_obs = ndwi(observation["green"], observation["nir"])

        d_ndvi = ndvi_ref - ndvi_obs
        d_nbr = nbr_ref - nbr_obs

        eligible = valid & (ndvi_ref >= t.min_reference_ndvi)
        evidence = eligible & (d_ndvi >= t.min_ndvi_drop) & (d_nbr >= t.min_nbr_drop)

        s_ndvi = np.clip(d_ndvi / t.ndvi_drop_saturation, 0, 1)
        s_nbr = np.clip(d_nbr / t.nbr_drop_saturation, 0, 1)
        score = np.where(evidence, 0.5 * s_ndvi + 0.5 * s_nbr, 0.0).astype(np.float32)
        score = np.nan_to_num(score, nan=0.0)
        # Una mediana de 3×3 quita los píxeles sueltos (ruido del sensor, nubes residuales).
        score = cv2.medianBlur(score, 3)
        score[~valid] = np.nan

        signal = np.full(score.shape, SIGNAL_NONE, dtype=np.uint8)
        changed = np.nan_to_num(score) > 0
        signal[changed] = SIGNAL_LOSS
        signal[changed & (nbr_obs <= t.burn_nbr_post_max)] = SIGNAL_BURN
        signal[changed & (ndwi_obs >= t.water_ndwi_post_min)] = SIGNAL_FLOOD

        return DetectorOutput(score=score, signal=signal, ndvi_drop=d_ndvi, nbr_drop=d_nbr)
