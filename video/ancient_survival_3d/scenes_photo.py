#!/usr/bin/env python3
"""Shots 1 + 2 of the reel, rebuilt around photoreal AI people.

The environment stays the procedural 3D world from `scenes3d.py` (terrain,
ridges, pines, grass, fire, fog, mist, the same shader and grade). The humans
are AI-generated studio plates, packed into an atlas and drawn as 3D geometry
by the rasteriser's photo-card path (`photopeople.py`), so they receive the
same sun, moon, fire light, shadows, fog and mist as everything else.

    shot_night  0.0 - 5.0 s   hunter standing watch in the moonlight, camera
                              creeping in, mist rolling, fireflies, breath
    shot_fire   5.0 - 10.0 s  the fire is lit: woman + elder warm their hands
                              at a real fire whose point light flickers over
                              them; slow orbit, sparks

Both shots are built to be read: who is there, what they are doing, and why.
"""

from __future__ import annotations

import math
import random

import numpy as np

import photopeople as PP
from mesh3d import (Builder, MAT_STONE, MAT_WOOD, MAT_LEAF, MAT_GROUND)
from scenes3d import (add_terrain, add_mountains, add_treeline, add_tree,
                      height as height_at,
                      add_bush, add_rock, add_fern, add_grass_tufts, add_fire,
                      add_log, add_basket, add_berries, height, ground_colour)


# --------------------------------------------------------------------- props
def _fireflies(b: Builder, t: float, centre, count: int = 16, radius: float = 3.4,
               seed: int = 3) -> None:
    """Slow drifting points of light: the night has to feel alive."""
    cx, cy, cz = centre
    rng = random.Random(seed)
    for i in range(count):
        a0 = rng.random() * math.tau
        r0 = 0.7 + rng.random() * radius
        hh = 0.35 + rng.random() * 1.5
        spd = 0.20 + rng.random() * 0.45
        a = a0 + t * spd
        x = cx + math.cos(a) * r0
        z = cz + math.sin(a * 0.8 + i) * r0 * 0.6
        y = cy + hh + 0.10 * math.sin(t * 1.7 + i * 2.1)
        phase = (t * 0.55 + i * 0.31) % 1.0
        glow = max(0.0, math.sin(math.pi * phase)) ** 2
        if glow < 0.05:
            continue
        b.mat = 0.0
        b.sphere((x, y, z), 0.016 + 0.006 * glow, (0.65, 0.95, 0.35), rings=4, seg=6,
                 emission=(0.55 * glow, 0.95 * glow, 0.30 * glow))


def _breath(b: Builder, mouth, t: float, yaw: float, period: float = 3.4,
            phase: float = 0.0) -> None:
    """A pulse of vapour from the mouth on every exhale: small and faint, so
    it reads as cold air rather than a white ball on the face."""
    k = ((t + phase) % period) / period
    if k > 0.30:
        return
    u = k / 0.30
    fade = (1.0 - u) ** 1.6
    fwd = np.array([math.sin(yaw), 0.0, math.cos(yaw)])
    side = np.array([fwd[2], 0.0, -fwd[0]])
    b.mat = 0.0
    for i in range(6):
        j = u - 0.055 * i
        if j <= 0.0:
            continue
        puff = 0.006 + 0.022 * j
        off = (fwd * (0.095 + 0.20 * j)
               + side * (0.016 * math.sin(i * 2.1 + t))
               - np.array([0.0, 0.055 + 0.11 * j, 0.0]))
        e = 0.013 * fade * (1.0 - 0.12 * i)
        b.sphere(tuple(np.asarray(mouth, float) + off), puff,
                 (0.62, 0.66, 0.74), rings=4, seg=7, scale=(1.0, 0.75, 1.0),
                 emission=(e * 0.85, e * 0.92, e))


