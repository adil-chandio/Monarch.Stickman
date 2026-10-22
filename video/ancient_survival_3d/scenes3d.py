"""3D scenes for the Ancient Survival reel.

Every object in these shots is geometry generated at render time: terrain,
rocks, trees, the fire, and the rigged cast. Nothing is a picture.
"""

from __future__ import annotations

import math
import random

import numpy as np

from mesh3d import (Builder, Rig, make_transform, pose_crouch, pose_idle, pose_knap,
                    pose_knap_strike,
                    pose_pick, pose_point, pose_sit_tend, pose_sit_warm, pose_walk,
                    pose_warm, MAT_SKIN, MAT_CLOTH, MAT_HAIR, MAT_STONE, MAT_LEAF,
                    MAT_EYE, MAT_WOOD, MAT_GROUND)

RIG = Rig()
S_RIG = RIG
RNG = random.Random(7)


def blink_at(t: float, offset: float = 0.0) -> float:
    """Short lid dips every few seconds; returns 0 (open) .. 1 (closed)."""
    phase = (t + offset) % 4.6
    if phase > 0.17:
        return 0.0
    return math.sin(math.pi * phase / 0.17)


def apply_env(r, env) -> None:
    """Push an env dict at the renderer, including the v2 lighting channels."""
    r.environment(env["sun"], env["sun_colour"], env["ambient"], env["ground"],
                  env["fog"], env["fog_density"], env["exposure"], env["night"],
                  env["moon"], env["shadow"],
                  light=env.get("light"), light_colour=env.get("light_colour", (0, 0, 0)),
                  light_range=env.get("light_range", 4.0),
                  light2=env.get("light2"), light2_colour=env.get("light2_colour", (0, 0, 0)),
                  light2_range=env.get("light2_range", 3.0),
                  dof_focus=env.get("dof_focus", 0.0), dof=env.get("dof", 0.0),
                  mist=env.get("mist"), mist_amount=env.get("mist_amount", 0.0),
                  mist_height=env.get("mist_height", 0.9),
                  sky=env.get("sky"), cloud=env.get("cloud", 0.0),
                  milky=env.get("milky", 0.0), ao=env.get("ao", 0.62),
                  bloom=env.get("bloom", 0.5))


# ------------------------------------------------------------------ terrain
def height(x: float, z: float) -> float:
    return (0.55 * math.sin(x * 0.055 + 0.4) * math.cos(z * 0.045)
            + 0.35 * math.sin((x + z) * 0.09)
            + 0.18 * math.cos(x * 0.21 - z * 0.13))


def ground_colour(x: float, z: float, y: float):
    """Sand, dry grass and mossy patches broken up by three noise bands."""
    patch = 0.5 + 0.5 * math.sin(x * 0.31) * math.cos(z * 0.27)
    fine = 0.5 + 0.5 * math.sin(x * 1.7 + 0.9) * math.cos(z * 1.9 - 0.4)
    moss = max(0.0, min(1.0, 0.55 * patch + 0.45 * fine - 0.10))
    dry = max(0.0, min(1.0, 0.38 + 0.30 * patch + 0.10 * y))
    r = 0.27 + 0.17 * dry - 0.10 * moss
    g = 0.23 + 0.13 * dry + 0.02 * moss
    bl = 0.12 + 0.05 * dry - 0.04 * moss
    return (r, g, bl)


def add_terrain(b: Builder, size: float = 120.0, cells: int = 44,
                colour=ground_colour) -> None:
    b.ground(size, cells, height, colour)


def add_rock(b: Builder, pos, size: float, colour=(0.34, 0.31, 0.27), seed: int = 0):
    """A weathered boulder: one main mass plus chipped shoulders and gravel."""
    rng = random.Random(seed)
    prev, b.mat = b.mat, MAT_STONE
    x, y, z = pos
    base = tuple(c * (0.92 + 0.16 * rng.random()) for c in colour)
    b.sphere((x, y + size * 0.38, z), size, base, rings=8, seg=11,
             scale=(1.0 + rng.random() * 0.45, 0.62 + rng.random() * 0.3,
                    0.82 + rng.random() * 0.45), squash=0.24)
    for i in range(3):
        a = rng.random() * 2 * math.pi
        d = size * (0.45 + 0.35 * rng.random())
        s2 = size * (0.30 + 0.28 * rng.random())
        shade = tuple(c * (0.86 + 0.22 * rng.random()) for c in colour)
        b.sphere((x + math.cos(a) * d, y + s2 * 0.42, z + math.sin(a) * d), s2, shade,
                 rings=6, seg=9, scale=(1.0 + 0.3 * rng.random(), 0.70, 0.9),
                 squash=0.26)
    for i in range(3):
        a = rng.random() * 2 * math.pi
        d = size * (0.9 + 0.6 * rng.random())
        s3 = size * (0.09 + 0.09 * rng.random())
        b.sphere((x + math.cos(a) * d, y + s3 * 0.5, z + math.sin(a) * d), s3,
                 tuple(c * 0.9 for c in colour), rings=5, seg=7, squash=0.3)
    b.mat = prev


