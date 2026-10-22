#!/usr/bin/env python3
"""Photoreal human cards: AI-generated people placed as 3D geometry.

`tools/make_photo_cards.py` packs the studio plates into one RGBA atlas. This
module turns a rectangle of that atlas into a quad mesh that the rasteriser
draws with real depth, fog, mist, sun shadowing and fire light (material id 21
in `raster.c`). The quads carry a card-local horizontal coordinate in the vertex
colour so the shader can swing the shading normal around the body axis: light
rolls off towards the silhouette instead of lighting a flat billboard.

Public API
----------
`CARDS`      manifest of every card (world size in metres, atlas rectangle)
`atlas()`    the packed RGBA atlas as an (H, W, 4) uint8 array
`add_person(b, name, pos, yaw, ...)`  add one figure to a `Builder`
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PHOTOS = HERE / "photo"
MANIFEST = PHOTOS / "people.json"
ATLAS = PHOTOS / "people_atlas.png"

MAT_CARD = 21.0          # >= 20 => the rasteriser samples the photo atlas


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text())["cards"]


CARDS = _manifest()


def atlas() -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.open(ATLAS).convert("RGBA"), np.uint8)


def card_size(name: str) -> tuple[float, float]:
    c = CARDS[name]
    return float(c["width_m"]), float(c["height_m"])


def add_person(b, name: str, pos, yaw: float = 0.0,
               height: float | None = None, lean: float = 0.0,
               gain: float = 0.92, contact_shadow: bool = True,
               shadow_colour=(0.10, 0.085, 0.07)) -> tuple:
    """Place one photoreal figure standing at `pos`, facing `yaw`.

    yaw = 0 means the figure faces +Z (towards a camera that sits on +Z looking
    back down -Z). `height` overrides the card's real height in metres (used for
    children / forced perspective), `lean` tilts the card forward in radians.
    Returns the world-space centre of the head and of the feet, so callers can
    hang props (spears, spearshafts, baskets) off the body.
    """
    c = CARDS[name]
    w_m = c["width_m"]
    h_m = c["height_m"]
    if height is not None:
        k = height / h_m
        w_m *= k
        h_m = height
    x, y, z = (float(v) for v in pos)
    u0, u1 = c["u"]
    v0, v1 = c["v"]

    # card frame: `side` runs left->right on the picture, `up` is world up
    dx, dz = math.sin(yaw), math.cos(yaw)
    side = np.array([dz, 0.0, -dx])
    up = np.array([0.0, 1.0, 0.0])
    forward = np.array([dx, 0.0, dz])
    base = np.array([x, y, z])
    if lean:
        up = up * math.cos(lean) + forward * math.sin(lean)

    bl = base - side * (w_m * 0.5)
    br = base + side * (w_m * 0.5)
    tl = bl + up * h_m
    tr = br + up * h_m
    # front face must wind so the rasteriser sees it (CCW, normal towards yaw)
    b.mat = MAT_CARD
    b.quad(bl, br, tr, tl, (gain, gain, 0.0),
           uvs=[(u0, v1), (u1, v1), (u1, v0), (u0, v0)])
    # re-tag the four vertices' blue channel with the card-local u
    for vi, uu in ((-4, 0.0), (-3, 1.0), (-2, 1.0), (-1, 0.0)):
        b.c[vi] = np.array([gain, gain, uu])
    if contact_shadow:
        b.mat = 0.0
        for i, (scale, col) in enumerate(((1.9, (0.235, 0.215, 0.175)),
                                          (1.3, (0.170, 0.155, 0.126)),
                                          (0.85, (0.100, 0.091, 0.074)))):
            b.sphere((x, y + 0.008 + i * 0.0012, z), max(0.15, w_m * 0.34 * scale),
                     col, rings=4, seg=16, scale=(1.0, 0.014, 0.66))
    feet = np.array([x, y, z])
    head = base + up * h_m * 0.92 + forward * 0.02
    return head, feet


def add_card_shadow(b, name: str, pos, yaw: float = 0.0,
                    height: float | None = None, strength: float = 0.5) -> None:
    """A soft elliptical contact shadow, fading out to the ground tone.

    The rasteriser has no blending, so the gradient is built from nested opaque
    ellipses: the widest (drawn first) matches the dry ground, and each smaller
    ring is darker, so the patch reads as a pool of shade rather than a disc.
    """
    c = CARDS[name]
    w_m = c["width_m"]
    if height is not None:
        w_m *= height / c["height_m"]
    x, y, z = (float(v) for v in pos)
    b.mat = 0.0
    rings = ((2.35, (0.235, 0.215, 0.175)),
             (1.80, (0.205, 0.188, 0.152)),
             (1.35, (0.165, 0.150, 0.122)),
             (0.98, (0.120, 0.108, 0.088)),
             (0.66, (0.085, 0.076, 0.062)))
    for i, (scale, col) in enumerate(rings):
        k = 0.55 + 0.45 * (1.0 - i / (len(rings) - 1))
        b.sphere((x, y + 0.008 + i * 0.0012, z), max(0.16, w_m * 0.34 * scale),
                 tuple(v * (0.75 + 0.35 * strength) for v in col),
                 rings=4, seg=18, scale=(1.0, 0.014, 0.62))


def yaw_for(pos, cam, aim=None, max_dev: float = 0.34) -> float:
    """Card-friendly facing: look at the camera, tilted toward `aim`.

    A photo card only has one view, so it must stay close to face-on to the
    lens (beyond ~20 degrees it collapses to a sliver). This returns the yaw
    that faces the camera, biased toward `aim` (the fire, a companion) but
    clamped to `max_dev` radians so the figure never turns edge-on.
    """
    x, _, z = (float(v) for v in pos)
    base = math.atan2(float(cam[0]) - x, float(cam[2]) - z)
    if aim is None:
        return base
    want = math.atan2(float(aim[0]) - x, float(aim[2]) - z)
    delta = (want - base + math.pi) % (2 * math.pi) - math.pi
    delta = max(-max_dev, min(max_dev, delta))
    return base + delta


def mouth_point(head, yaw: float, forward: float = 0.095,
                down: float = 0.030):
    """Approximate the mouth position from the card's head anchor."""
    head = np.asarray(head, float)
    fwd = np.array([math.sin(yaw), 0.0, math.cos(yaw)])
    return head + fwd * forward - np.array([0.0, down, 0.0])
