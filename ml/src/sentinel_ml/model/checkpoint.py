"""Formato del checkpoint y normalización de bandas.

Un checkpoint es un dict de ``torch.save`` con:

* ``format``: "forest-sentinel/siamese-unet@1"
* ``state_dict``: pesos del modelo
* ``arch``: kwargs para :class:`SiameseUNet`
* ``bands``: nombres de las bandas que se esperan como entrada, en orden
* ``norm``: {"mean": [...], "std": [...]} por banda (en unidades de reflectancia)
* ``threshold``: umbral de decisión elegido sobre el set de validación
* ``metrics``: métricas de validación/test (ver metrics.py)
* ``dataset``: texto libre con la procedencia de los datos de entrenamiento
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .siamese_unet import SiameseUNet

FORMAT = "forest-sentinel/siamese-unet@1"
DEFAULT_BANDS = ("blue", "green", "red", "nir", "swir16", "swir22")


@dataclass
class Checkpoint:
    model: SiameseUNet
    bands: tuple[str, ...]
    mean: np.ndarray
    std: np.ndarray
    threshold: float
    metrics: dict[str, Any] = field(default_factory=dict)
    dataset: str = ""
    version: str = "0.0.0"

    def normalise(self, bands: dict[str, np.ndarray]) -> np.ndarray:
        arr = np.stack([bands[b] for b in self.bands]).astype(np.float32)
        arr = (arr - self.mean[:, None, None]) / self.std[:, None, None]
        return np.nan_to_num(arr, nan=0.0)


def save_checkpoint(path: Path, ckpt: Checkpoint) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "format": FORMAT,
            "version": ckpt.version,
            "state_dict": ckpt.model.state_dict(),
            "arch": {"in_channels": ckpt.model.in_channels, "widths": list(ckpt.model.widths)},
            "bands": list(ckpt.bands),
            "norm": {"mean": ckpt.mean.tolist(), "std": ckpt.std.tolist()},
            "threshold": ckpt.threshold,
            "metrics": ckpt.metrics,
            "dataset": ckpt.dataset,
        },
        path,
    )


def load_checkpoint(path: Path, device: str = "cpu") -> Checkpoint:
    # weights_only=True: rechaza objetos arbitrarios en pickle (los archivos no son de confianza).
    raw = torch.load(path, map_location=device, weights_only=True)
    if raw.get("format") != FORMAT:
        raise ValueError(f"unsupported checkpoint format: {raw.get('format')!r}")
    arch = raw["arch"]
    model = SiameseUNet(in_channels=int(arch["in_channels"]), widths=tuple(arch["widths"]))
    model.load_state_dict(raw["state_dict"])
    model.eval().to(device)
    return Checkpoint(
        model=model,
        bands=tuple(raw["bands"]),
        mean=np.asarray(raw["norm"]["mean"], dtype=np.float32),
        std=np.asarray(raw["norm"]["std"], dtype=np.float32),
        threshold=float(raw["threshold"]),
        metrics=dict(raw.get("metrics", {})),
        dataset=str(raw.get("dataset", "")),
        version=str(raw.get("version", "0.0.0")),
    )