def add_tree(b: Builder, pos, scale: float = 1.0, kind: str = "pine"):
    """Pines get stacked skirted tiers, oaks get branches under a leaf dome."""
    rng = random.Random(int(abs(pos[0] * 91 + pos[2] * 37)) + 5)
    x, y, z = pos
    bark = (0.25 + 0.05 * rng.random(), 0.165, 0.098)
    prev, b.mat = b.mat, MAT_WOOD
    if kind == "pine":
        b.capsule((x, y - 0.15, z), (x, y + 2.5 * scale, z), 0.17 * scale, 0.085 * scale,
                  bark, rings=4, seg=7)
        b.mat = MAT_LEAF
        for i in range(5):
            yy = y + (1.18 + i * 0.78) * scale
            r = (1.24 - i * 0.20) * scale * (0.90 + 0.20 * rng.random())
            h = (1.45 - i * 0.10) * scale
            g = (0.055 + 0.020 * i, 0.135 + 0.026 * i, 0.070 + 0.014 * i)
            b.cone((x, yy, z), r, h, g, seg=26)
            # a second offset cone gives the tier a ragged silhouette
            b.cone((x + 0.18 * scale, yy + 0.10 * scale, z - 0.12 * scale), r * 0.72,
                   h * 0.86, tuple(c * 1.10 for c in g), seg=18)
    else:
        b.capsule((x, y - 0.12, z), (x, y + 1.75 * scale, z), 0.21 * scale, 0.13 * scale,
                  bark, rings=4, seg=8)
        for i in range(4):
            a = i * 1.62 + rng.random() * 0.4
            b.mat = MAT_WOOD
            b.capsule((x, y + (1.15 + 0.22 * i) * scale, z),
                      (x + math.cos(a) * 0.75 * scale, y + (1.85 + 0.2 * i) * scale,
                       z + math.sin(a) * 0.75 * scale), 0.075 * scale, 0.035 * scale,
                      bark, rings=3, seg=6)
        b.mat = MAT_LEAF
        for i in range(7):
            a = i * 0.95 + rng.random() * 0.5
            d = (0.42 + 0.42 * rng.random()) * scale
            yy = y + (2.05 + 0.30 * rng.random()) * scale
            rr = (0.62 + 0.30 * rng.random()) * scale
            g = (0.15 + 0.08 * rng.random(), 0.24 + 0.07 * rng.random(), 0.10)
            b.sphere((x + math.cos(a) * d, yy, z + math.sin(a) * d), rr, g,
                     rings=9, seg=15, scale=(1.0, 0.78, 1.0), squash=0.2)


def add_bush(b: Builder, pos, scale: float = 1.0, seed: int = 0):
    rng = random.Random(seed)
    x, y, z = pos
    for i in range(5):
        a = rng.random() * 2 * math.pi
        d = 0.36 * scale * rng.random()
        b.sphere((x + math.cos(a) * d, y + (0.20 + 0.16 * rng.random()) * scale,
                  z + math.sin(a) * d), (0.26 + 0.14 * rng.random()) * scale,
                 (0.15 + 0.05 * rng.random(), 0.23 + 0.05 * rng.random(), 0.10),
                 rings=5, seg=8, scale=(1.0, 0.75, 1.0), squash=0.24)


def add_fern(b: Builder, pos, scale: float = 1.0, seed: int = 0):
    rng = random.Random(seed)
    x, y, z = pos
    for i in range(6):
        a = i * 1.05 + rng.random() * 0.3
        lean = (math.cos(a) * 0.30 * scale, math.sin(a) * 0.30 * scale)
        b.cone((x, y, z), 0.055 * scale, (0.34 + 0.16 * rng.random()) * scale,
               (0.13, 0.22, 0.09), seg=5, lean=lean)


def _peak(b: Builder, x: float, z: float, r: float, h: float, col, seed: int,
          snow: float = 0.55) -> None:
    """One mountain: a noisy cone surface, darker rock at the base, snow up top."""
    rng = random.Random(seed)
    seg, rings = 34, 9
    ph = [rng.random() * 6.283 for _ in range(5)]
    prev, b.mat = b.mat, MAT_STONE
    cols = []
    for i in range(rings + 1):
        t = i / rings
        row = []
        for j in range(seg):
            a = 2 * math.pi * j / seg
            wob = (1.0 + 0.16 * math.sin(3 * a + ph[0] + t * 2.0)
                   + 0.10 * math.sin(7 * a + ph[1] - t * 3.0)
                   + 0.06 * math.sin(13 * a + ph[2] + t * 5.0))
            rr = r * (1.0 - t) ** 0.92 * wob
            yy = h * t ** 1.15 + 0.55 * math.sin(5 * a + ph[3]) * (1.0 - t) * (t > 0.02)
            row.append(np.array([x + math.cos(a) * rr, -1.6 + yy, z + math.sin(a) * rr]))
        cols.append(row)
    for i in range(rings):
        t0, t1 = i / rings, (i + 1) / rings
        for j in range(seg):
            j2 = (j + 1) % seg
            c0 = np.array(col, float)
            # snow on the upper slopes, rock below, a touch of haze at the base
            k0 = 0.55 + 0.65 * t0
            s0 = max(0.0, (t0 - snow) / (1.0 - snow))
            k1 = 0.55 + 0.65 * t1
            s1 = max(0.0, (t1 - snow) / (1.0 - snow))
            ca = c0 * k0
            cb = c0 * k1
            ca = ca * (1 - s0) + np.array([0.80, 0.84, 0.92]) * s0 * 0.9
            cb = cb * (1 - s1) + np.array([0.80, 0.84, 0.92]) * s1 * 0.9
            cm = (ca + cb) * 0.5
            b.quad(cols[i][j], cols[i][j2], cols[i + 1][j2], cols[i + 1][j],
                   tuple(float(v) for v in cm))
    b.mat = prev


