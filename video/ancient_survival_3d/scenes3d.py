"""3D scenes for the Ancient Survival reel.

Every object in these shots is geometry generated at render time: terrain,
rocks, trees, the fire, and the rigged cast. Nothing is a picture.
"""

from __future__ import annotations

import math
import random

import numpy as np

from mesh3d import (Builder, Rig, make_transform, pose_crouch, pose_idle, pose_knap,
                    pose_pick, pose_point, pose_sit_tend, pose_sit_warm, pose_walk,
                    pose_warm)

RIG = Rig()
S_RIG = RIG
RNG = random.Random(7)


# ------------------------------------------------------------------ terrain
def height(x: float, z: float) -> float:
    return (0.55 * math.sin(x * 0.055 + 0.4) * math.cos(z * 0.045)
            + 0.35 * math.sin((x + z) * 0.09)
            + 0.18 * math.cos(x * 0.21 - z * 0.13))


def ground_colour(x: float, z: float, y: float):
    patch = 0.5 + 0.5 * math.sin(x * 0.31) * math.cos(z * 0.27)
    dry = max(0.0, min(1.0, 0.38 + 0.30 * patch + 0.10 * y))
    return (0.30 + 0.16 * dry, 0.27 + 0.12 * dry, 0.15 + 0.05 * dry)


def add_terrain(b: Builder, size: float = 120.0, cells: int = 44,
                colour=ground_colour) -> None:
    b.ground(size, cells, height, colour)


def add_rock(b: Builder, pos, size: float, colour=(0.34, 0.31, 0.27), seed: int = 0):
    rng = random.Random(seed)
    x, y, z = pos
    b.sphere((x, y + size * 0.42, z), size, colour, rings=7, seg=9,
             scale=(1.0 + rng.random() * 0.5, 0.62 + rng.random() * 0.3,
                    0.8 + rng.random() * 0.5), squash=0.22)


def add_tree(b: Builder, pos, scale: float = 1.0, kind: str = "pine"):
    x, y, z = pos
    if kind == "pine":
        b.capsule((x, y, z), (x, y + 2.4 * scale, z), 0.16 * scale, 0.10 * scale,
                  (0.26, 0.17, 0.10), rings=3, seg=6)
        for i in range(3):
            yy = y + (1.5 + i * 1.25) * scale
            b.cone((x, yy, z), (1.25 - i * 0.28) * scale, 2.0 * scale,
                   (0.10 + 0.02 * i, 0.20 + 0.03 * i, 0.12 + 0.02 * i), seg=7)
    else:
        b.capsule((x, y, z), (x, y + 1.6 * scale, z), 0.18 * scale, 0.12 * scale,
                  (0.28, 0.19, 0.11), rings=3, seg=6)
        for i in range(3):
            a = i * 2.1
            b.sphere((x + math.cos(a) * 0.55 * scale, y + 2.05 * scale,
                      z + math.sin(a) * 0.55 * scale), 0.85 * scale,
                     (0.20, 0.27, 0.12), rings=6, seg=8,
                     scale=(1.0, 0.72, 1.0), squash=0.18)
        b.sphere((x, y + 2.35 * scale, z), 0.95 * scale, (0.22, 0.29, 0.13),
                 rings=6, seg=9, scale=(1.0, 0.7, 1.0), squash=0.2)


def add_bush(b: Builder, pos, scale: float = 1.0, seed: int = 0):
    rng = random.Random(seed)
    x, y, z = pos
    for i in range(3):
        a = rng.random() * 2 * math.pi
        b.sphere((x + math.cos(a) * 0.3 * scale, y + 0.22 * scale,
                  z + math.sin(a) * 0.3 * scale), 0.34 * scale,
                 (0.17 + 0.04 * rng.random(), 0.24 + 0.04 * rng.random(), 0.11),
                 rings=5, seg=8, scale=(1.0, 0.75, 1.0), squash=0.22)
    b.sphere((x, y + 0.30 * scale, z), 0.40 * scale, (0.20, 0.27, 0.12),
             rings=6, seg=9, scale=(1.05, 0.72, 1.05), squash=0.25)


def add_mountains(b: Builder, radius: float, count: int = 14) -> None:
    for i in range(count):
        a = 2 * math.pi * i / count + 0.3
        d = radius * (0.82 + 0.2 * math.sin(i * 2.3))
        x, z = math.cos(a) * d, math.sin(a) * d
        h = 9 + 5 * math.sin(i * 1.7)
        b.cone((x, -1.2, z), 9 + 3 * math.cos(i * 2.1), h, (0.13, 0.15, 0.21), seg=7)


