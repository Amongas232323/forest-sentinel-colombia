"""Reportes CSV y PDF armados con datos reales de alertas."""

from __future__ import annotations

import csv
import io
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.models import Alert, DetectionResult, Report, User
from app.models.enums import ReportFormat, Role
from app.schemas.domain import AlertFilters, AlertOut

from . import audit, evidence
from .alerts import list_alerts
from .explain import SEVERITY_LABELS, human_date
from .serializers import alert_out

MAX_REPORT_ALERTS = 2000
STATUS_LABELS = {
    "new": "Nueva",
    "pending_review": "Pendiente de revisión",
    "in_review": "En revisión",
    "confirmed": "Hallazgo confirmado",
    "dismissed": "Descartada",
    "closed": "Cerrada",
}
SIGNAL_LABELS = {"vegetation_loss": "Pérdida de vegetación", "possible_burn": "Posible quema", "possible_flooding": "Posible inundación"}

FOREST = colors.HexColor("#10251D")
JUNGLE = colors.HexColor("#183D2C")
LEAF = colors.HexColor("#397B50")
MINERAL = colors.HexColor("#A5B0A7")


def _safe_cell(value: object) -> str:
    """Neutraliza la inyección de fórmulas en hojas de cálculo (OWASP CSV Injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def build_csv(alerts: list[AlertOut]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "codigo",
            "estado",
            "prioridad",
            "tipo_de_cambio",
            "territorio",
            "zona",
            "area_ha",
            "intensidad_senal",
            "latitud",
            "longitud",
            "fecha_imagen_referencia",
            "fecha_imagen_observacion",
            "primera_deteccion",
            "ultima_deteccion",
            "detecciones",
            "calidad_imagen",
            "detector",
            "tipo_detector",
        ]
    )
    for a in alerts:
        w.writerow(
            [
                _safe_cell(v)
                for v in (
                    a.code,
                    STATUS_LABELS[a.status],
                    SEVERITY_LABELS[a.severity],
                    SIGNAL_LABELS[a.signal],
                    a.territory_name,
                    a.region_name,
                    f"{a.area_ha:.2f}",
                    f"{a.confidence:.3f}",
                    f"{a.centroid[1]:.6f}",
                    f"{a.centroid[0]:.6f}",
                    a.reference_date.date().isoformat(),
                    a.observation_date.date().isoformat(),
                    a.first_detected_at.isoformat(),
                    a.last_detected_at.isoformat(),
                    a.detection_count,
                    f"{a.image_quality:.2f}",
                    a.detector,
                    a.detector_kind,
                )
            ]
        )
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM → así Excel abre bien el UTF-8


def _evidence_image(db: Session, alert: Alert, width_mm: float) -> RLImage | None:
    result = db.get(DetectionResult, alert.latest_result_id)
    if not result or not result.artifacts:
        return None
    try:
        obs = Image.open(evidence.artifact_path(result.job_id, "observation")).convert("RGBA")
        overlay = Image.open(evidence.artifact_path(result.job_id, "overlay")).convert("RGBA").resize(obs.size)
    except (OSError, ValueError):
        return None
    obs.alpha_composite(overlay)
    obs.thumbnail((900, 900))
    buf = io.BytesIO()
    obs.convert("RGB").save(buf, format="JPEG", quality=82)
    buf.seek(0)
    ratio = obs.height / obs.width
    return RLImage(buf, width=width_mm * mm, height=width_mm * ratio * mm)


def build_pdf(db: Session, title: str, alerts: list[Alert], filters: AlertFilters, author: str) -> bytes:
    s = get_settings()
    outs = [alert_out(a) for a in alerts]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="Forest Sentinel",
    )
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=FOREST, fontSize=22, leading=26, alignment=0)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=JUNGLE)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11, textColor=colors.HexColor("#4a564e"))
    mono = ParagraphStyle("mono", parent=small, fontName="Courier")

    total_area = sum(a.area_ha for a in outs)
    by_sev = Counter(a.severity for a in outs)
    by_terr = Counter(a.territory_name for a in outs)
    by_status = Counter(a.status for a in outs)
    story: list = [
        Paragraph("FOREST SENTINEL · INFORME DE HALLAZGOS", mono),
        Spacer(1, 4 * mm),
        Paragraph(title, h1),
        Paragraph(f"Generado el {human_date(datetime.now(UTC))} por {author}.", small),
        Spacer(1, 6 * mm),
        Paragraph("Resumen ejecutivo", h2),
        Paragraph(
            f"Este informe incluye <b>{len(outs)}</b> hallazgo(s) que suman un área estimada de <b>{total_area:,.1f} ha</b>. "
            f"Confirmados tras revisión humana: <b>{by_status.get('confirmed', 0)}</b>; pendientes o en revisión: "
            f"<b>{by_status.get('new', 0) + by_status.get('pending_review', 0) + by_status.get('in_review', 0)}</b>; "
            f"descartados: <b>{by_status.get('dismissed', 0)}</b>.",
            body,
        ),
        Spacer(1, 3 * mm),
    ]
    summary = [["Prioridad", "Hallazgos"]] + [[SEVERITY_LABELS[k], str(by_sev.get(k, 0))] for k in SEVERITY_LABELS]
    terr = [["Territorio", "Hallazgos"]] + [[k, str(v)] for k, v in by_terr.most_common()]
    story.append(
        Table([[_table(summary, [45 * mm, 25 * mm]), _table(terr or [["—", "0"]], [55 * mm, 25 * mm])]], colWidths=[80 * mm, 90 * mm])
    )
    story += [Spacer(1, 6 * mm), Paragraph("Hallazgos", h2)]
    rows = [["Código", "Zona", "Tipo", "Área (ha)", "Prioridad", "Estado"]]
    for a in outs[:200]:
        rows.append(
            [
                a.code,
                Paragraph(a.region_name, small),
                SIGNAL_LABELS[a.signal],
                f"{a.area_ha:.1f}",
                SEVERITY_LABELS[a.severity],
                STATUS_LABELS[a.status],
            ]
        )
    story.append(_table(rows, [26 * mm, 38 * mm, 32 * mm, 18 * mm, 30 * mm, 30 * mm]))
    if len(outs) > 200:
        story.append(Paragraph(f"Se muestran 200 de {len(outs)} hallazgos; el listado completo está disponible en CSV.", small))

    story += [Spacer(1, 6 * mm), Paragraph("Evidencia visual de los hallazgos principales", h2)]
    for a_model, a in list(zip(alerts, outs, strict=True))[:4]:
        img = _evidence_image(db, a_model, 120)
        story.append(Paragraph(f"<b>{a.code}</b> — {a.explanation.headline}. {a.explanation.summary} {a.explanation.area_text}.", body))
        story.append(Paragraph(f"Coordenadas: {a.centroid[1]:.5f}, {a.centroid[0]:.5f} · Detector: {a.detector} ({a.detector_kind})", mono))
        if img:
            story += [
                Spacer(1, 2 * mm),
                img,
                Paragraph(
                    "Imagen Sentinel-2 del periodo de observación con las áreas de cambio superpuestas (ámbar: moderado, rojo: fuerte).",
                    small,
                ),
            ]
        story.append(Spacer(1, 5 * mm))

    story += [
        Paragraph("Metodología y limitaciones", h2),
        Paragraph(
            "Los hallazgos se obtienen comparando composiciones de imágenes Sentinel-2 L2A (Copernicus/ESA, distribuidas por Earth Search) "
            "de dos periodos, con enmascaramiento de nubes. La intensidad de la señal es una medida ordinal "
            "y no una probabilidad calibrada. Una pérdida de vegetación detectada no equivale a deforestación "
            "confirmada: cosechas, cambios estacionales, quemas o inundaciones "
            "pueden producir señales similares. Todo hallazgo requiere verificación por personal competente antes de tomar decisiones.",
            body,
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            "Contiene información modificada de Copernicus Sentinel. Límites territoriales "
            f"© OpenStreetMap contributors (ODbL). Responsable: {s.privacy_controller_name}.",
            small,
        ),
    ]
    doc.build(story)
    return buf.getvalue()


def _table(rows: list[list], widths: list[float]) -> Table:  # type: ignore[type-arg]
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), FOREST),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F3EA")]),
                ("GRID", (0, 0), (-1, -1), 0.25, MINERAL),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def create_report(db: Session, user: User, fmt: ReportFormat, title: str, filters: AlertFilters, ip: str | None) -> tuple[Report, bytes]:
    alerts, total = list_alerts(db, filters, 1, MAX_REPORT_ALERTS, order="severity")
    if fmt == ReportFormat.CSV:
        content = build_csv([alert_out(a) for a in alerts])
    else:
        content = build_pdf(db, title, alerts, filters, user.full_name)
    report_id = uuid.uuid4()
    file_name = f"forest-sentinel-{datetime.now(UTC):%Y%m%d-%H%M}-{str(report_id)[:8]}.{fmt.value}"
    path = get_settings().reports_dir / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    report = Report(
        id=report_id,
        created_by_id=user.id,
        format=fmt,
        title=title,
        filters=filters.model_dump(mode="json", exclude_none=True),
        file_name=file_name,
        size_bytes=len(content),
        alert_count=len(alerts),
    )
    db.add(report)
    audit.record(
        db,
        "report.created",
        actor_id=user.id,
        resource_type="report",
        resource_id=report.id,
        ip=ip,
        details={"format": fmt.value, "alerts": len(alerts), "total_matching": total},
    )
    db.commit()
    return report, content


def get_report_for(db: Session, report_id: uuid.UUID, user: User) -> tuple[Report, Path]:
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("El informe no existe.")
    # Protección IDOR: solo el autor o un administrador pueden acceder a un reporte.
    if report.created_by_id != user.id and user.role != Role.ADMIN:
        raise NotFoundError("El informe no existe.")
    path = report_path(report)
    if path is None:
        raise NotFoundError("El archivo del informe ya no está disponible.")
    return report, path


def report_path(report: Report) -> Path | None:
    """Ruta del archivo del informe, solo si existe y está dentro de DATA_DIR/reports."""
    base = get_settings().reports_dir.resolve()
    path = (base / report.file_name).resolve()
    return path if base in path.parents and path.is_file() else None


def list_reports(db: Session, user: User) -> list[Report]:
    stmt = select(Report).order_by(Report.created_at.desc()).limit(100)
    if user.role != Role.ADMIN:
        stmt = stmt.where(Report.created_by_id == user.id)
    return list(db.scalars(stmt))