def add_mountains(b: Builder, radius: float, count: int = 14, layer: int = 0) -> None:
    """Ridge lines at several distances; fog and colour carry the aerial perspective."""
    palettes = ((0.085, 0.100, 0.145), (0.105, 0.122, 0.168), (0.130, 0.145, 0.190))
    col = palettes[min(layer, 2)]
    for i in range(count):
        a = 2 * math.pi * i / count + 0.3 + layer * 0.21
        d = radius * 2.1 * (0.82 + 0.20 * math.sin(i * 2.3 + layer))
        x, z = math.cos(a) * d, math.sin(a) * d
        h = (10 + 6 * math.sin(i * 1.7 + layer)) * (1.0 - 0.16 * layer) * 0.92
        r = (8.5 + 3.5 * math.cos(i * 2.1)) * (1.0 - 0.10 * layer) * 1.35
        _peak(b, x, z, r, h, col, seed=i * 17 + layer * 5, snow=0.52 + 0.08 * layer)
        _peak(b, x + r * 0.55, z + r * 0.35, r * 0.62, h * 0.66, col,
              seed=i * 29 + layer * 11 + 3, snow=0.58)


def add_treeline(b: Builder, radius: float, count: int = 40, height_scale: float = 1.0):
    """A dark silhouette hedge of distant conifers closing the horizon."""
    for i in range(count):
        a = 2 * math.pi * i / count + 0.11
        d = radius * (0.9 + 0.14 * math.sin(i * 3.1))
        x, z = math.cos(a) * d, math.sin(a) * d
        h = (2.4 + 1.5 * math.sin(i * 2.7)) * height_scale
        b.cone((x, -0.3, z), 0.80 * height_scale, h, (0.070, 0.098, 0.080), seg=14)


def add_grass_tufts(b: Builder, centre, count: int, spread: float, seed: int = 0):
    rng = random.Random(seed)
    for i in range(count):
        a = rng.random() * 2 * math.pi
        d = spread * (0.18 + rng.random() ** 0.6)
        x, z = centre[0] + math.cos(a) * d, centre[2] + math.sin(a) * d
        y = height(x, z)
        h = 0.20 + rng.random() * 0.34
        col = (0.22 + 0.10 * rng.random(), 0.30 + 0.10 * rng.random(), 0.10)
        blades = 5 + int(rng.random() * 3)
        for k in range(blades):
            ang = a + k * 1.9 + rng.random() * 0.6
            lean = (math.cos(ang) * 0.085, math.sin(ang) * 0.085)
            b.cone((x, y - 0.02, z), 0.020, h * (0.7 + 0.5 * rng.random()), col,
                   seg=4, lean=lean)
        if rng.random() < 0.22:
            b.sphere((x, y + h * 0.95, z), 0.028, (0.42, 0.38, 0.16), rings=4, seg=5)


