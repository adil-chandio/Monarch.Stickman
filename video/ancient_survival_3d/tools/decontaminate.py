#!/usr/bin/env python3
"""Remove the studio backdrop from the cards' semi-transparent edge pixels.

A matte leaves a ring of half-transparent pixels that still carry the old
background colour. The rasteriser blends those pixels as-is, so every card used
to wear a pale halo along its silhouette. This bleeds the *interior* colour
outwards through the half-transparent ring (the standard decontamination step of
alpha compositing) and leaves fully opaque pixels untouched.

    python3 tools/decontaminate.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
PHOTOS = HERE / "photo"


def _blur(x: np.ndarray) -> np.ndarray:
    """3x3 box blur, edge-clamped."""
    p = np.pad(x, ((1, 1), (1, 1)) + ((0, 0),) * (x.ndim - 2), mode="edge")
    out = np.zeros_like(x)
    for dy in range(3):
        for dx in range(3):
            out += p[dy:dy + x.shape[0], dx:dx + x.shape[1]]
    return out / 9.0


def clean(rgba: np.ndarray, rounds: int = 14) -> np.ndarray:
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    a = rgba[..., 3].astype(np.float32) / 255.0
    solid = a > 0.97
    pre = rgb * a[..., None]
    aw = a.copy()
    for _ in range(rounds):
        pre = _blur(pre)
        aw = _blur(aw)
    fill = pre / np.maximum(aw[..., None], 1e-4)
    out = rgb.copy()
    edge = (~solid) & (a > 0.002)
    out[edge] = fill[edge]
    out[~edge] = np.clip(out[~edge], 0.0, 1.0)
    res = rgba.copy()
    res[..., :3] = np.round(np.clip(out, 0.0, 1.0) * 255.0).astype(np.uint8)
    return res


def main() -> None:
    cards = json.loads((PHOTOS / "people.json").read_text())["cards"]
    atlas = np.array(Image.open(PHOTOS / "people_atlas.png").convert("RGBA"))
    for name, c in cards.items():
        x, y, w, h = c["rect"]
        patch = atlas[y:y + h, x:x + w]
        atlas[y:y + h, x:x + w] = clean(patch)
    Image.fromarray(atlas, "RGBA").save(PHOTOS / "people_atlas.png")
    for path in sorted(PHOTOS.glob("card_*.png")):
        im = Image.open(path).convert("RGBA")
        Image.fromarray(clean(np.asarray(im)), "RGBA").save(path)
    print("cleaned", len(cards), "cards")


if __name__ == "__main__":
    main()
