"""Métricas de segmentación binaria acumuladas sobre todo un set de evaluación.

Las métricas salen de una matriz de confusión global (micro-promedio), que es la
convención del benchmark OSCD y evita inflar los puntajes en chips vacíos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ConfusionMatrix:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def update(self, pred: np.ndarray, target: np.ndarray, valid: np.ndarray | None = None) -> None:
        pred = pred.astype(bool)
        target = target.astype(bool)
        if valid is not None:
            pred, target = pred[valid], target[valid]
        self.tp += int(np.sum(pred & target))
        self.fp += int(np.sum(pred & ~target))
        self.fn += int(np.sum(~pred & target))
        self.tn += int(np.sum(~pred & ~target))

    @staticmethod
    def _div(a: float, b: float) -> float:
        return float(a / b) if b else 0.0

    def report(self) -> dict[str, float | int]:
        precision = self._div(self.tp, self.tp + self.fp)
        recall = self._div(self.tp, self.tp + self.fn)
        f1 = self._div(2 * precision * recall, precision + recall)
        iou = self._div(self.tp, self.tp + self.fp + self.fn)
        total = self.tp + self.fp + self.fn + self.tn
        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "dice": f1,  # idéntico al F1 para máscaras binarias
            "iou": iou,
            "accuracy": self._div(self.tp + self.tn, total),
            "false_positive_rate": self._div(self.fp, self.fp + self.tn),
            "false_negative_rate": self._div(self.fn, self.fn + self.tp),
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
        }