# --------------------------------------------------------------------- fire
def add_fire(b: Builder, pos, t: float, scale: float = 1.0, fuel: float = 1.0):
    x, y, z = pos
    for i in range(4):
        a = i * 1.6
        b.capsule((x - math.cos(a) * 0.42 * scale, y + 0.05, z - math.sin(a) * 0.42 * scale),
                  (x + math.cos(a) * 0.42 * scale, y + 0.08, z + math.sin(a) * 0.42 * scale),
                  0.085 * scale, 0.075 * scale, (0.20, 0.11, 0.06), rings=3, seg=6)
    # stone ring
    for i in range(9):
        a = 2 * math.pi * i / 9
        b.sphere((x + math.cos(a) * 0.72 * scale, y + 0.04, z + math.sin(a) * 0.72 * scale),
                 0.13 * scale, (0.33, 0.31, 0.29), rings=5, seg=7, scale=(1.1, 0.7, 1.0),
                 squash=0.2)
    # ---- layered flame tongues: lofted, curved, tapering blades ----------
    def tongue(cx, cz, h, w, ph, col, emis, base_y, seg=7, rings=6, spin=0.0):
        pts = []
        for k in range(rings + 1):
            t = k / rings
            grow = (1.0 - t) ** 0.62
            rr = w * grow * (0.92 + 0.16 * math.sin(ph * 2.1 + t * 4.0))
            yy = base_y + h * t
            sway = (0.05 + 0.16 * t * t) * math.sin(ph * 1.7 + t * 3.4 + spin)
            row = []
            for j in range(seg):
                a = 2 * math.pi * j / seg + spin
                row.append((cx + sway + rr * math.cos(a), yy,
                            cz + rr * 0.85 * math.sin(a)))
            pts.append(row)
        for k in range(rings):
            for j in range(seg):
                j2 = (j + 1) % seg
                a0, a1 = pts[k][j], pts[k][j2]
                b0, b1 = pts[k + 1][j], pts[k + 1][j2]
                b.quad(a0, a1, b1, b0, col, emission=emis,
                       uvs=[(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.1)])
        tip = (cx + (0.05 + 0.16) * math.sin(ph * 1.7 + 3.4 + spin),
               base_y + h * 1.24, cz)
        for j in range(seg):
            j2 = (j + 1) % seg
            b.tri(pts[rings][j], pts[rings][j2], tip, col, emission=emis,
                  uvs=((0.0, 0.0), (0.1, 0.0), (0.05, 0.12)))

    fy = y + 0.06
    for i in range(9):
        ph = t * (4.4 + i * 0.5) + i * 2.1
        h = (0.50 + 0.26 * math.sin(ph)) * scale * fuel
        w = (0.088 + 0.030 * math.sin(ph * 1.3)) * scale
        off = (i - 4) * 0.058 * scale
        tongue(x + off, z + ((i % 3) - 1) * 0.05 * scale, h, w, ph,
               (1.0, 0.46, 0.10), (0.26, 0.070, 0.008), fy, spin=i * 0.7)
    for i in range(6):
        ph = t * (6.1 + i * 0.6) + i * 1.3
        h = (0.30 + 0.18 * math.sin(ph)) * scale * fuel
        tongue(x + (i - 2.5) * 0.052 * scale, z + 0.01, h, 0.055 * scale, ph,
               (1.0, 0.72, 0.28), (0.42, 0.20, 0.030), fy + 0.02, spin=i * 1.1)
    for i in range(3):
        ph = t * 7.7 + i * 2.4
        h = (0.17 + 0.09 * math.sin(ph)) * scale * fuel
        tongue(x + (i - 1) * 0.035 * scale, z + 0.02, h, 0.035 * scale, ph,
               (1.0, 0.92, 0.62), (0.60, 0.40, 0.12), fy + 0.04, spin=i * 1.9)
    # coal bed: a hot glow at the base that spills onto the logs
    b.sphere((x, fy + 0.02, z), 0.26 * scale, (1.0, 0.42, 0.12), rings=6, seg=14,
             scale=(1.0, 0.14, 1.0), emission=(0.22, 0.060, 0.010))
    # sparks riding the heat column
    rng = random.Random(int(t * 14) + 3)
    for i in range(9):
        a = rng.random() * 2 * math.pi
        d = 0.10 + rng.random() * 0.40
        hh = 0.30 + rng.random() * 1.15
        b.sphere((x + math.cos(a) * d, y + hh, z + math.sin(a) * d),
                 0.010 * scale, (1.0, 0.62, 0.22), rings=3, seg=5,
                 emission=(0.90, 0.34, 0.05))


# ---------------------------------------------------------------- characters
PALETTES = {
    "man": dict(skin=(0.50, 0.315, 0.205), tunic=(0.44, 0.245, 0.105),
                hair=(0.07, 0.055, 0.045), grey=False),
    "woman": dict(skin=(0.52, 0.345, 0.235), tunic=(0.255, 0.275, 0.135),
                  hair=(0.09, 0.065, 0.045), grey=False),
    "elder": dict(skin=(0.50, 0.355, 0.250), tunic=(0.38, 0.36, 0.30),
                  hair=(0.66, 0.65, 0.63), grey=True),
}


def add_character(b: Builder, kind: str, pose, root=(0, 0, 0), yaw=0.0,
                  scale: float = 1.0, lean=(0.0, 0.0), grounded: bool = True,
                  blink: float = 0.0) -> dict:
    pal = PALETTES[kind]
    if grounded:
        # Measure the real silhouette: build once at y=0, find the lowest vertex,
        # then slide the whole rig so that point touches the terrain. This works
        # for standing, walking, kneeling, sitting and lying poses alike.
        probe_b = Builder()
        probe_w = RIG.solve(pose, root=(root[0], 0.0, root[2]), yaw=yaw,
                            scale=scale, lean=lean)
        RIG.mesh(probe_b, probe_w, skin=pal["skin"], tunic=pal["tunic"],
                 hair=pal["hair"], grey_hair=pal["grey"], kind=kind)
        v = probe_b.arrays()[0]
        lowest = float(v[:, 1].min()) if len(v) else 0.0
        target = height(root[0], root[2]) + 0.015
        # probe was solved at y=0, so the offset is absolute (no double counting)
        root = (root[0], target - lowest, root[2])
    world = RIG.solve(pose, root=root, yaw=yaw, scale=scale, lean=lean)
    RIG.mesh(b, world, skin=pal["skin"], tunic=pal["tunic"], hair=pal["hair"],
             grey_hair=pal["grey"], kind=kind, blink=blink)
    return world


def _add_shadow_blob(b: Builder, root, scale: float) -> None:
    """A flattened dark ellipse under each character grounds them on the terrain."""
    x, y, z = root
    b.sphere((x, y + 0.012, z), 0.52 * scale, (0.16, 0.13, 0.10), rings=4, seg=9,
             scale=(1.0, 0.02, 1.0))


# ---------------------------------------------------------------- props
def add_basket(b: Builder, pos, scale: float = 1.0):
    x, y, z = pos
    b.capsule((x, y, z), (x, y + 0.26 * scale, z), 0.17 * scale, 0.20 * scale,
              (0.45, 0.33, 0.16), rings=3, seg=10)
    for i in range(5):
        yy = y + 0.04 + i * 0.05
        b.capsule((x - 0.18 * scale, yy, z), (x + 0.18 * scale, yy, z),
                  0.018 * scale, 0.018 * scale, (0.30, 0.21, 0.10), rings=2, seg=4)