def add_grass_tufts(b: Builder, centre, count: int, spread: float, seed: int = 0):
    rng = random.Random(seed)
    for i in range(count):
        a = rng.random() * 2 * math.pi
        d = spread * (0.25 + rng.random() ** 0.6)
        x, z = centre[0] + math.cos(a) * d, centre[2] + math.sin(a) * d
        y = height(x, z)
        h = 0.22 + rng.random() * 0.3
        col = (0.36 + rng.random() * 0.14, 0.33 + rng.random() * 0.12, 0.15)
        for k in range(3):
            ang = a + k * 2.1
            b.capsule((x, y, z), (x + math.cos(ang) * 0.06, y + h, z + math.sin(ang) * 0.06),
                      0.022, 0.006, col, rings=2, seg=4)


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
    # layered emissive flame tongues
    for i in range(9):
        ph = t * (4.2 + i * 0.55) + i * 1.9
        h = (0.42 + 0.20 * math.sin(ph)) * scale * fuel
        w = (0.105 + 0.03 * math.sin(ph * 1.3)) * scale
        off = (i - 4) * 0.062 * scale
        lean = 0.05 * math.sin(ph * 0.8 + i) * scale
        b.cone((x + off, y + 0.10, z + (i % 3 - 1) * 0.04 * scale), w, h,
               (1.0, 0.48, 0.14), seg=7, emission=(0.30, 0.085, 0.012), lean=(lean, 0))
    for i in range(5):
        ph = t * (5.6 + i * 0.5) + i * 1.4
        h = (0.26 + 0.13 * math.sin(ph)) * scale * fuel
        b.cone((x + (i - 2) * 0.045 * scale, y + 0.12, z), 0.062 * scale, h,
               (1.0, 0.66, 0.24), seg=6, emission=(0.44, 0.20, 0.035))
    # sparks
    rng = random.Random(int(t * 12) + 3)
    for i in range(5):
        a = rng.random() * 2 * math.pi
        d = rng.random() * 0.55
        hh = 0.35 + rng.random() * 0.8
        b.sphere((x + math.cos(a) * d, y + hh, z + math.sin(a) * d), 0.013 * scale,
                 (1.0, 0.6, 0.2), rings=3, seg=4, emission=(0.75, 0.30, 0.06))


# ---------------------------------------------------------------- characters
PALETTES = {
    "man": dict(skin=(0.78, 0.55, 0.38), tunic=(0.62, 0.33, 0.12),
                hair=(0.08, 0.06, 0.05), grey=False),
    "woman": dict(skin=(0.80, 0.58, 0.42), tunic=(0.34, 0.36, 0.18),
                  hair=(0.10, 0.07, 0.05), grey=False),
    "elder": dict(skin=(0.76, 0.56, 0.42), tunic=(0.52, 0.50, 0.42),
                  hair=(0.72, 0.72, 0.70), grey=True),
}


def add_character(b: Builder, kind: str, pose, root=(0, 0, 0), yaw=0.0,
                  scale: float = 1.0, lean=(0.0, 0.0), grounded: bool = True) -> dict:
    pal = PALETTES[kind]
    if grounded:
        # Measure the real silhouette: build once at y=0, find the lowest vertex,
        # then slide the whole rig so that point touches the terrain. This works
        # for standing, walking, kneeling, sitting and lying poses alike.
        probe_b = Builder()
        probe_w = RIG.solve(pose, root=(root[0], 0.0, root[2]), yaw=yaw,
                            scale=scale, lean=lean)
        RIG.mesh(probe_b, probe_w, skin=pal["skin"], tunic=pal["tunic"],
                 hair=pal["hair"], grey_hair=pal["grey"])
        v = probe_b.arrays()[0]
        lowest = float(v[:, 1].min()) if len(v) else 0.0
        target = height(root[0], root[2]) + 0.015
        # probe was solved at y=0, so the offset is absolute (no double counting)
        root = (root[0], target - lowest, root[2])
    world = RIG.solve(pose, root=root, yaw=yaw, scale=scale, lean=lean)
    RIG.mesh(b, world, skin=pal["skin"], tunic=pal["tunic"], hair=pal["hair"],
             grey_hair=pal["grey"])
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
                  yaw=math.pi * 0.52, scale=1.0)
    add_grass_tufts(b, (0.0, 0, 0.0), 26, 7.0, seed=3)
    cam = ((run_x - 2.6, 1.55, -4.6), (run_x + 0.3, 1.05, 0.4))
    env = dict(sun=(-0.35, 0.72, 0.5), sun_colour=(0.66, 0.72, 0.96),
               ambient=(0.26, 0.31, 0.50), ground=(0.13, 0.13, 0.20),
               fog=(0.16, 0.19, 0.32), fog_density=0.0030, exposure=1.85,
               night=1, moon=(-0.34, 0.46, 0.045), shadow=0.55, fov=0.82)
    return [b.arrays()], dict(cam=cam, env=env)