def _torch(b: Builder, pos, t: float, scale: float = 1.0) -> None:
    """A burning brand: handle, wrap, and a small lofted flame."""
    x, y, z = pos
    b.mat = MAT_WOOD
    b.capsule((x, y, z), (x, y + 0.52 * scale, z), 0.017 * scale, 0.021 * scale,
              (0.30, 0.20, 0.12), rings=4, seg=8)
    b.mat = MAT_LEAF
    b.capsule((x, y + 0.44 * scale, z), (x, y + 0.53 * scale, z),
              0.030 * scale, 0.026 * scale, (0.20, 0.13, 0.07), rings=3, seg=8)
    b.mat = 0.0
    for i in range(4):
        ph = t * (7.0 + i * 0.9) + i * 1.7
        h = (0.10 + 0.035 * math.sin(ph)) * scale
        w = (0.030 + 0.010 * math.sin(ph * 1.4)) * scale
        b.cone((x + (i - 1.5) * 0.010 * scale, y + 0.52 * scale, z),
               w, h, (1.0, 0.68, 0.30), seg=6,
               emission=(0.55, 0.26, 0.06), lean=(0.01 * math.sin(ph), 0.0))


def _lean_to(b: Builder, pos, width: float, depth: float, yaw: float = 0.0,
             height: float = 1.25) -> None:
    """A hide shelter: two forked uprights, a ridge pole and a draped sheet.

    This is the visual shorthand for "camp" - it reads instantly in silhouette
    even when it is softly out of focus behind the subject.
    """
    x, z = pos
    y = height_at(x, z)
    fwd = np.array([math.sin(yaw), 0.0, math.cos(yaw)])
    side = np.array([fwd[2], 0.0, -fwd[0]])
    base = np.array([x, y, z])
    b.mat = MAT_WOOD
    for sgn in (-1, 1):
        foot = base + side * (sgn * width * 0.5) - fwd * depth * 0.45
        top = foot + np.array([0.0, height, 0.0]) + fwd * depth * 0.30
        b.capsule(foot - np.array([0.0, 0.04, 0.0]), top, 0.030, 0.024,
                  (0.28, 0.20, 0.12), rings=4, seg=8)
    ridge_a = base + side * (width * 0.5) + np.array([0.0, height, 0.0]) - fwd * depth * 0.15
    ridge_b = base - side * (width * 0.5) + np.array([0.0, height, 0.0]) - fwd * depth * 0.15
    b.capsule(ridge_a + fwd * 0.02, ridge_b + fwd * 0.02, 0.026, 0.026,
              (0.30, 0.22, 0.13), rings=4, seg=8)
    # the hide: two quads from the ridge down to the ground, front and back
    b.mat = 2.0
    ground = lambda p: np.array([p[0], height_at(p[0], p[2]) - 0.02, p[2]])
    for sgn in (-1, 1):
        top_l = ridge_a + fwd * (sgn * 0.01) - side * 0.02
        top_r = ridge_b + fwd * (sgn * 0.01) + side * 0.02
        bot_l = ground(top_l + fwd * depth * 0.95)
        bot_r = ground(top_r + fwd * depth * 0.95)
        if sgn > 0:
            b.quad(tuple(bot_l), tuple(bot_r), tuple(top_r), tuple(top_l),
                   (0.34, 0.26, 0.17))
        else:
            b.quad(tuple(top_l), tuple(top_r), tuple(bot_r), tuple(bot_l),
                   (0.28, 0.21, 0.14))


def _sleeping_roll(b: Builder, pos, yaw: float) -> None:
    """A bedroll of hides, so the camp reads as lived in."""
    x, y, z = pos
    b.mat = 2.0
    b.capsule((x - 0.52, y + 0.085, z), (x + 0.52, y + 0.085, z), 0.095, 0.088,
              (0.115, 0.088, 0.062), rings=6, seg=14)
    b.capsule((x - 0.56, y + 0.135, z + 0.02), (x + 0.54, y + 0.135, z + 0.02),
              0.070, 0.062, (0.092, 0.070, 0.048), rings=5, seg=12)