def add_berries(b: Builder, pos, count: int = 16, seed: int = 1):
    rng = random.Random(seed)
    x, y, z = pos
    for i in range(count):
        dx = (rng.random() - 0.5) * 0.9
        dz = (rng.random() - 0.5) * 0.9
        dy = rng.random() * 0.35
        b.sphere((x + dx, y + dy, z + dz), 0.038, (0.20, 0.09, 0.26), rings=4, seg=5)


def add_log(b: Builder, pos, yaw: float, length: float = 2.2):
    x, y, z = pos
    dx, dz = math.cos(yaw) * length / 2, math.sin(yaw) * length / 2
    b.capsule((x - dx, y + 0.18, z - dz), (x + dx, y + 0.18, z + dz), 0.22, 0.19,
              (0.35, 0.23, 0.13), rings=4, seg=9)


# ------------------------------------------------------------------- shots
def shot_night(t: float, p: float) -> tuple[list, dict]:
    """Opening: a lone figure runs through a moonlit pass, camera tracks in 3D."""
    b = Builder()
    add_terrain(b, 140, 40, lambda x, z, y: (0.16 + 0.05 * y, 0.15 + 0.05 * y, 0.13))
    add_mountains(b, 70, 16)
    add_mountains(b, 50, 13, layer=1)
    add_mountains(b, 34, 11, layer=2)
    add_treeline(b, 26, 46, 0.95)
    for i in range(30):
        a = 2 * math.pi * i / 30
        d = 22 + 9 * math.sin(i * 1.7)
        add_tree(b, (math.cos(a) * d, height(math.cos(a) * d, math.sin(a) * d),
                     math.sin(a) * d), 0.85 + 0.35 * math.sin(i * 2.1))
    for i in range(9):
        add_rock(b, (-3.4 + i * 0.9, height(-3.4 + i * 0.9, 2.4), 2.4), 0.35 + 0.2 * (i % 3),
                 (0.26, 0.24, 0.24), seed=i)
    add_rock(b, (1.9, height(1.9, -0.8), -0.8), 0.85, (0.28, 0.26, 0.25), seed=4)
    run_x = -3.2 + 4.6 * p
    add_character(b, "man", pose_walk(t * 3.1), root=(run_x, height(run_x, 0.4), 0.4),
                  yaw=math.pi * 0.52, scale=1.0, blink=blink_at(t, 0.4))
    add_grass_tufts(b, (0.0, 0, 0.0), 26, 7.0, seed=3)
    cam = ((run_x - 2.6, 1.55, -4.6), (run_x + 0.3, 1.05, 0.4))
    env = dict(sun=(-0.35, 0.72, 0.5), sun_colour=(0.70, 0.76, 1.00),
               ambient=(0.24, 0.29, 0.48), ground=(0.11, 0.11, 0.18),
               fog=(0.13, 0.16, 0.28), fog_density=0.0011, exposure=0.92,
               night=1, moon=(-0.34, 0.46, 0.045), shadow=0.55, fov=0.82,
               sky=((0.062, 0.078, 0.150), (0.012, 0.020, 0.062)),
               milky=0.95, cloud=0.0, ao=0.62, bloom=0.45,
               dof_focus=5.6, dof=0.55)
    return [b.arrays()], dict(cam=cam, env=env)


def shot_fire(t: float, p: float) -> tuple[list, dict]:
    """Campfire: three figures in 3D, firelight as emissive geometry."""
    b = Builder()
    add_terrain(b, 120, 38, lambda x, z, y: (0.24 + 0.04 * y, 0.21 + 0.04 * y, 0.17))
    add_mountains(b, 60, 14)
    add_mountains(b, 42, 12, layer=1)
    add_treeline(b, 25, 32, 0.85)
    for i in range(10):
        a = 2 * math.pi * i / 10 + 0.4
        d = 22 + 4 * math.sin(i * 1.9)
        add_tree(b, (math.cos(a) * d, height(math.cos(a) * d, math.sin(a) * d),
                     math.sin(a) * d), 0.9 + 0.25 * math.cos(i))
    fire_pos = (0.0, height(0.0, 0.0), 0.0)
    add_log(b, (-1.9, height(-1.9, 0.9), 0.9), 0.4, 2.0)
    add_log(b, (1.7, height(1.7, 1.1), 1.1), -0.5, 1.8)
    y = fire_pos[1]
    add_fire(b, (0.0, y, 0.55), t, 1.05)
    # two survivors warming their hands, one crouched feeding the flames
    for kind, pose, px, pz, sc, bl in (
        ("elder", pose_warm(t), -0.66, 0.02, 1.00, 0.0),
        ("woman", pose_warm(t + 1.7), 0.66, 0.06, 0.98, 2.1),
    ):
        yy = math.atan2(0.0 - px, 0.55 - pz)
        add_character(b, kind, pose, root=(px, height(px, pz), pz),
                      yaw=yy, scale=sc, grounded=True, blink=blink_at(t, bl + 1.3))
    add_grass_tufts(b, (0.0, 0, 0.0), 22, 6.0, seed=9)
    angle = -0.10 + 0.16 * p
    cam = ((math.sin(angle) * 4.65 + 0.26, y + 1.40, math.cos(angle) * 4.65),
           (-0.02, y + 0.74, 0.06))
    env = dict(sun=(-0.2, 0.55, 0.55), sun_colour=(0.22, 0.24, 0.40),
               ambient=(0.34, 0.22, 0.16), ground=(0.14, 0.10, 0.08),
               fog=(0.14, 0.13, 0.20), fog_density=0.0035, exposure=1.15,
               night=1, moon=(0.42, 0.52, 0.035), shadow=0.5, fov=0.78)
    return [b.arrays()], dict(cam=cam, env=env)


