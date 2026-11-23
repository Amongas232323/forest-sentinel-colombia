"""Entrena y evalúa la Siamese U-Net con una división geográfica train/val/test.

Las AOIs de test nunca se ven durante el entrenamiento ni al escoger el umbral, y la
línea base por reglas se evalúa sobre exactamente los mismos píxeles de test, así que
la comparación que reportamos es justa (manzanas con manzanas).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from ..composite import REFLECTANCE_BANDS
from ..detectors.spectral import SpectralBaselineDetector
from ..model.checkpoint import Checkpoint, save_checkpoint
from ..model.metrics import ConfusionMatrix
from ..model.siamese_unet import SiameseUNet
from .dataset import IGNORE

log = logging.getLogger(__name__)


@dataclass
class Sample:
    name: str
    split: str
    ref: np.ndarray  # (6,H,W) float32, NaN = inválido
    obs: np.ndarray
    label: np.ndarray  # (H,W) uint8 {0,1,255}


def load_samples(data_dir: Path, splits: dict[str, str]) -> list[Sample]:
    out = []
    for name, split in splits.items():
        path = data_dir / f"{name}.npz"
        if not path.exists():
            log.warning("missing sample %s", name)
            continue
        z = np.load(path)
        out.append(Sample(name, split, z["ref"].astype(np.float32), z["obs"].astype(np.float32), z["label"]))
    return out


def band_stats(samples: list[Sample]) -> tuple[np.ndarray, np.ndarray]:
    stack = np.concatenate([np.concatenate([s.ref, s.obs], axis=2).reshape(len(REFLECTANCE_BANDS), -1) for s in samples], axis=1)
    mean = np.nanmean(stack, axis=1)
    std = np.nanstd(stack, axis=1) + 1e-6
    return mean.astype(np.float32), std.astype(np.float32)


def _norm(a: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return np.nan_to_num((a - mean[:, None, None]) / std[:, None, None], nan=0.0).astype(np.float32)


def random_patches(
    samples: list[Sample], n: int, size: int, rng: np.random.Generator, pos_fraction: float = 0.5
) -> list[tuple[int, int, int]]:
    """(sample_idx, row, col) con ~pos_fraction de parches que contienen positivos."""
    picks: list[tuple[int, int, int]] = []
    pos_index = [np.argwhere(s.label == 1) for s in samples]
    while len(picks) < n:
        i = int(rng.integers(len(samples)))
        s = samples[i]
        h, w = s.label.shape
        if rng.random() < pos_fraction and len(pos_index[i]):
            r, c = pos_index[i][rng.integers(len(pos_index[i]))]
            r0 = int(np.clip(r - rng.integers(size), 0, h - size))
            c0 = int(np.clip(c - rng.integers(size), 0, w - size))
        else:
            r0, c0 = int(rng.integers(0, h - size + 1)), int(rng.integers(0, w - size + 1))
        picks.append((i, r0, c0))
    return picks


def _augment(x: np.ndarray, k: int, flip: bool) -> np.ndarray:
    x = np.rot90(x, k, axes=(-2, -1))
    return np.ascontiguousarray(x[..., ::-1] if flip else x)


def dice_bce_loss(logits: torch.Tensor, target: torch.Tensor, mask: torch.Tensor, pos_weight: float) -> torch.Tensor:
    bce = nn.functional.binary_cross_entropy_with_logits(logits, target, reduction="none", pos_weight=torch.tensor(pos_weight))
    bce = (bce * mask).sum() / mask.sum().clamp(min=1)
    prob = torch.sigmoid(logits) * mask
    inter = (prob * target).sum()
    dice = 1 - (2 * inter + 1) / (prob.sum() + (target * mask).sum() + 1)
    return bce + dice


@torch.inference_mode()
def predict_full(model: SiameseUNet, s: Sample, mean: np.ndarray, std: np.ndarray, patch: int = 256) -> np.ndarray:
    from ..detectors.unet import _hann2d  # reutilizamos la ventana de mezcla de producción

    ref, obs = _norm(s.ref, mean, std), _norm(s.obs, mean, std)
    _, h, w = ref.shape
    stride = max(patch // 2, patch - 64)
    weight = _hann2d(patch)
    acc = np.zeros((h, w), np.float32)
    norm = np.zeros((h, w), np.float32)
    rows = sorted({*range(0, max(h - patch, 0) + 1, stride), max(h - patch, 0)})
    cols = sorted({*range(0, max(w - patch, 0) + 1, stride), max(w - patch, 0)})
    model.eval()
    for r in rows:
        for c in cols:
            a = torch.from_numpy(ref[None, :, r : r + patch, c : c + patch])
            b = torch.from_numpy(obs[None, :, r : r + patch, c : c + patch])
            p = torch.sigmoid(model(a, b))[0, 0].numpy()
            acc[r : r + patch, c : c + patch] += p * weight
            norm[r : r + patch, c : c + patch] += weight
    return acc / np.maximum(norm, 1e-6)


def best_threshold(probs: list[np.ndarray], labels: list[np.ndarray]) -> tuple[float, float]:
    best = (0.5, -1.0)
    for t in np.arange(0.2, 0.99, 0.025):
        cm = ConfusionMatrix()
        for p, y in zip(probs, labels, strict=True):
            m = y != IGNORE
            cm.update(p >= t, y == 1, m)
        f1 = float(cm.report()["f1"])
        if f1 > best[1]:
            best = (float(t), f1)
    return best


def evaluate(probs: list[np.ndarray], samples: list[Sample], threshold: float) -> dict[str, Any]:
    cm = ConfusionMatrix()
    for p, s in zip(probs, samples, strict=True):
        cm.update(p >= threshold, s.label == 1, s.label != IGNORE)
    return cm.report()


def evaluate_baseline(samples: list[Sample]) -> dict[str, Any]:
    det = SpectralBaselineDetector()
    cm = ConfusionMatrix()
    for s in samples:
        bands_r = {b: s.ref[i] for i, b in enumerate(REFLECTANCE_BANDS)}
        bands_o = {b: s.obs[i] for i, b in enumerate(REFLECTANCE_BANDS)}
        valid = np.isfinite(s.ref).all(0) & np.isfinite(s.obs).all(0)
        out = det.predict(bands_r, bands_o, valid)
        cm.update(np.nan_to_num(out.score) >= 0.5, s.label == 1, s.label != IGNORE)
    return cm.report()


def train(
    data_dir: Path,
    splits: dict[str, str],
    out: Path,
    epochs: int = 12,
    steps_per_epoch: int = 60,
    batch: int = 8,
    patch: int = 256,
    lr: float = 1e-3,
    seed: int = 7,
) -> dict[str, Any]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    samples = load_samples(data_dir, splits)
    tr = [s for s in samples if s.split == "train"]
    va = [s for s in samples if s.split == "val"]
    te = [s for s in samples if s.split == "test"]
    if not tr or not va or not te:
        raise RuntimeError("need at least one train, val and test AOI")
    mean, std = band_stats(tr)
    pos = sum(int((s.label == 1).sum()) for s in tr)
    neg = sum(int((s.label == 0).sum()) for s in tr)
    pos_weight = float(min(20.0, neg / max(pos, 1)))
    model = SiameseUNet(in_channels=len(REFLECTANCE_BANDS))
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    trn = [(_norm(s.ref, mean, std), _norm(s.obs, mean, std), s.label) for s in tr]
    history = []
    best_val, best_state = -1.0, None
    t0 = time.time()
    for epoch in range(epochs):
        model.train()
        losses = []
        for _ in range(steps_per_epoch):
            picks = random_patches(tr, batch, patch, rng)
            xa, xb, ys, ms = [], [], [], []
            for i, r, c in picks:
                k, flip = int(rng.integers(4)), bool(rng.integers(2))
                a, b, y = trn[i]
                win = (slice(r, r + patch), slice(c, c + patch))
                xa.append(_augment(a[(slice(None), *win)], k, flip))
                xb.append(_augment(b[(slice(None), *win)], k, flip))
                yy = _augment(y[win], k, flip)
                ys.append((yy == 1).astype(np.float32))
                ms.append((yy != IGNORE).astype(np.float32))
            logits = model(torch.from_numpy(np.stack(xa)), torch.from_numpy(np.stack(xb)))
            loss = dice_bce_loss(logits[:, 0], torch.from_numpy(np.stack(ys)), torch.from_numpy(np.stack(ms)), pos_weight)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss))
        sched.step()
        val_probs = [predict_full(model, s, mean, std, patch) for s in va]
        thr, f1 = best_threshold(val_probs, [s.label for s in va])
        history.append(
            {"epoch": epoch + 1, "loss": float(np.mean(losses)), "val_f1": f1, "val_threshold": thr, "elapsed_s": round(time.time() - t0)}
        )
        log.info("epoch %d loss %.4f val_f1 %.3f @ %.2f", epoch + 1, np.mean(losses), f1, thr)
        if f1 > best_val:
            best_val, best_state, best_thr = f1, {k: v.clone() for k, v in model.state_dict().items()}, thr
    assert best_state is not None
    model.load_state_dict(best_state)
    test_probs = [predict_full(model, s, mean, std, patch) for s in te]
    metrics = {
        "test_model": evaluate(test_probs, te, best_thr),
        "test_baseline": evaluate_baseline(te),
        "val_f1": best_val,
        "threshold": best_thr,
        "splits": splits,
        "history": history,
        "pos_weight": pos_weight,
        "train_positive_px": pos,
    }
    ckpt = Checkpoint(
        model,
        tuple(REFLECTANCE_BANDS),
        mean,
        std,
        best_thr,
        {k: metrics[k] for k in ("test_model", "test_baseline", "val_f1")},
        "Hansen GFC lossyear weak labels; Sentinel-2 L2A C1 dry-season composites",
        "0.1.0",
    )
    save_checkpoint(out, ckpt)
    out.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics
