from __future__ import annotations

from .config import SeverityThresholds
from .contracts import Severity


def classify(area_ha: float, score: float, t: SeverityThresholds) -> Severity:
    if area_ha >= t.priority_area_ha and score >= t.priority_score:
        return Severity.PRIORITY
    if area_ha >= t.high_area_ha and score >= t.high_score:
        return Severity.HIGH
    if area_ha >= t.moderate_area_ha and score >= t.moderate_score:
        return Severity.MODERATE
    return Severity.LOW
