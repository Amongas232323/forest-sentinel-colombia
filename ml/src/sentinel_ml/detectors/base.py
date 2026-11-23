"""Contrato de detector compartido por las implementaciones por reglas y de deep learning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

# Códigos de señal que se guardan en DetectorOutput.signal (ráster uint8).
SIGNAL_NONE = 0
SIGNAL_LOSS = 1
SIGNAL_BURN = 2
SIGNAL_FLOOD = 3


@dataclass
class DetectorOutput:
    score: np.ndarray  # float32 0..1, NaN donde es inválido
    signal: np.ndarray  # códigos uint8, ver SIGNAL_*
    ndvi_drop: np.ndarray  # float32, lo guardamos como evidencia explicable
    nbr_drop: np.ndarray  # float32


@runtime_checkable
class ChangeDetector(Protocol):
    detector_id: str
    version: str
    kind: str  # "rule-based" | "deep-learning"

    def predict(
        self,
        reference: dict[str, np.ndarray],
        observation: dict[str, np.ndarray],
        valid: np.ndarray,
    ) -> DetectorOutput: ...

    def parameters(self) -> dict[str, object]: ...