def shot_fire(t: float, p: float) -> tuple[list, dict]:
    """Campfire: three figures in 3D, firelight as emissive geometry."""
    b = Builder()
    add_terrain(b, 120, 38, lambda x, z, y: (0.24 + 0.04 * y, 0.21 + 0.04 * y, 0.17))
    add_mountains(b, 60, 14)
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
    for kind, pose, px, pz, sc in (
        ("elder", pose_warm(t), -0.66, 0.02, 1.00),
        ("woman", pose_warm(t + 1.7), 0.66, 0.06, 0.98),
    ):
        yy = math.atan2(0.0 - px, 0.55 - pz)
        add_character(b, kind, pose, root=(px, height(px, pz), pz),
                      yaw=yy, scale=sc, grounded=True)
    add_grass_tufts(b, (0.0, 0, 0.0), 22, 6.0, seed=9)
    angle = -0.10 + 0.16 * p
    cam = ((math.sin(angle) * 4.65 + 0.26, y + 1.40, math.cos(angle) * 4.65),
           (-0.02, y + 0.74, 0.06))
    env = dict(sun=(-0.2, 0.55, 0.55), sun_colour=(0.22, 0.24, 0.40),
               ambient=(0.34, 0.22, 0.16), ground=(0.14, 0.10, 0.08),
               fog=(0.14, 0.13, 0.20), fog_density=0.0035, exposure=1.15,
               night=1, moon=(0.42, 0.52, 0.035), shadow=0.5, fov=0.78)
    return [b.arrays()], dict(cam=cam, env=env)


def shot_tools(t: float, p: float) -> tuple[list, dict]:
    """Stone tools: one survivor lifts a hand-axe, a mate holds the spear."""
    b = Builder()
    add_terrain(b, 80, 34, lambda x, z, y: (0.32 + 0.06 * y, 0.27 + 0.05 * y, 0.17))
    add_mountains(b, 56, 13)
    for i in range(10):
        rx, rz = -3.6 + i * 0.74, -3.1
        add_rock(b, (rx, height(rx, rz), rz), 0.16 + 0.08 * (i % 2),
                 (0.30, 0.28, 0.25), seed=20 + i)
    for i in range(5):
        rx, rz = -1.7 + i * 0.80, 1.85
        add_rock(b, (rx, height(rx, rz), rz), 0.09 + 0.04 * (i % 2),
                 (0.34, 0.32, 0.29), seed=31 + i)
    # the toolmaker lifts a fresh hand-axe; her mate carries the spear
    pose_a = pose_idle(t)
    pose_a.update({
        "shoulder_r": (-1.52 + 0.07 * math.sin(t * 2.4), 0.16, 0.26),
        "elbow_r": (-0.34, 0, 0),
        "shoulder_l": (0.10, 0, -0.24), "elbow_l": (-0.46, 0, 0),
        "chest": (0, 0.12, 0), "neck": (-0.10, 0, 0),
    })
    world_a = add_character(b, "woman", pose_a, root=(-0.52, height(-0.52, 0.30), 0.30),
                            yaw=0.42, scale=1.0, grounded=True)
    # hand-axe clasped in her fist, handle following the forearm line
    wrist = world_a["wrist_r"][:3, 3]
    elbow = world_a["elbow_r"][:3, 3]
    d = wrist - elbow
    d = d / (float(np.linalg.norm(d)) + 1e-6)
    head = wrist + d * 0.24
    b.capsule(wrist - d * 0.10, head + d * 0.03, 0.016, 0.019, (0.46, 0.34, 0.21), seg=5)
    b.sphere(head + d * 0.04, 0.055, (0.36, 0.34, 0.32), rings=5, seg=7,
             scale=(1.7, 1.0, 0.35))
    add_character(b, "man", pose_idle(t + 1.2), root=(0.66, height(0.66, -0.10), -0.10),
                  yaw=-0.55, scale=1.02, grounded=True)
    # spear planted in the ground beside him
    b.capsule((0.98, height(0.98, 0.15), 0.15), (0.86, height(0.86, 0.15) + 1.62, 0.15),
              0.022, 0.030, (0.45, 0.33, 0.20), seg=6)
    b.cone((0.86, height(0.86, 0.15) + 1.62, 0.15), 0.05, 0.17, (0.36, 0.33, 0.30),
           seg=6, lean=(0.02, 0.0))
    # knapped flakes and finished hand-axes on the ground
    for i in range(6):
        b.box((-0.55 + i * 0.15, height(-0.55 + i * 0.15, 1.35) + 0.02, 1.35),
              (0.085, 0.02, 0.13), (0.30, 0.29, 0.27), yaw=i * 0.7)
    for i, (ax, az, ay) in enumerate(((-0.05, 1.72, 0.5), (0.42, 1.55, -0.7))):
        b.sphere((ax, height(ax, az) + 0.05, az), 0.085, (0.33, 0.31, 0.29),
                 rings=5, seg=7, scale=(1.45, 0.5, 0.8))
    if max(0.0, math.sin(t * 6.5)) > 0.72:
        for k in range(3):
            a = k * 2.1
            b.sphere((-0.52 + math.cos(a) * 0.20, 1.06 + 0.10 + k * 0.04,
                      0.30 + math.sin(a) * 0.20), 0.016, (1.0, 0.86, 0.55),
                     rings=4, seg=4, emission=(1.1, 0.85, 0.5))
    cam = ((1.35, height(1.35, 3.75) + 1.56, 3.75), (-0.05, 0.94, 0.05))
    env = dict(sun=(0.55, 0.7, 0.45), sun_colour=(1.15, 0.98, 0.80),
               ambient=(0.40, 0.38, 0.36), ground=(0.26, 0.22, 0.16),
               fog=(0.62, 0.55, 0.46), fog_density=0.0016, exposure=1.05,
               night=0, moon=(0.5, 0.62, 0.05), shadow=0.8, fov=0.86)
    if p > 0:
        cam = ((1.35 - 0.20 * p, height(1.35, 3.75) + 1.56 - 0.05 * p, 3.75 - 0.35 * p),
               (-0.05, 0.94, 0.05))
    return [b.arrays()], dict(cam=cam, env=env)


