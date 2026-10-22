#!/usr/bin/env python3
"""Turn the AI-generated studio plates into scene-ready photo cards.

The generated plates are full-body studio photographs on a flat light-grey
seamless backdrop. This tool

  1. estimates the backdrop colour from the border,
  2. builds a matte with a colour-distance test plus a border flood fill, so
     only the connected backdrop is removed and nothing inside the body is cut,
  3. feathers the matte one pixel and unmixes the backdrop tint off the edge,
  4. crops to the body (feet = the card's bottom edge, head = the top edge),
  5. packs every card into one RGBA atlas plus a JSON manifest of rectangles.

The rasteriser samples this atlas for material ids >= 20 (see `raster.c`), so
the photoreal humans are ordinary 3D geometry in the scene: they are depth
sorted, fogged, misted, lit by the sun and by the camp fire, and they carry the
same grade and grain as everything else.

Usage:  python3 tools/make_photo_cards.py
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent.parent
PHOTOS = HERE / "photo"
ATLAS = PHOTOS / "people_atlas.png"
MANIFEST = PHOTOS / "people.json"

# name -> (source plate, real standing height in metres)
CARDS = {
    "hunter_stand": ("hunter_front.png", 1.76),
    "hunter_walk": ("hunter_walk.png", 1.76),
    "woman_stand": ("woman_front.png", 1.68),
    "woman_warm": ("woman_warm.png", 1.68),
    "elder_stand": ("elder_front.png", 1.70),
    "elder_warm": ("elder_warm.png", 1.70),
}

CARD_HEIGHT = 1400          # px of atlas used for the tallest card
FEATHER_PX = 1.2


def estimate_backdrop(rgb: np.ndarray) -> np.ndarray:
    h, w, _ = rgb.shape
    band = 8
    border = np.concatenate([
        rgb[:band].reshape(-1, 3), rgb[-band:].reshape(-1, 3),
        rgb[:, :band].reshape(-1, 3), rgb[:, -band:].reshape(-1, 3)])
    return np.median(border, axis=0)


def backdrop_surface(rgb: np.ndarray, chroma_max: float = 14.0,
                      bright_min: float = 70.0) -> np.ndarray:
    """Fit a smooth quadratic surface to the seamless studio sweep.

    Studio plates are not a flat colour: they vignette, gradient and carry a
    soft floor shadow. A single median leaves a rim of backdrop around the
    subject, so instead we find the desaturated, bright pixels (the sweep),
    fit a 2nd-order polynomial per channel and return that model as an image.
    """
    h, w, _ = rgb.shape
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    cand = (chroma < chroma_max) & (rgb.mean(axis=2) > bright_min)
    # the sweep is everything connected to the border that is desaturated
    seen = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if cand[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if cand[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and cand[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    ys, xs = np.nonzero(seen)
    if len(ys) < 200:                                   # nothing to fit
        return np.ones_like(rgb) * estimate_backdrop(rgb)[None, None, :]
    step = max(1, len(ys) // 40000)
    ys, xs = ys[::step], xs[::step]
    X = xs / w
    Y = ys / h
    A = np.stack([np.ones_like(X), X, Y, X * X, X * Y, Y * Y], axis=1)
    gy, gx = np.mgrid[0:h, 0:w]
    GX = gx / w
    GY = gy / h
    B = np.stack([np.ones_like(GX), GX, GY, GX * GX, GX * GY, GY * GY], axis=-1)
    model = np.empty_like(rgb)
    for c in range(3):
        coef, *_ = np.linalg.lstsq(A, rgb[ys, xs, c], rcond=None)
        model[..., c] = np.einsum("...k,k->...", B, coef)
    return np.clip(model, 0, 255)


def matte(rgb: np.ndarray, model: np.ndarray, tol: float = 11.0,
          soft: float = 9.0) -> np.ndarray:
    """Alpha in [0, 1]: 1 = subject, 0 = backdrop.

    Two tests, because the plates carry a soft floor shadow on a white sweep:

    * colour distance from the fitted sweep (catches the sweep itself),
    * a neutral-darkening test: a shadow is the sweep multiplied by a scalar,
      so the per-channel ratio to the model is flat. Skin and hide are warm,
      so their ratios are not flat and they survive.
    """
    if model.ndim == 1:
        model = np.broadcast_to(model, rgb.shape)
    diff = np.linalg.norm(rgb - model, axis=2)
    near = np.clip((diff - tol) / soft, 0.0, 1.0).astype(np.float32)

    denom = np.maximum(model, 1.0)
    ratio = rgb / denom
    spread = ratio.max(axis=2) - ratio.min(axis=2)
    level = ratio.mean(axis=2)
    shadow = (spread < 0.05) & (level > 0.70) & (level < 1.04) & (diff > tol)
    near[shadow] = 0.0

    # only remove backdrop that is connected to the border, so a bright patch
    # inside the body (teeth, stitched hide) can never punch a hole
    h, w = near.shape
    seen = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if near[y, x] < 0.55 and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if near[y, x] < 0.55 and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and near[ny, nx] < 0.55:
                seen[ny, nx] = True
                q.append((ny, nx))
    near[seen] = 0.0
    return near


def drop_faint(alpha: np.ndarray, floor: float = 0.55) -> np.ndarray:
    """Remove soft-shadow residue: anything not clearly part of the body."""
    a = alpha.copy()
    a[a < floor] = 0.0
    return a


def keep_largest(alpha: np.ndarray) -> np.ndarray:
    """Keep only the biggest connected blob: kills shadow specks and smudges."""
    mask = alpha > 0.5
    h, w = mask.shape
    label = np.zeros((h, w), np.int32)
    best, best_n, cur = 0, 0, 0
    for sy in range(h):
        row = mask[sy]
        if not row.any():
            continue
        for sx in range(w):
            if not row[sx] or label[sy, sx]:
                continue
            cur += 1
            label[sy, sx] = cur
            q = deque([(sy, sx)])
            n = 0
            while q:
                y, x = q.popleft()
                n += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1),
                               (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not label[ny, nx]:
                        label[ny, nx] = cur
                        q.append((ny, nx))
            if n > best_n:
                best, best_n = cur, n
    out = alpha.copy()
    out[label != best] = 0.0
    return out


def clean(alpha: np.ndarray) -> np.ndarray:
    """Drop specks, close small holes, feather the edge."""
    alpha = keep_largest(alpha)
    im = Image.fromarray((alpha * 255).astype(np.uint8), "L")
    im = im.filter(ImageFilter.MedianFilter(3))
    im = im.filter(ImageFilter.MaxFilter(3))       # close pinholes in the body
    im = im.filter(ImageFilter.MinFilter(3))       # put the outer edge back
    im = im.filter(ImageFilter.MinFilter(3))       # erode 1px of fringe
    im = im.filter(ImageFilter.GaussianBlur(FEATHER_PX))
    a = np.asarray(im).astype(np.float32) / 255.0
    # keep the interior fully solid, only the rim is soft
    solid = (a > 0.90)
    solid = np.asarray(Image.fromarray((solid * 255).astype(np.uint8), "L")
                       .filter(ImageFilter.MinFilter(5))).astype(bool)
    a[solid] = 1.0
    return a


def defringe(rgb: np.ndarray, alpha: np.ndarray, bg: np.ndarray) -> np.ndarray:
    """Unmix the backdrop colour from partially transparent edge pixels."""
    out = rgb.copy()
    a = alpha[..., None]
    edge = (alpha > 0.02) & (alpha < 0.98)
    if edge.any():
        # C = a*F + (1-a)*B  ->  F = (C - (1-a)*B) / a
        f = (out[edge] - (1.0 - a[edge]) * bg[edge]) / np.maximum(a[edge], 0.08)
        out[edge] = np.clip(f, 0, 255)
    return out


def crop_to_body(rgb: np.ndarray, alpha: np.ndarray, pad: int = 6):
    ys, xs = np.nonzero(alpha > 0.75)
    if len(ys) == 0:
        raise ValueError("empty matte")
    y0, y1 = max(0, ys.min() - pad), min(rgb.shape[0], ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(rgb.shape[1], xs.max() + 1 + pad)
    return rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]


def build_card(path: Path) -> tuple[np.ndarray, dict]:
    rgb = np.asarray(Image.open(PHOTOS / path).convert("RGB"), np.float32)
    bg = backdrop_surface(rgb)                 # H x W x 3 model of the sweep
    a = clean(drop_faint(matte(rgb, bg)))
    rgb = defringe(rgb, a, bg)
    rgb, a = crop_to_body(rgb, a)
    # scale so the body is CARD_HEIGHT tall
    scale = CARD_HEIGHT / rgb.shape[0]
    w = max(8, round(rgb.shape[1] * scale))
    im = Image.fromarray(np.dstack([rgb, a * 255.0]).astype(np.uint8), "RGBA")
    im = im.resize((w, CARD_HEIGHT), Image.Resampling.LANCZOS)
    arr = np.asarray(im, np.uint8).copy()
    return arr, {"w": w, "h": CARD_HEIGHT,
                 "aspect": round(w / CARD_HEIGHT, 5)}


def main() -> None:
    cards, meta = [], {}
    for name, (src, height_m) in CARDS.items():
        arr, info = build_card(Path(src))
        info["height_m"] = height_m
        # metres per card unit along x, so the world quad keeps the true aspect
        info["width_m"] = round(height_m * info["aspect"], 4)
        cards.append((name, arr, info))
        print(f"{name:14s} {arr.shape[1]}x{arr.shape[0]}  "
              f"{info['width_m']}m x {height_m}m")

    # shelf-pack into one atlas: tallest first, fixed shelf height
    order = sorted(cards, key=lambda c: -c[1].shape[1])
    pad = 4
    cursor_x, cursor_y, shelf_h, atlas_w = pad, pad, 0, 0
    placed = []
    for name, arr, info in order:
        h, w = arr.shape[:2]
        if cursor_x + w + pad > 6000:
            cursor_x = pad
            cursor_y += shelf_h + pad
            shelf_h = 0
        placed.append((name, arr, info, cursor_x, cursor_y))
        cursor_x += w + pad
        atlas_w = max(atlas_w, cursor_x)
        shelf_h = max(shelf_h, h)
    atlas_h = cursor_y + shelf_h + pad
    atlas = np.zeros((atlas_h, atlas_w, 4), np.uint8)
    for name, arr, info, x, y in placed:
        atlas[y:y + arr.shape[0], x:x + arr.shape[1]] = arr
        info["rect"] = [int(x), int(y), int(arr.shape[1]), int(arr.shape[0])]
        info["u"] = [round(x / atlas_w, 6), round((x + arr.shape[1]) / atlas_w, 6)]
        info["v"] = [round(y / atlas_h, 6), round((y + arr.shape[0]) / atlas_h, 6)]
        meta[name] = info
        Image.fromarray(arr, "RGBA").save(PHOTOS / f"card_{name}.png")
    Image.fromarray(atlas, "RGBA").save(ATLAS)
    MANIFEST.write_text(json.dumps({"atlas": {"w": atlas_w, "h": atlas_h},
                                    "cards": meta}, indent=1))
    print(f"atlas {atlas_w}x{atlas_h} -> {ATLAS}")


if __name__ == "__main__":
    main()
