"""Smoke test de entrenamiento de punta a punta sobre un dataset sintético chiquito (sin red)."""

from __future__ import annotations

import json

import numpy as np
import pytest

pytest.importorskip("torch")

from sentinel_ml.detectors import get_detector  # noqa: E402
from sentinel_ml.training.dataset import IGNORE, hansen_tile, make_labels  # noqa: E402
from sentinel_ml.training.train import train  # noqa: E402

FOREST = np.array([0.02, 0.05, 0.03, 0.35, 0.15, 0.07], np.float32)
BARE = np.array([0.08, 0.11, 0.14, 0.22, 0.30, 0.22], np.float32)


def synthetic(path, seed: int, size: int = 96) -> None:
    rng = np.random.default_rng(seed)
    ref = np.broadcast_to(FOREST[:, None, None], (6, size, size)).copy() + rng.normal(0, 0.005, (6, size, size))
    obs = ref.copy()
    label = np.zeros((size, size), np.uint8)
    for _ in range(3):
        r, c = rng.integers(0, size - 20, 2)
        obs[:, r : r + 16, c : c + 16] = BARE[:, None, None]
        label[r : r + 16, c : c + 16] = 1
    label[:4] = IGNORE
    np.savez_compressed(path, ref=ref.astype(np.float16), obs=obs.astype(np.float16), label=label)


def test_hansen_tile_names():
    assert hansen_tile(-72.7, 2.3) == "10N_080W"
    assert hansen_tile(-70.2, -3.9) == "00N_080W"


def test_label_policy_marks_ambiguous_year_and_clouds_as_ignore():
    lossyear = np.array([[0, 23, 24], [22, 23, 0]])
    valid = np.array([[1, 1, 1], [1, 0, 1]], bool)
    assert make_labels(lossyear, valid, 23).tolist() == [[0, 1, 255], [0, 255, 0]]


def test_training_pipeline_produces_a_usable_checkpoint(tmp_path):
    for name, seed in (("a", 1), ("b", 2), ("v", 3), ("t", 4)):
        synthetic(tmp_path / f"{name}.npz", seed)
    out = tmp_path / "model.pt"
    metrics = train(tmp_path, {"a": "train", "b": "train", "v": "val", "t": "test"}, out, epochs=2, steps_per_epoch=3, batch=2, patch=64)
    assert out.exists() and out.with_suffix(".metrics.json").exists()
    for key in ("precision", "recall", "f1", "iou"):
        assert 0 <= metrics["test_model"][key] <= 1
        assert 0 <= metrics["test_baseline"][key] <= 1
    # La línea base por reglas debería resolver este problema de juguete, que es trivialmente separable.
    assert metrics["test_baseline"]["f1"] > 0.8
    saved = json.loads(out.with_suffix(".metrics.json").read_text())
    assert len(saved["history"]) == 2
    det = get_detector("auto", out)
    assert det.kind == "deep-learning"
