#!/usr/bin/env python3
"""Stage plates: photoreal matte paintings used as real 3D geometry.

The environment of the reel used to be procedural geometry. It was honest 3D
and it looked like it: low-poly ridges, plastic rocks, a smooth dune. The
reference (a pre-viz reel that hands its blocking to a photoreal video model)
is about the *photographic* quality of the frame, not about the polygon count.

So the set is now a digital backlot: photoreal AI plates are placed as large
quads at real distances (material 22 in `raster.c`, which samples a second RGBA
texture and writes the photograph straight to the frame - a matte painting is
already lit and graded, so it must not be multiplied by the scene sun). They
still write depth, so 3D characters, props and embers sit in front of or behind
them correctly, and a moving camera gives real parallax between the layers.

`add_plate()` fits a plate to the frame of the camera that is about to render
it, so a plate always covers the full frame at its own distance.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATLAS = HERE / "plates" / "stage_atlas.png"

# name -> (u0, u1) inside plates/stage_atlas.png (four 768x1376 tiles)
PLATES = {
    "night": (0.000, 0.250),
    "camp": (0.250, 0.500),
    "shadow": (0.500, 0.750),
    "glow": (0.750, 1.000),
}

MAT_PLATE = 22.0
MAT_ADD = 23.0

_ATLAS = None


def atlas() -> np.ndarray:
    global _ATLAS
    if _ATLAS is None:
        _ATLAS = np.ascontiguousarray(
            np.asarray(Image.open(ATLAS).convert("RGBA"), np.uint8))
    return _ATLAS


def _basis(cam_pos, target, up=(0.0, 1.0, 0.0)):
    pos = np.asarray(cam_pos, float)
    fwd = np.asarray(target, float) - pos
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, np.asarray(up, float))
    right /= np.linalg.norm(right)
    up2 = np.cross(right, fwd)
    return pos, fwd, right, up2


def add_plate(b, name: str, cam_pos, target, fov: float, aspect: float,
              distance: float = 40.0, overscan: float = 1.0,
              shift=(0.0, 0.0), roll: float = 0.0, tilt: float = 0.0) -> None:
    """Place `name` so it exactly fills the camera's frame at `distance`.

    `shift` moves the plate in camera space (x right, y up, in units of the
    frame half-height), `roll` rotates it in its own plane and `tilt` leans it
    back (a plate standing on the ground can be leaned instead of hung).
    """
    pos, fwd, right, up = _basis(cam_pos, target)
    half_h = distance * math.tan(fov * 0.5) * overscan
    half_w = half_h * aspect
    centre = pos + fwd * distance + right * (shift[0] * half_h) + up * (shift[1] * half_h)
    if roll:
        c, s = math.cos(roll), math.sin(roll)
        r2 = right * c + up * s
        u2 = up * c - right * s
        right, up = r2, u2
    if tilt:
        c, s = math.cos(tilt), math.sin(tilt)
        u2 = up * c + fwd * s
        f2 = fwd * c - up * s
        up, fwd = u2, f2
    bl = centre - right * half_w - up * half_h
    br = centre + right * half_w - up * half_h
    tr = centre + right * half_w + up * half_h
    tl = centre - right * half_w + up * half_h
    u0, u1 = PLATES[name]
    b.mat = MAT_PLATE
    # winding: this rasteriser keeps the counter-clockwise-in-screen-space
    # face, i.e. bottom-left -> bottom-right -> top-right -> top-left
    b.quad(bl, br, tr, tl, (1.0, 1.0, 1.0),
           uvs=[(u0, 1.0), (u1, 1.0), (u1, 0.0), (u0, 0.0)])


def project(cam_pos, target, fov: float, aspect: float, w: int, h: int, p):
    """Screen pixel for a world point - used to line 3D props up on a plate."""
    pos, fwd, right, up = _basis(cam_pos, target)
    v = np.asarray(p, float) - pos
    z = float(v @ fwd)
    if z <= 1e-4:
        return None
    tan_half = math.tan(fov * 0.5)
    sx = (float(v @ right) / (z * tan_half * aspect) * 0.5 + 0.5) * w
    sy = (0.5 - float(v @ up) / (z * tan_half) * 0.5) * h
    return float(sx), float(sy), z


def _cam_basis(cam_pos, target):
    return _basis(cam_pos, target)


def contact_shadow(b, x: float, z: float, y: float, radius: float = 0.55,
                   strength: float = 1.0, cam_pos=None, target=None) -> None:
    """Soft dark patch under a character's feet, painted onto the plate.

    The plate's ground is a photograph, so there is no geometry for a shadow to
    fall on: without a contact patch the figure reads as a cut-out hovering
    over a picture. The quad lies flat on the floor, its long axis turned
    toward the lens, and is shaded with the shadow tile's alpha.
    """
    if cam_pos is None:
        cam_pos = (0.0, 1.5, 4.0)
    tx, tz = float(cam_pos[0]) - x, float(cam_pos[2]) - z
    n = math.hypot(tx, tz) or 1.0
    tx, tz = tx / n, tz / n            # ground direction toward the camera
    rx, rz = tz, -tx                   # its perpendicular
    ax, az = radius, radius * 0.55
    y0 = float(y) + 0.006
    c = np.array([x, y0, z])
    q = [c - np.array([rx * ax, 0.0, rz * ax]) - np.array([tx * az, 0.0, tz * az]),
         c - np.array([rx * ax, 0.0, rz * ax]) + np.array([tx * az, 0.0, tz * az]),
         c + np.array([rx * ax, 0.0, rz * ax]) + np.array([tx * az, 0.0, tz * az]),
         c + np.array([rx * ax, 0.0, rz * ax]) - np.array([tx * az, 0.0, tz * az])]
    u0, u1 = PLATES["shadow"]
    b.mat = MAT_PLATE
    b.tri(q[0], q[1], q[2], (1.0, 1.0, 1.0), uvs=[(u0, 1.0), (u0, 0.0), (u1, 0.0)])
    b.tri(q[0], q[2], q[3], (1.0, 1.0, 1.0), uvs=[(u0, 1.0), (u1, 0.0), (u1, 1.0)])


def glow_sprite(b, pos, radius: float, cam_pos, target, strength: float = 1.0) -> None:
    """Billboarded additive sprite: the bloom of the fire, ember haze."""
    p0, fwd, right, up = _basis(cam_pos, target)
    at = np.asarray(pos, float)
    bl = at - right * radius - up * radius
    br = at + right * radius - up * radius
    tr = at + right * radius + up * radius
    tl = at - right * radius + up * radius
    u0, u1 = PLATES["glow"]
    b.mat = MAT_ADD
    b.quad(bl, br, tr, tl, (strength, strength, strength),
           uvs=[(u0, 1.0), (u1, 1.0), (u1, 0.0), (u0, 0.0)])
