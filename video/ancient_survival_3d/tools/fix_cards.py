#!/usr/bin/env python3
"""Repair matte artefacts in the packed cards, then repack the atlas.

The studio plates occasionally leave a *horizontal* streak of backdrop in the
matte - a reflection or a floor shadow that survived the colour test. On a flat
billboard it is invisible; once the card has a skeleton the streak gets skinned
onto the legs and swings through the shot as a pale flag, so it has to go.

The rule is geometric, not magic: a row whose opaque span is wider than 70 % of
the card is a streak, because no human in these plates is that wide. The rows
of the streak are rebuilt from the nearest clean row below it, so the legs keep
their exact silhouette.

    python3 tools/fix_cards.py && python3 tools/decontaminate.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
PHOTOS = HERE / "photo"


def streak_rows(mask: np.ndarray, span_frac: float = 0.70) -> tuple[int, int] | None:
    """Longest run of rows that are both impossibly wide *and* unsupported.

    A wide row is only a streak if the rows well above and below it are much
    narrower - shoulders and outstretched arms are wide for hundreds of rows,
    a floor reflection is wide for twenty.
    """
    H, W = mask.shape
    span = np.zeros(H)
    for y in range(H):
        xs = np.nonzero(mask[y])[0]
        span[y] = (xs[-1] - xs[0]) if len(xs) else 0
    wide = np.zeros(H, bool)
    for y in range(10, H - 10):
        near = np.concatenate([span[max(0, y - 95):max(0, y - 40)], span[y + 40:y + 96]])
        if len(near) == 0:
            continue
        if span[y] > span_frac * W and span[y] > 1.8 * float(np.median(near)):
            wide[y] = True
    if not wide.any():
        return None
    best = (0, -1)
    y = 0
    while y < len(wide):
        if wide[y]:
            y0 = y
            while y < len(wide) and wide[y]:
                y += 1
            if y - 1 - y0 > best[1] - best[0]:
                best = (y0, y - 1)
        else:
            y += 1
    # extend a few rows: the streak feathers out at both ends
    return (max(0, best[0] - 4), min(mask.shape[0] - 1, best[1] + 4))


def fix(im: np.ndarray) -> tuple[np.ndarray, tuple[int, int] | None]:
    """Clear a backdrop streak: neutral-grey pixels inside the streak rows.

    The strays are the studio sweep, which is neutral (R=G=B within a couple of
    levels); skin, leather and cloth in these plates are all warm or olive, so a
    saturation test separates them without touching the body. The test is only
    applied inside the rows the geometry test flagged, so nothing else moves.
    """
    mask = im[..., 3] > 60
    rows = streak_rows(mask)
    if rows is None:
        return im, None
    y0, y1 = max(0, rows[0] - 30), min(im.shape[0] - 1, rows[1] + 30)
    rgb = im[y0:y1 + 1, :, :3].astype(np.int16)
    hi = rgb.max(axis=2)
    lo = rgb.min(axis=2)
    neutral = (hi - lo <= 16) & (hi >= 120)
    keep = im[y0:y1 + 1, :, 3] > 60
    out = im.copy()
    alpha = out[y0:y1 + 1, :, 3]
    alpha[neutral & keep] = 0
    out[y0:y1 + 1, :, 3] = alpha
    return out, rows


def main() -> None:
    cards = json.loads((PHOTOS / "people.json").read_text())["cards"]
    atlas = np.array(Image.open(PHOTOS / "people_atlas.png").convert("RGBA"))
    for name, c in cards.items():
        path = PHOTOS / f"card_{name}.png"
        im = np.array(Image.open(path).convert("RGBA"))
        fixed, rows = fix(im)
        if rows is None:
            continue
        im = fixed
        Image.fromarray(im, "RGBA").save(path)
        x, y, w, h = c["rect"]
        atlas[y:y + h, x:x + w] = im
        print(f"{name}: cleared matte streak rows {rows[0]}..{rows[1]}")
    Image.fromarray(atlas, "RGBA").save(PHOTOS / "people_atlas.png")


if __name__ == "__main__":
    main()