STRIKE_PERIOD = 0.62
STRIKE_START = 10.0


def strike_times(t: float, window: float = 0.55) -> list[float]:
    """Recent knapping impacts, newest first (used by the chip debris)."""
    out = []
    k = 0
    while True:
        ts = STRIKE_START + k * STRIKE_PERIOD
        if ts > t:
            break
        if t - ts < window:
            out.append(ts)
        k += 1
    return out


def shot_tools(t: float, p: float) -> tuple[list, dict]:
    """Stone tools: one survivor knaps a core into a hand-axe, a mate watches."""
    b = Builder()
    add_terrain(b, 90, 36, ground_colour)
    add_mountains(b, 56, 13)
    add_mountains(b, 40, 11, layer=1)
    add_mountains(b, 28, 9, layer=2)
    add_treeline(b, 22, 30, 0.7)
    for i in range(4):
        add_tree(b, (-5.2 + i * 3.1, height(-5.2 + i * 3.1, -6.4), -6.4),
                 0.72 + 0.16 * (i % 2), "pine" if i % 2 else "oak")
    for i in range(3):
        add_bush(b, (2.6 - i * 2.4, height(2.6 - i * 2.4, -4.6), -4.6), 0.9, seed=50 + i)
    for i in range(10):
        rx, rz = -3.6 + i * 0.74, -3.1
        add_rock(b, (rx, height(rx, rz), rz), 0.16 + 0.08 * (i % 2),
                 (0.30, 0.28, 0.25), seed=20 + i)
    for i in range(5):
        rx, rz = -1.7 + i * 0.80, 1.85
        add_rock(b, (rx, height(rx, rz), rz), 0.09 + 0.04 * (i % 2),
                 (0.34, 0.32, 0.29), seed=31 + i)
    # --- the knapper, kneeling behind a flat anvil stone ---------------
    kx, kz = -0.48, 0.54
    ky = height(kx, kz)
    phase = ((t - STRIKE_START) / STRIKE_PERIOD) % 1.0
    pose_a = pose_knap_strike(phase)
    world_a = add_character(b, "woman", pose_a, root=(kx, ky, kz), yaw=0.90,
                            scale=1.0, grounded=True, blink=blink_at(t, 0.9))
    # --- the working ledge: a flat-topped bedrock crag beside him ---------
    ax, az = -0.12, 0.40
    ay = height(ax, az)
    b.mat = MAT_STONE
    # rubble skirt so the crag reads as bedrock, not a pedestal
    for i in range(9):
        a = 2 * math.pi * i / 9 + 0.4
        rr = 0.30 + 0.07 * math.sin(i * 2.1)
        px, pz = ax + math.cos(a) * rr, az + math.sin(a) * rr
        b.sphere((px, height(px, pz) + 0.04, pz), 0.09 + 0.04 * math.cos(i * 1.7),
                 (0.30, 0.285, 0.265), rings=6, seg=11,
                 scale=(1.2, 0.62, 1.0), squash=0.25)
    b.sphere((ax, ay + 0.09, az), 0.265, (0.275, 0.262, 0.246), rings=9, seg=20,
             scale=(1.22, 0.86, 1.14), squash=0.30)
    b.sphere((ax, ay + 0.30, az), 0.245, (0.315, 0.298, 0.274), rings=10, seg=20,
             scale=(1.14, 0.62, 1.08), squash=0.18)
    core = np.array([ax - 0.01, ay + 0.455, az - 0.01])
    b.sphere(core, 0.105, (0.33, 0.315, 0.29), rings=10, seg=15,
             scale=(1.0, 0.78, 0.95), squash=0.22)
    b.mat = MAT_SKIN
    # hammer stone clamped in the striking fist
    wrist = world_a["wrist_r"][:3, 3]
    elbow = world_a["elbow_r"][:3, 3]
    d = wrist - elbow
    d = d / (float(np.linalg.norm(d)) + 1e-6)
    b.mat = MAT_STONE
    b.sphere(wrist + d * 0.055, 0.052, (0.34, 0.32, 0.30), rings=7, seg=11,
             scale=(1.0, 0.85, 1.0), squash=0.2)
    b.mat = MAT_SKIN
    b.capsule(wrist - d * 0.02, wrist + d * 0.04, 0.033, 0.031, (0.60, 0.43, 0.31),
              rings=4, seg=10)
    # --- chips: analytic ballistic debris from each recent strike -------
    for si, ts in enumerate(strike_times(t)):
        dt = t - ts
        rng = random.Random(int(ts * 1000))
        b.mat = MAT_STONE
        for i in range(11):
            a = rng.random() * 2 * math.pi
            sp = 0.9 + rng.random() * 2.0
            vy = 0.5 + rng.random() * 1.5
            px = core[0] + math.cos(a) * sp * dt
            pz = core[2] + math.sin(a) * sp * dt
            py = core[1] + vy * dt - 4.9 * dt * dt
            floor = height(px, pz) + 0.012
            if py < floor:
                py = floor
            b.sphere((px, py, pz), 0.011 + rng.random() * 0.014,
                     (0.36, 0.345, 0.32), rings=4, seg=7,
                     scale=(1.0, 0.55, 1.0), squash=0.3)
        # a quick spark-like glint at the point of impact
        if dt < 0.10:
            k = 1.0 - dt / 0.10
            b.sphere((core[0], core[1] + 0.03, core[2]), 0.05 * (0.4 + 0.6 * k),
                     (1.0, 0.94, 0.78), rings=5, seg=8,
                     emission=(1.1 * k, 0.85 * k, 0.50 * k))
        # a small dust puff that lingers and drifts up
        if dt < 0.45:
            k = dt / 0.45
            rng2 = random.Random(int(ts * 1000) + 7)
            for i in range(4):
                a = rng2.random() * 2 * math.pi
                rr = 0.05 + 0.16 * k + 0.05 * rng2.random()
                b.sphere((core[0] + math.cos(a) * rr,
                          core[1] + 0.03 + 0.12 * k,
                          core[2] + math.sin(a) * rr),
                         0.022 + 0.038 * k, (0.46, 0.44, 0.40), rings=4, seg=8,
                         scale=(1.0, 0.7, 1.0))
        b.mat = MAT_SKIN
    # --- the mate, spear in hand, watching the work --------------------
    pose_b = pose_idle(t + 1.2)
    pose_b.update({"chest": (0.04, 0.16, 0), "neck": (0.06, 0.18, 0),
                   "shoulder_l": (-0.22, 0, -0.30), "elbow_l": (-0.62, 0, 0)})
    world_b = add_character(b, "man", pose_b, root=(-2.15, height(-2.15, 1.30), 1.30),
                            yaw=1.96, scale=1.02, grounded=True, blink=blink_at(t, 2.6))
    # spear held in his left hand, butt on the ground
    hand = world_b["wrist_l"][:3, 3]
    butt = np.array([hand[0] + 0.10, height(hand[0] + 0.10, hand[2] + 0.05), hand[2] + 0.05])
    tip = butt + np.array([0.02, 1.78, -0.03])
    b.capsule(butt, tip, 0.023, 0.030, (0.42, 0.31, 0.19), rings=6, seg=9)
    b.cone(tip - np.array([0.0, 0.02, 0.0]), 0.05, 0.20, (0.36, 0.33, 0.30), seg=8,
           lean=(0.03, 0.0))
    # finished flakes and hand-axes on the ground
    for i in range(8):
        b.box((-0.55 + i * 0.13, height(-0.55 + i * 0.13, kz + 0.85) + 0.02, kz + 0.85),
              (0.075, 0.02, 0.12), (0.30, 0.29, 0.27), yaw=i * 0.7)
    for i, (gx, gz, gy) in enumerate(((0.10, 1.45, 0.5), (0.52, 1.30, -0.7))):
        b.sphere((gx, height(gx, gz) + 0.05, gz), 0.085, (0.33, 0.31, 0.29),
                 rings=6, seg=11, scale=(1.45, 0.5, 0.8))
    add_grass_tufts(b, (0.0, 0.0, 0.6), 26, 4.2, seed=17)
    add_grass_tufts(b, (0.2, 0.0, 2.4), 18, 3.0, seed=23)
    # --- camera: low three-quarter, easing in on the hands -------------
    target = (core[0] + 0.06, core[1] + 0.06, core[2] + 0.02)
    cam = ((0.58 - 0.12 * p, height(0.58, 3.42) + 1.62 - 0.10 * p, 3.42 - 0.26 * p),
           target)
    env = dict(sun=(0.55, 0.7, 0.45), sun_colour=(1.06, 0.90, 0.70),
               ambient=(0.26, 0.28, 0.34), ground=(0.22, 0.18, 0.13),
               fog=(0.55, 0.61, 0.70), fog_density=0.0007, exposure=0.70,
               night=0, moon=(-0.46, 0.50, 0.030), shadow=0.8, fov=0.72,
               sky=((0.72, 0.68, 0.60), (0.20, 0.38, 0.66)),
               cloud=0.55, ao=0.62, bloom=0.35, dof_focus=1.9, dof=0.45,
               mist=(0.62, 0.66, 0.72), mist_amount=0.13, mist_height=0.95)
    return [b.arrays()], dict(cam=cam, env=env)


