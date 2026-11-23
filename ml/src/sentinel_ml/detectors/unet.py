"""Detector de deep learning que envuelve un checkpoint entrenado de la Siamese U-Net.

La inferencia corre sobre parches solapados que se mezclan con una ventana de Hann, así
los bordes de los tiles no dejan costuras, y la memoria queda limitada por el tamaño de ``patch``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from ..indices import nbr, ndvi, ndwi
from ..model.checkpoint import Checkpoint, load_checkpoint
from .base import SIGNAL_BURN, SIGNAL_FLOOD, SIGNAL_LOSS, SIGNAL_NONE, DetectorOutput


def _hann2d(size: int) -> np.ndarray:
    w = np.hanning(size + 2)[1:-1].astype(np.float32)
    return np.outer(w, w)


class SiameseUNetDetector:
    detector_id = "siamese-unet"
    kind = "deep-learning"

    def __init__(self, checkpoint_path: Path, device: str | None = None, patch: int = 256, overlap: int = 64) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.ckpt: Checkpoint = load_checkpoint(checkpoint_path, self.device)
        div = self.ckpt.model.divisor
        if patch % div:
            raise ValueError(f"patch must be divisible by {div}")
        self.patch = patch
        self.stride = patch - overlap
        self.weight = _hann2d(patch)
        self.version = self.ckpt.version

    def parameters(self) -> dict[str, object]:
        return {
            "threshold": self.ckpt.threshold,
            "patch": self.patch,
            "bands": list(self.ckpt.bands),
            "validation_metrics": self.ckpt.metrics,
            "dataset": self.ckpt.dataset,
        }

    @torch.inference_mode()
    def _probabilities(self, ref: np.ndarray, obs: np.ndarray) -> np.ndarray:
        _, h, w = ref.shape
        p = self.patch
        ph, pw = max(h, p), max(w, p)
        pad = ((0, 0), (0, ph - h), (0, pw - w))
        ref, obs = np.pad(ref, pad, mode="reflect"), np.pad(obs, pad, mode="reflect")
        acc = np.zeros((ph, pw), np.float32)
        norm = np.zeros((ph, pw), np.float32)
        rows = list(range(0, ph - p + 1, self.stride)) or [0]
        cols = list(range(0, pw - p + 1, self.stride)) or [0]
        if rows[-1] != ph - p:
            rows.append(ph - p)
        if cols[-1] != pw - p:
            cols.append(pw - p)
        for r in rows:
            for c in cols:
                a = torch.from_numpy(ref[None, :, r : r + p, c : c + p]).to(self.device)
                b = torch.from_numpy(obs[None, :, r : r + p, c : c + p]).to(self.device)
                prob = torch.sigmoid(self.ckpt.model(a, b))[0, 0].cpu().numpy()
                acc[r : r + p, c : c + p] += prob * self.weight
                norm[r : r + p, c : c + p] += self.weight
        return (acc / np.maximum(norm, 1e-6))[:h, :w]

    def predict(
        self,
        reference: dict[str, np.ndarray],
        observation: dict[str, np.ndarray],
        valid: np.ndarray,
    ) -> DetectorOutput:
        prob = self._probabilities(self.ckpt.normalise(reference), self.ckpt.normalise(observation))
        # Re-mapeamos para que el corte genérico de 0.5 del pipeline equivalga al umbral ajustado del checkpoint.
        t = self.ckpt.threshold
        score = np.where(prob < t, 0.5 * prob / t, 0.5 + 0.5 * (prob - t) / (1 - t)).astype(np.float32)
        score[~valid] = np.nan

        d_ndvi = ndvi(reference["nir"], reference["red"]) - ndvi(observation["nir"], observation["red"])
        nbr_obs = nbr(observation["nir"], observation["swir22"])
        d_nbr = nbr(reference["nir"], reference["swir22"]) - nbr_obs
        ndwi_obs = ndwi(observation["green"], observation["nir"])
        signal = np.full(score.shape, SIGNAL_NONE, np.uint8)
        changed = np.nan_to_num(score) >= 0.5
        signal[changed] = SIGNAL_LOSS
        signal[changed & (nbr_obs <= -0.05)] = SIGNAL_BURN
        signal[changed & (ndwi_obs >= 0.10)] = SIGNAL_FLOOD
        return DetectorOutput(score=score, signal=signal, ndvi_drop=d_ndvi, nbr_drop=d_nbr)
