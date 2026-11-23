"""Explicaciones en lenguaje sencillo de los hallazgos (en español, primero lo no técnico).

Los valores técnicos (caídas de NDVI/NBR, puntajes) siguen disponibles en la vista
de detalle; este módulo genera lo primero que lee alguien que no es especialista.
"""

from __future__ import annotations

from datetime import datetime

from app.models.enums import ChangeSignal, Severity
from app.schemas.domain import Explanation

_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

HEADLINES = {
    ChangeSignal.VEGETATION_LOSS: "Se detectó una posible pérdida de vegetación",
    ChangeSignal.POSSIBLE_BURN: "Se detectó una posible área quemada",
    ChangeSignal.POSSIBLE_FLOODING: "Se detectó un posible cambio por agua o inundación",
}

SEVERITY_LABELS = {
    Severity.LOW: "Cambio bajo",
    Severity.MODERATE: "Cambio moderado",
    Severity.HIGH: "Cambio importante",
    Severity.PRIORITY: "Hallazgo prioritario",
}

CAVEATS = {
    ChangeSignal.VEGETATION_LOSS: (
        "Una pérdida de vegetación no siempre es deforestación: cosechas, cambios de temporada "
        "o podas pueden producir señales parecidas. Requiere revisión humana."
    ),
    ChangeSignal.POSSIBLE_BURN: (
        "La señal es compatible con una quema, pero no confirma su causa ni si fue intencional. Requiere revisión humana."
    ),
    ChangeSignal.POSSIBLE_FLOODING: (
        "La señal sugiere presencia de agua. Puede tratarse de una inundación estacional y no de una pérdida de bosque."
    ),
}


def human_date(d: datetime) -> str:
    return f"{d.day} de {_MONTHS[d.month - 1]} de {d.year}"


def human_area(ha: float) -> str:
    if ha < 1:
        return f"{ha * 10_000:,.0f} m²".replace(",", ".")
    soccer = ha / 0.714  # cancha de la FIFA ≈ 0.714 ha
    return f"{ha:,.1f} hectáreas (≈ {soccer:,.0f} canchas de fútbol)".replace(",", "X").replace(".", ",").replace("X", ".")


def confidence_text(score: float, detector_kind: str) -> str:
    level = "alta" if score >= 0.75 else "media" if score >= 0.6 else "baja"
    method = "modelo de inteligencia artificial" if detector_kind == "deep-learning" else "análisis espectral por reglas (no IA)"
    return f"Intensidad de la señal: {level}. Detectado por {method}. No es una probabilidad calibrada."


def explain(
    signal: ChangeSignal,
    area_ha: float,
    score: float,
    reference_date: datetime,
    observation_date: datetime,
    detector_kind: str,
) -> Explanation:
    return Explanation(
        headline=HEADLINES[signal],
        summary=(
            "El sistema identificó una diferencia importante entre las imágenes satelitales del "
            f"{human_date(reference_date)} y el {human_date(observation_date)}."
        ),
        area_text=f"Área estimada afectada: {human_area(area_ha)}",
        confidence_text=confidence_text(score, detector_kind),
        caveat=CAVEATS[signal],
    )