def shot_walk(t: float, p: float) -> tuple[list, dict]:
    """Trio travels along a 3D path; camera tracks beside them."""
    b = Builder()
    add_terrain(b, 140, 42, ground_colour)
    add_mountains(b, 64, 15)
    add_mountains(b, 46, 12, layer=1)
    add_treeline(b, 27, 40, 0.9)
    for i in range(26):
        a = 2 * math.pi * i / 26
        d = 19 + 7 * math.sin(i * 1.4)
        add_tree(b, (math.cos(a) * d, height(math.cos(a) * d, math.sin(a) * d),
                     math.sin(a) * d), 0.90 + 0.30 * math.cos(i * 2.2),
                 "oak" if i % 4 == 0 else "pine")
    for i in range(14):
        a = 2 * math.pi * i / 14 + 0.5
        d = 7.5 + 2.2 * math.sin(i * 2.3)
        add_bush(b, (math.cos(a) * d, height(math.cos(a) * d, math.sin(a) * d),
                     math.sin(a) * d), 0.8 + 0.3 * math.cos(i), seed=i)
    for i in range(10):
        x = -6 + i * 1.3
        add_rock(b, (x, height(x, 3.2), 3.2), 0.25 + 0.15 * (i % 3),
                 (0.33, 0.30, 0.26), seed=40 + i)
    travel = p * 3.4
    base_z = -0.2
    trio = (("man", 0.0, 0.0), ("woman", -0.95, 0.55), ("elder", -1.95, 1.1))
    for kind, off, phase in trio:
        x = -1.8 + travel + off
        z = base_z + (0.35 if kind == "woman" else 0.0 if kind == "man" else 0.5)
        add_character(b, kind, pose_walk(t * 2.35 + phase), root=(x, height(x, z), z),
                      yaw=math.pi * 0.5, scale=1.0 if kind != "elder" else 0.92,
                      blink=blink_at(t, phase * 1.7))
    add_grass_tufts(b, (0.0, 0, 0.0), 34, 9.0, seed=11)
    lead = -1.8 + travel
    cam = ((lead + 2.75, height(0, -3.3) + 1.44, -3.15),
           (lead - 0.55, 1.05, 0.30))
    env = dict(sun=(0.45, 0.66, 0.5), sun_colour=(1.08, 0.92, 0.72),
               ambient=(0.27, 0.30, 0.37), ground=(0.24, 0.20, 0.14),
               fog=(0.62, 0.67, 0.74), fog_density=0.0008, exposure=0.70,
               night=0, moon=(0.50, 0.60, 0.030), shadow=0.8, fov=0.80,
               sky=((0.76, 0.72, 0.62), (0.22, 0.42, 0.70)),
               cloud=0.45, ao=0.62, bloom=0.35, dof_focus=3.6, dof=0.55)
    return [b.arrays()], dict(cam=cam, env=env)