# ---------------------------------------------------------------------- shots
def shot_night(t: float, p: float) -> tuple[list, dict]:
    """Moonlit pass: the hunter stands watch while the camp sleeps behind him."""
    b = Builder()
    add_terrain(b, 120, 40, lambda x, z, y: (0.16 + 0.035 * y, 0.175 + 0.035 * y,
                                             0.16 + 0.03 * y))
    add_mountains(b, 54, 14)
    add_mountains(b, 40, 11, layer=1)
    add_treeline(b, 26, 34, 0.95)
    for i in range(9):
        a = -1.15 + i * 0.29
        d = 12.5 + 3.2 * math.sin(i * 1.7)
        add_tree(b, (math.cos(a) * d, height(math.cos(a) * d, math.sin(a) * d),
                     -abs(math.sin(a)) * d - 2.2),
                 0.95 + 0.25 * math.cos(i), "pine" if i % 3 else "oak")
    for i, (rx, rz, rs) in enumerate(((-3.9, 2.9, 0.42), (-3.2, 3.5, 0.26),
                                      (3.6, 3.1, 0.38), (4.2, 2.2, 0.24),
                                      (-4.8, 1.4, 0.30), (5.0, 0.6, 0.28),
                                      (3.1, 4.4, 0.22))):
        add_rock(b, (rx, height(rx, rz), rz), rs, seed=40 + i)
    for i in range(4):
        x = -3.2 + i * 2.1
        add_bush(b, (x, height(x, -5.0), -5.0), 0.85, seed=70 + i)

    # camera first: the hunter's facing is derived from it so the card stays
    # face-on (a photo card collapses to a sliver when turned sideways)
    e = p * p * (3 - 2 * p)
    hx, hz = 0.72, 0.0
    hy = height(hx, hz)
    cam_pos = (1.55 - 0.16 * e, hy + 1.22 - 0.05 * e, 3.55 - 0.45 * e)
    aim = (-0.30, hy + 0.98, -0.55)
    sway = math.sin(t * 0.9) * 0.045
    breathe = 1.0 + 0.006 * math.sin(t * 1.7)
    fyaw = PP.yaw_for((hx, hy, hz), cam_pos, aim=(-1.06, 0, -1.35), max_dev=0.22) + sway
    head, feet = PP.add_person(b, "hunter_stand", (hx, hy, hz), yaw=fyaw,
                               height=1.76 * breathe, gain=0.52)
    # (no breath vapour here: at this framing it reads as a blemish, not air)
    # the spear is planted on his far side so it never cuts across his face
    fwd = np.array([math.sin(fyaw), 0.0, math.cos(fyaw)])
    side = np.array([fwd[2], 0.0, -fwd[0]])
    spear_base = np.array([hx, 0.0, hz]) - side * 0.42 - fwd * 0.10
    sx, sz = float(spear_base[0]), float(spear_base[2])
    b.mat = MAT_WOOD
    b.capsule((sx, height(sx, sz) - 0.02, sz), (sx + 0.02, hy + 1.90, sz + 0.03),
              0.015, 0.019, (0.30, 0.22, 0.14), rings=5, seg=8)
    b.mat = MAT_STONE
    b.cone((sx + 0.02, hy + 1.90, sz + 0.03), 0.040, 0.18, (0.38, 0.37, 0.35), seg=7)

    # the camp he is guarding, six metres behind him and softly out of focus:
    # a live fire (its own warm light rims his back), two sleepers, a bedroll,
    # baskets. This is the "why" of the shot: someone keeps watch.
    cfx, cfz = -0.60, -2.35
    cfy = height(cfx, cfz)
    b.mat = MAT_WOOD
    for i in range(3):
        a = 0.7 + i * 1.9
        lx = cfx + math.cos(a) * 0.46
        lz = cfz + math.sin(a) * 0.46
        b.capsule((lx - math.cos(a) * 0.30, height(lx, lz) + 0.07, lz - math.sin(a) * 0.30),
                  (lx + math.cos(a) * 0.30, height(lx, lz) + 0.09, lz + math.sin(a) * 0.30),
                  0.055, 0.048, (0.16, 0.10, 0.055), rings=4, seg=7)
    add_fire(b, (cfx, cfy, cfz), t, 0.95)
    _sleeping_roll(b, (0.10, height(0.10, -1.55), -1.55), 0.4)
    # someone else is awake at the fire: the reason he is standing watch
    kx, kz = -1.30, -1.55
    kyaw = PP.yaw_for((kx, 0, kz), cam_pos, aim=(cfx, 0, cfz), max_dev=0.42)
    PP.add_person(b, "woman_warm", (kx, height(kx, kz), kz), yaw=kyaw, gain=0.58)
    add_basket(b, (cfx - 0.86, height(cfx - 0.86, cfz + 0.30), cfz + 0.30), 0.95)
    add_berries(b, (cfx - 1.25, height(cfx - 1.25, cfz + 0.52), cfz + 0.52), 10, seed=12)

    _fireflies(b, t, (-0.4, hy + 0.05, -1.9), 10, 1.7, seed=7)
    add_grass_tufts(b, (0.0, 0.0, 1.4), 30, 5.0, seed=13)
    # a few tufts right in front of the lens for depth, kept out of the legs
    for gx, gz, n_, sd in ((1.55, 2.30, 12, 61), (-0.55, 2.55, 10, 62),
                           (2.25, 1.30, 9, 63)):
        add_grass_tufts(b, (gx, 0.0, gz), n_, 0.75, seed=sd)
    add_grass_tufts(b, (-2.2, 0.0, -1.4), 26, 3.6, seed=29)

    cam = (cam_pos, aim)
    env = dict(sun=(-0.42, 0.44, 0.62), sun_colour=(0.46, 0.52, 0.72),
               ambient=(0.24, 0.27, 0.38), ground=(0.09, 0.10, 0.13),
               fog=(0.10, 0.12, 0.19), fog_density=0.0011, exposure=1.02,
               night=1, moon=(-0.30, 0.46, 0.038), shadow=0.55,
               light=(cfx, cfy + 0.55, cfz),
               light_colour=(1.0, 0.50, 0.19), light_range=6.2,
               light2=(cfx, cfy + 1.20, cfz),
               light2_colour=(0.42, 0.20, 0.07), light2_range=3.6,
               sky=((0.055, 0.070, 0.120), (0.010, 0.018, 0.055)),
               milky=1.05, cloud=0.0, ao=0.66, bloom=0.62,
               dof_focus=3.6 - 0.6 * e, dof=0.50,
               mist=(0.30, 0.36, 0.52), mist_amount=0.34, mist_height=1.10,
               fov=0.92)
    return [b.arrays()], dict(cam=cam, env=env)