def shot_walk(t: float, p: float) -> tuple[list, dict]:
    """Trio travels along a 3D path; camera tracks beside them."""
    b = Builder()
    add_terrain(b, 140, 42, ground_colour)
    add_mountains(b, 64, 15)
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
                      yaw=math.pi * 0.5, scale=1.0 if kind != "elder" else 0.92)
    add_grass_tufts(b, (0.0, 0, 0.0), 34, 9.0, seed=11)
    lead = -1.8 + travel
    cam = ((lead + 2.75, height(0, -3.3) + 1.44, -3.15),
           (lead - 0.55, 1.05, 0.30))
    env = dict(sun=(0.45, 0.66, 0.5), sun_colour=(1.18, 1.00, 0.80),
               ambient=(0.42, 0.44, 0.48), ground=(0.30, 0.25, 0.17),
               fog=(0.76, 0.68, 0.56), fog_density=0.0018, exposure=1.06,
               night=0, moon=(0.55, 0.66, 0.045), shadow=0.8, fov=0.80)
    return [b.arrays()], dict(cam=cam, env=env)


def shot_finale(t: float, p: float) -> tuple[list, dict]:
    """The group at the fire; the camera eases back as the music resolves."""
    b = Builder()
    add_terrain(b, 140, 44, lambda x, z, y: (0.22 + 0.04 * y, 0.19 + 0.04 * y, 0.16))
    add_mountains(b, 58, 14)
    for i in range(9):
        a = 2 * math.pi * i / 9 + 0.7
        d = 17 + 3 * math.cos(i)
        add_tree(b, (math.cos(a) * d, height(math.cos(a) * d, math.sin(a) * d),
                     math.sin(a) * d), 0.85, "oak" if i % 3 == 0 else "pine")
    fx, fz = 0.0, 0.0
    fy = height(fx, fz)
    add_log(b, (-1.75, height(-1.75, 0.85), 0.85), 0.4, 1.9)
    add_fire(b, (fx, fy, 0.55), t, 1.02)
    for kind, pose, px, pz, sc in (
        ("elder", pose_warm(t), -0.76, 0.06, 1.00),
        ("woman", pose_warm(t + 2.1), 0.76, 0.10, 0.98),
    ):
        yy = math.atan2(fx - px, 0.55 - pz)
        add_character(b, kind, pose, root=(px, height(px, pz), pz),
                      yaw=yy, scale=sc, grounded=True)
    add_grass_tufts(b, (0, 0, 0), 26, 8.0, seed=21)
    d = 4.05 + 1.60 * p
    h = 1.46 + 0.26 * p
    cam = ((math.sin(0.30) * d + 0.18, fy + h, math.cos(0.30) * d),
           (0.0, fy + 0.86, 0.02))
    env = dict(sun=(-0.3, 0.6, 0.5), sun_colour=(0.30, 0.32, 0.48),
               ambient=(0.36, 0.26, 0.20), ground=(0.15, 0.12, 0.09),
               fog=(0.16, 0.16, 0.24), fog_density=0.0032, exposure=1.24,
               night=1, moon=(0.36, 0.55, 0.05), shadow=0.5, fov=0.80)
    return [b.arrays()], dict(cam=cam, env=env)


SHOTS = [
    (0.0, 5.0, shot_night),
    (5.0, 10.0, shot_fire),
    (10.0, 14.0, shot_tools),
    (14.0, 18.0, shot_walk),
    (18.0, 23.0, shot_finale),
]