def shot_finale(t: float, p: float) -> tuple[list, dict]:
    """The group at the fire; the camera eases back as the music resolves."""
    b = Builder()
    add_terrain(b, 140, 44, lambda x, z, y: (0.22 + 0.04 * y, 0.19 + 0.04 * y, 0.16))
    add_mountains(b, 58, 14)
    add_mountains(b, 42, 12, layer=1)
    add_treeline(b, 24, 28, 0.8)
    for i in range(9):
        a = 2 * math.pi * i / 9 + 0.7
        d = 17 + 3 * math.cos(i)
        add_tree(b, (math.cos(a) * d, height(math.cos(a) * d, math.sin(a) * d),
                     math.sin(a) * d), 0.85, "oak" if i % 3 == 0 else "pine")
    fx, fz = 0.0, 0.0
    fy = height(fx, fz)
    add_log(b, (-1.75, height(-1.75, 0.85), 0.85), 0.4, 1.9)
    add_fire(b, (fx, fy, 0.55), t, 1.02)
    for kind, pose, px, pz, sc, bl in (
        ("elder", pose_warm(t), -0.76, 0.06, 1.00, 0.0),
        ("woman", pose_warm(t + 2.1), 0.76, 0.10, 0.98, 1.9),
    ):
        yy = math.atan2(fx - px, 0.55 - pz)
        add_character(b, kind, pose, root=(px, height(px, pz), pz),
                      yaw=yy, scale=sc, grounded=True, blink=blink_at(t, bl + 1.3))
    add_grass_tufts(b, (0, 0, 0), 70, 9.0, seed=21)
    d = 4.05 + 1.60 * p
    h = 1.46 + 0.26 * p
    cam = ((math.sin(0.30) * d + 0.18, fy + h, math.cos(0.30) * d),
           (0.0, fy + 0.86, 0.02))
    env = dict(sun=(-0.3, 0.6, 0.5), sun_colour=(0.32, 0.34, 0.50),
               ambient=(0.32, 0.24, 0.19), ground=(0.13, 0.10, 0.08),
               fog=(0.14, 0.14, 0.22), fog_density=0.0013, exposure=0.82,
               night=1, moon=(0.36, 0.55, 0.032), shadow=0.5, fov=0.80,
               light=(0.0, fy + 0.50, 0.55), light_colour=(1.0, 0.42, 0.12),
               light_range=6.0,
               sky=((0.080, 0.078, 0.130), (0.016, 0.024, 0.066)),
               milky=0.90, cloud=0.0, ao=0.62, bloom=0.55,
               dof_focus=4.6, dof=0.55)
    return [b.arrays()], dict(cam=cam, env=env)


SHOTS = [
    (0.0, 5.0, shot_night),
    (5.0, 10.0, shot_fire),
    (10.0, 14.0, shot_tools),
    (14.0, 18.0, shot_walk),
    (18.0, 23.0, shot_finale),
]
