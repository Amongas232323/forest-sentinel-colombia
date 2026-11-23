"""Siamese U-Net con skip-connections de diferencia (FC-Siam-diff).

Referencia: Daudt, Le Saux & Boulch, "Fully Convolutional Siamese Networks for
Change Detection", ICIP 2018. La escogimos sobre SegFormer/DeepLabV3+ porque:

* está pensada para detección de cambios bi-temporal *multiespectral*;
* compartir pesos entre fechas reduce los parámetros a la mitad y regulariza el entrenamiento,
  lo cual importa con los datasets etiquetados tan pequeños que hay para el trópico;
* ~1.4 M de parámetros → se puede hacer inferencia en CPU para AOIs de escala municipal.

Ver docs/AI_MODEL_DOCUMENTATION.md para la tabla comparativa.
"""

from __future__ import annotations

import torch
from torch import nn


def _block(cin: int, cout: int, dropout: float) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, padding=1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(inplace=True),
        nn.Conv2d(cout, cout, 3, padding=1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(inplace=True),
        nn.Dropout2d(dropout) if dropout > 0 else nn.Identity(),
    )


class Encoder(nn.Module):
    def __init__(self, in_channels: int, widths: tuple[int, ...], dropout: float) -> None:
        super().__init__()
        chans = (in_channels, *widths)
        self.stages = nn.ModuleList(_block(chans[i], chans[i + 1], dropout) for i in range(len(widths)))
        self.pool = nn.MaxPool2d(2)

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        feats = []
        for i, stage in enumerate(self.stages):
            if i > 0:
                x = self.pool(x)
            x = stage(x)
            feats.append(x)
        return feats


class SiameseUNet(nn.Module):
    """Entrada: dos tensores (B, C, H, W). Salida: logits de cambio (B, 1, H, W).

    H y W tienen que ser divisibles por 2 ** (len(widths) - 1).
    """

    def __init__(
        self,
        in_channels: int = 6,
        widths: tuple[int, ...] = (16, 32, 64, 128),
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.widths = widths
        self.encoder = Encoder(in_channels, widths, dropout)
        self.ups = nn.ModuleList()
        self.decs = nn.ModuleList()
        rev = list(reversed(widths))
        cur = rev[0] * 2  # cuello de botella: concat(f_obs, |f_obs - f_ref|)
        for skip in rev[1:]:
            self.ups.append(nn.ConvTranspose2d(cur, skip, 2, stride=2))
            self.decs.append(_block(skip * 2, skip, 0.0))
            cur = skip
        self.head = nn.Conv2d(cur, 1, 1)

    @property
    def divisor(self) -> int:
        return 2 ** (len(self.widths) - 1)

    def forward(self, ref: torch.Tensor, obs: torch.Tensor) -> torch.Tensor:
        f_ref = self.encoder(ref)
        f_obs = self.encoder(obs)
        diffs = [torch.abs(a - b) for a, b in zip(f_obs, f_ref, strict=True)]
        x = torch.cat([f_obs[-1], diffs[-1]], dim=1)
        for up, dec, skip in zip(self.ups, self.decs, reversed(diffs[:-1]), strict=True):
            x = up(x)
            x = dec(torch.cat([x, skip], dim=1))
        return self.head(x)
