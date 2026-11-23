"""Pasa las métricas de evaluación a docs/AI_MODEL_DOCUMENTATION.md (entre los marcadores).

python -m sentinel_ml.training.report ml/checkpoints/siamese-unet-0.1.0.metrics.json docs/AI_MODEL_DOCUMENTATION.md
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
ROWS = [
    ("precision", "Precisión"),
    ("recall", "Recall"),
    ("f1", "F1 / Dice"),
    ("iou", "IoU"),
    ("false_positive_rate", "Tasa de falsos positivos"),
    ("false_negative_rate", "Tasa de falsos negativos"),
]


def render(metrics: dict) -> str:  # type: ignore[type-arg]
    m, b = metrics["test_model"], metrics["test_baseline"]
    test = [k for k, v in metrics["splits"].items() if v == "test"]
    lines = [
        f"Generado el {date.today().isoformat()} a partir de `{Path(sys.argv[1]).name}`. AOI de prueba (nunca vistas): {', '.join(test)}.",
        "",
        "| Métrica (prueba) | Siamese U-Net | Baseline espectral |",
        "|---|---:|---:|",
    ]
    for key, label in ROWS:
        lines.append(f"| {label} | {m[key]:.3f} | {b[key]:.3f} |")
    lines += [
        f"| Píxeles positivos de prueba (TP+FN) | {m['tp'] + m['fn']:,} | {b['tp'] + b['fn']:,} |",
        "",
        f"F1 de validación del mejor epoch: **{metrics['val_f1']:.3f}** · umbral elegido en validación: **{metrics['threshold']:.2f}** · "
        f"`pos_weight` = {metrics['pos_weight']:.1f} · píxeles positivos de entrenamiento: {metrics['train_positive_px']:,}.",
        "",
        "Evolución del entrenamiento:",
        "",
        "| Epoch | Pérdida | F1 validación | Umbral |",
        "|---:|---:|---:|---:|",
        *[f"| {h['epoch']} | {h['loss']:.4f} | {h['val_f1']:.3f} | {h['val_threshold']:.2f} |" for h in metrics["history"]],
    ]
    better = m["f1"] > b["f1"]
    lines += [
        "",
        "**Lectura honesta:** "
        + (
            f"el modelo supera al baseline en F1 ({m['f1']:.3f} frente a {b['f1']:.3f}) sobre territorio no visto. "
            if better
            else f"el modelo **no** supera al baseline en F1 ({m['f1']:.3f} frente a {b['f1']:.3f}); "
            "por eso producción sigue usando el detector espectral. "
        )
        + "Las cifras miden concordancia con Hansen GFC (etiquetas débiles a 30 m, §5), no exactitud de campo. "
        "Activar el modelo en producción requiere además validación con analistas sobre alertas reales.",
    ]
    return "\n".join(lines)


def main() -> int:
    metrics = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    doc = Path(sys.argv[2])
    text = doc.read_text(encoding="utf-8")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    doc.write_text(f"{head}{START}\n{render(metrics)}\n{END}{tail}", encoding="utf-8")
    print("updated", doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