def shot_fire(t: float, p: float) -> tuple[list, dict]:
    """Hands to the flames: the fire is lit and the camp comes alive."""
    b = Builder()
    add_terrain(b, 120, 40, lambda x, z, y: (0.235 + 0.045 * y, 0.205 + 0.042 * y,
                                             0.165 + 0.030 * y))
    add_mountains(b, 56, 13)
    add_mountains(b, 40, 11, layer=1)
    add_treeline(b, 24, 30, 0.85)
    for i in range(8):
        a = 2 * math.pi * i / 8 + 0.55
        d = 15.5 + 3.0 * math.cos(i * 1.3)
        add_tree(b, (math.cos(a) * d, height(math.cos(a) * d, math.sin(a) * d),
                     math.sin(a) * d), 0.8 + 0.22 * math.cos(i * 2.1),
                 "oak" if i % 3 == 0 else "pine")

    fx, fz = 0.0, 0.0
    fy = height(fx, fz)
    add_log(b, (-1.85, height(-1.85, 0.75), 0.75), 0.35, 1.9)
    add_log(b, (1.70, height(1.70, -0.55), -0.55), -0.55, 1.7)
    add_fire(b, (fx, fy, 0.42), t, 1.02)

    # camera path first (slow orbit), so both cards can be turned to stay
    # face-on to the lens while still leaning toward the fire
    ang = -0.20 + 0.26 * p
    rad = 5.65 - 0.32 * p
    cam_pos = (math.sin(ang) * rad + 0.05, fy + 1.46 - 0.04 * p, math.cos(ang) * rad)
    aim = (0.0, fy + 0.84, 0.10)

    # both figures stand a step back from the fire, flanking it, so the 9:16
    # frame holds the full bodies plus the flames between them
    wx, wz = -0.62, 0.92
    wy = PP.yaw_for((wx, 0, wz), cam_pos, aim=(fx, 0, fz), max_dev=0.34)
    PP.add_person(b, "woman_stand", (wx, height(wx, wz), wz), yaw=wy, gain=0.62)
    PP.add_card_shadow(b, "woman_stand", (wx, height(wx, wz), wz), wy, strength=0.5)

    ex, ez = 0.66, 1.00
    ey = PP.yaw_for((ex, 0, ez), cam_pos, aim=(fx, 0, fz), max_dev=0.34)
    PP.add_person(b, "elder_warm", (ex, height(ex, ez), ez), yaw=ey,
                  height=1.66 + 0.008 * math.sin(t * 1.3), gain=0.62)
    PP.add_card_shadow(b, "elder_warm", (ex, height(ex, ez), ez), ey, strength=0.5)

    # a rack of tools behind them, and a basket, so the camp is a place
    b.mat = MAT_WOOD
    for i, (ax, az) in enumerate(((-2.25, -0.55), (-2.10, -0.75))):
        b.capsule((ax, height(ax, az), az), (ax + 0.05, height(ax, az) + 1.05, az),
                  0.018, 0.020, (0.30, 0.21, 0.13), rings=4, seg=7)
    b.mat = MAT_STONE
    b.sphere((-2.18, height(-2.18, -0.65) + 0.72, -0.65), 0.10, (0.34, 0.32, 0.29),
             rings=6, seg=10, scale=(1.5, 0.7, 0.5))
    add_basket(b, (1.95, height(1.95, 1.55), 1.55), 1.0)
    add_berries(b, (1.62, height(1.62, 1.70), 1.70), 12, seed=5)
    _sleeping_roll(b, (-0.55, height(-0.55, -2.55), -2.55), 0.4)

    add_grass_tufts(b, (0.0, 0.0, 1.6), 52, 6.2, seed=17)
    add_grass_tufts(b, (0.0, 0.0, -2.2), 24, 4.0, seed=31)
    _fireflies(b, t, (0.0, fy - 0.35, -2.6), 6, 2.2, seed=11)

    cam = (cam_pos, aim)
    flick = 0.86 + 0.14 * math.sin(t * 9.1) + 0.06 * math.sin(t * 23.0 + 1.2)
    env = dict(sun=(-0.28, 0.58, 0.52), sun_colour=(0.26, 0.30, 0.46),
               ambient=(0.26, 0.20, 0.17), ground=(0.10, 0.08, 0.07),
               fog=(0.12, 0.12, 0.20), fog_density=0.0016, exposure=0.92,
               night=1, moon=(0.34, 0.50, 0.034), shadow=0.55,
               light=(fx, fy + 0.52, 0.45),
               light_colour=(1.0 * flick, 0.44 * flick, 0.13 * flick),
               light_range=6.4,
               light2=(fx, fy + 1.15, 0.45),
               light2_colour=(0.55 * flick, 0.24 * flick, 0.07 * flick),
               light2_range=3.4,
               sky=((0.085, 0.085, 0.140), (0.014, 0.022, 0.062)),
               milky=0.95, cloud=0.0, ao=0.62, bloom=0.60,
               dof_focus=rad - 0.4, dof=0.55,
               mist=(0.22, 0.20, 0.26), mist_amount=0.16, mist_height=0.8,
               fov=0.80)
    return [b.arrays()], dict(cam=cam, env=env)


SHOTS10 = [
    (0.0, 5.0, shot_night),
    (5.0, 10.0, shot_fire),
]
