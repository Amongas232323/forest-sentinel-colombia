"""CLI de entrenamiento.

    python -m sentinel_ml.training build --config ml/training/aois.json --out ml/datasets/gfc
    python -m sentinel_ml.training train --config ml/training/aois.json --data ml/datasets/gfc \
        --out ml/checkpoints/siamese-unet-0.1.0.pt
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from .dataset import AOISpec, build_sample, parse_window


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sentinel_ml.training")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--config", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--only", default=None, help="build a single AOI (used internally per subprocess)")
    b.add_argument("--timeout", type=int, default=1200, help="seconds per AOI before it is retried")
    t = sub.add_parser("train")
    t.add_argument("--config", type=Path, required=True)
    t.add_argument("--data", type=Path, required=True)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--epochs", type=int, default=12)
    t.add_argument("--steps", type=int, default=60)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    aois = [AOISpec(a["name"], tuple(a["bbox"]), a["split"]) for a in cfg["aois"]]
    if args.cmd == "build":
        ref, obs = parse_window(cfg["reference"]), parse_window(cfg["observation"])
        if args.only:
            aoi = next(a for a in aois if a.name == args.only)
            build_sample(aoi, ref, obs, cfg["positive_year"], args.out)
            return 0
        # Cada AOI corre en su propio proceso con timeout: si una lectura GDAL/HTTP se pega
        # en una AOI no puede colgar todo el build, y se reintenta una vez.
        for aoi in aois:
            if (args.out / f"{aoi.name}.npz").exists():
                continue
            for attempt in (1, 2):
                cmd = [
                    sys.executable,
                    "-m",
                    "sentinel_ml.training",
                    "build",
                    "--config",
                    str(args.config),
                    "--out",
                    str(args.out),
                    "--only",
                    aoi.name,
                ]
                try:
                    subprocess.run(cmd, check=True, timeout=args.timeout)  # noqa: S603 — argv fijo, sin shell
                    break
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
                    logging.warning("AOI %s attempt %d failed: %s", aoi.name, attempt, exc)
        return 0
    from .train import train  # torch solo se importa para entrenar

    metrics = train(args.data, {a.name: a.split for a in aois}, args.out, epochs=args.epochs, steps_per_epoch=args.steps)
    print(json.dumps({k: metrics[k] for k in ("test_model", "test_baseline", "val_f1", "threshold")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
