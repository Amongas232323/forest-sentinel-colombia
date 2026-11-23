from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sentinel_ml.detectors import get_detector  # noqa: E402
from sentinel_ml.model.checkpoint import Checkpoint, load_checkpoint, save_checkpoint  # noqa: E402
from sentinel_ml.model.siamese_unet import SiameseUNet  # noqa: E402


def test_siamese_unet_output_shape():
    m = SiameseUNet(in_channels=6, widths=(8, 16, 32))
    a, b = torch.randn(2, 6, 64, 64), torch.randn(2, 6, 64, 64)
    assert m(a, b).shape == (2, 1, 64, 64)


def test_identical_inputs_have_zero_difference_features():
    m = SiameseUNet(in_channels=6, widths=(8, 16)).eval()
    x = torch.randn(1, 6, 32, 32)
    feats_a, feats_b = m.encoder(x), m.encoder(x.clone())
    assert all(torch.allclose(fa, fb) for fa, fb in zip(feats_a, feats_b, strict=True))


def test_checkpoint_roundtrip_and_detector(tmp_path):
    model = SiameseUNet(in_channels=6, widths=(8, 16, 32))
    ckpt = Checkpoint(
        model,
        ("blue", "green", "red", "nir", "swir16", "swir22"),
        np.zeros(6, np.float32),
        np.ones(6, np.float32),
        0.4,
        {"f1": 0.0},
        "unit-test",
        "0.0.1",
    )
    path = tmp_path / "m.pt"
    save_checkpoint(path, ckpt)
    loaded = load_checkpoint(path)
    assert loaded.threshold == pytest.approx(0.4)
    det = get_detector("auto", path)
    assert det.kind == "deep-learning"
    bands = {b: np.random.rand(300, 280).astype(np.float32) * 0.3 for b in ckpt.bands}
    out = det.predict(bands, bands, np.ones((300, 280), bool))
    assert out.score.shape == (300, 280)
    assert np.all((out.score >= 0) & (out.score <= 1))


def test_checkpoint_rejects_unknown_format(tmp_path):
    p = tmp_path / "bad.pt"
    torch.save({"format": "something-else"}, p)
    with pytest.raises(ValueError):
        load_checkpoint(p)
