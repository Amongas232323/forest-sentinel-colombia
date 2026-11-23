"""Punto de entrada por línea de comandos.

Ejemplo::

    python -m sentinel_ml.cli run --bbox -74.25 2.15 -74.15 2.25 \
        --reference 2018-12-01/2019-02-28 --observation 2019-12-01/2020-03-15 \
        --out runs/tinigua
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from .contracts import BBox, DateWindow
from .detectors import get_detector
from .pipeline import run_pipeline


def _window(text: str) -> DateWindow:
    start, end = text.split("/")
    return DateWindow(date.fromisoformat(start), date.fromisoformat(end))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel-ml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run change detection over an AOI")
    run.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"), required=True)
    run.add_argument("--reference", type=_window, required=True)
    run.add_argument("--observation", type=_window, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--detector", default="auto", choices=["auto", "spectral-baseline", "siamese-unet"])
    run.add_argument("--checkpoint", type=Path, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    detector = get_detector(args.detector, args.checkpoint)
    result = run_pipeline(
        BBox(*args.bbox),
        args.reference,
        args.observation,
        args.out,
        detector,
        progress=lambda stage, f: print(f"[{f:5.0%}] {stage}", file=sys.stderr),
    )
    summary = {
        "detector": f"{result.detector_id}@{result.detector_version} ({result.detector_kind})",
        "quality_ok": result.quality_ok,
        "notes": result.quality_notes,
        "reference_valid": result.reference.valid_fraction,
        "observation_valid": result.observation.valid_fraction,
        "analysed_ha": result.analysed_area_ha,
        "changed_ha": result.changed_area_ha,
        "findings": len(result.findings),
        "top": [
            {"area_ha": f.area_ha, "severity": f.severity.value, "signal": f.signal.value, "score": round(f.mean_score, 3)}
            for f in result.findings[:5]
        ],
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
