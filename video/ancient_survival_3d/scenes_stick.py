#!/usr/bin/env python3
"""Stickman reel: the same survival story in pre-viz stick figures.

Style reference: `kaomei/stickman-video-director` Style 1, dark - a black
field and a white figure, nothing else to hide behind. Style 3 (prehistoric
hand-drawn) supplies the set dressing: a fire, a spear, a cold night.

What makes this different from drawing sticks: the figures are driven by the
same skeleton and the same motion module as the photoreal cut (`rig.py`,
`motion.py`), so the walk is IK-planted, the weight transfers, and the head
leads the shoulders. The camera is a real 3D camera, and every shot is framed
by a projection formula rather than by eye.

    five shots, exactly 2.0 s each (48 frames at 24 fps), 10 s total

    0.0 - 2.0  WIDE   the watch, three-quarter, slow push
    2.0 - 4.0  CLOSE  the head snap (medium close-up)
    4.0 - 6.0  TRACK  he walks across frame, camera trucks with him
    6.0 - 8.0  FIRE   two of them at the flames, slow orbit
    8.0 - 10.0 GROUP  all three, wide, camera rising
"""

from __future__ import annotations

import math
import random

import numpy as np

import motion
from mesh3d import Builder
from rig import Rig, BONE_NAMES

# ------------------------------------------------------------------ skeleton
_RIG: Rig | None = None


def rig() -> Rig:
    global _RIG
    if _RIG is None:
        _RIG = Rig("hunter_stand")
    return _RIG


# stroke weight per bone, in metres at 1.76 m body height
THICK = {
    "pelvis": 0.020, "spine": 0.018, "chest": 0.020, "neck": 0.014,
    "head": 0.014,
    "upperarm_l": 0.017, "upperarm_r": 0.017,
    "forearm_l": 0.013, "forearm_r": 0.013,
    "thigh_l": 0.020, "thigh_r": 0.020,
    "shin_l": 0.016, "shin_r": 0.016,
    "foot_l": 0.012, "foot_r": 0.012,
}

JOINTS = ("pelvis", "chest", "neck", "upperarm_l", "upperarm_r",
          "forearm_l", "forearm_r", "thigh_l", "thigh_r", "shin_l", "shin_r")

# a flat, unlit white: the figure is drawn, not lit
INK = (0.03, 0.03, 0.035)
WHITE = 0.46


def add_stick(b: Builder, pose, pos, yaw: float, height: float = 1.76,
              glow: float = WHITE, open_arms: float = 1.0) -> dict:
    """Emit one stick figure and return its world anchors.

    `open_arms` pushes the upper arms off the torso around the forward axis.
    A front-on stickman collapses into one bright column otherwise, which is
    exactly what happened in the first pass of this shot.
    """
    if open_arms:
        pose = _copy_pose(pose)
        pose.add("upperarm_l", rz=-0.20 * open_arms)
        pose.add("upperarm_r", rz=0.20 * open_arms)
    _, anc = rig().deform(pose, ground=True)
    k = height / 1.76
    x, y, z = (float(v) for v in pos)
    dx, dz = math.sin(yaw), math.cos(yaw)
    side = np.array([dz, 0.0, -dx])

    # same basis as the photoreal actors (rig.build): person X -> screen right,
    # person Z -> the direction the figure faces. Getting this backwards hides
    # a walk's stride along the camera axis, which is exactly what it did here.
    def world(p):
        return np.array([x + (side[0] * p[0] + dx * p[2]) * k,
                         y + p[1] * k,
                         z + (side[2] * p[0] + dz * p[2]) * k])

    b.mat = 0.0
    for bone in BONE_NAMES:
        head, tail = world(anc[bone + "_head"]), world(anc[bone])
        r = THICK.get(bone, 0.018) * k
        r2 = r * (0.64 if bone.startswith(("forearm", "shin")) else 0.88)
        b.capsule(head, tail, r, r2, INK, rings=3, seg=7,
                  emission=(glow, glow, glow * 1.02))
    # a stick figure is not five separate sticks: the shoulders and hips are
    # joined by short bars, which is what makes it read as a body rather than
    # a bundle of lines
    for s_ in ("l", "r"):
        neck = world(anc["neck_head"])
        shoulder = world(anc["upperarm_" + s_ + "_head"])
        b.capsule(neck, shoulder, 0.013 * k, 0.011 * k, INK, rings=2, seg=6,
                  emission=(glow * 0.9,) * 3)
        hip = world(anc["pelvis_head"])
        hipj = world(anc["thigh_" + s_ + "_head"])
        b.capsule(hip, hipj, 0.014 * k, 0.012 * k, INK, rings=2, seg=6,
                  emission=(glow * 0.9,) * 3)
    for bone in JOINTS:
        b.sphere(world(anc[bone + "_head"]), 0.021 * k, INK,
                 rings=4, seg=9, emission=(glow, glow, glow))
    for s in ("l", "r"):
        b.sphere(world(anc["foot_" + s]), 0.012 * k, INK, rings=3, seg=7,
                 emission=(glow, glow, glow))
    neck = world(anc["neck_head"])
    top = world(anc["head"])
    centre = neck + (top - neck) * 0.58
    b.sphere(centre, 0.062 * k, INK, rings=9, seg=15,
             emission=(glow, glow, glow * 1.02))
    return {
        "head": centre,
        "hand_r": world(anc["forearm_r"]),
        "hand_l": world(anc["forearm_l"]),
        "foot_r": world(anc["foot_r"]),
        "foot_l": world(anc["foot_l"]),
    }


def _copy_pose(pose):
    from rig import Pose
    p = Pose()
    p.rot = dict(pose.rot)
    p.root = np.array(pose.root, float)
    p.root_rot = tuple(pose.root_rot)
    return p


def add_spear(b: Builder, hand, tilt: float = 0.0, length: float = 1.72,
              glow: float = 0.34, plant: float = 0.26) -> None:
    """A spear planted on the ground beside him, his hand resting on the shaft.

    Held free in the hand it swung across his head and read as a second stick;
    planted, it is instantly a spear and it anchors the silhouette.
    """
    h = np.asarray(hand, float)
    base = np.array([h[0] + plant, 0.0, h[2] + 0.05])
    top = base + np.array([math.sin(tilt) * length, length, 0.0])
    b.mat = 0.0
    b.capsule(base, top, 0.008, 0.007, INK, rings=3, seg=6,
              emission=(glow, glow, glow))
    b.cone(top, 0.022, 0.13, INK, seg=5, emission=(glow * 1.6,) * 3)


# --------------------------------------------------------------------- stage
def add_floor(b: Builder, extent: float = 26.0, cells: int = 24) -> None:
    """A dark plane, plus a pool of rings to give the frame a centre."""
    b.mat = 8.0
    b.ground(extent, cells, lambda x, z: 0.0,
             lambda x, z, y: (0.016, 0.019, 0.028))
    seg = 44
    for i in range(6):
        r = 0.7 + i * 0.78
        pts = [(math.cos(2 * math.pi * j / seg) * r, 0.005,
                math.sin(2 * math.pi * j / seg) * r) for j in range(seg)]
        b.mat = 0.0
        g = 0.16 * (1.0 - i / 6.5)
        for j in range(seg):
            b.capsule(pts[j], pts[(j + 1) % seg], 0.006, 0.006, INK,
                      rings=2, seg=4, emission=(g * 0.55, g * 0.72, g))


def add_dust(b: Builder, t: float, centre, count: int = 30, radius: float = 4.0,
             seed: int = 4) -> None:
    rng = random.Random(seed)
    cx, cy, cz = centre
    for i in range(count):
        a = rng.random() * math.tau + t * (0.04 + 0.05 * rng.random())
        r = 0.7 + rng.random() * radius
        h = 0.15 + rng.random() * 2.4 + 0.06 * math.sin(t * 1.3 + i)
        tw = 0.5 + 0.5 * math.sin(t * 1.6 + i * 2.3)
        if tw < 0.62:
            continue
        b.mat = 0.0
        b.sphere((cx + math.cos(a) * r, cy + h, cz + math.sin(a) * r),
                 0.007 + 0.004 * tw, INK, rings=2, seg=4,
                 emission=(0.10 * tw, 0.13 * tw, 0.20 * tw))


def add_fire(b: Builder, pos, t: float, scale: float = 1.0) -> None:
    """Stick-world fire: crossed logs and three soft tongues of light."""
    x, y, z = pos
    b.mat = 0.0
    for i in range(3):
        a = i * 2.1 + 0.4
        b.capsule((x - math.cos(a) * 0.32 * scale, y + 0.05, z - math.sin(a) * 0.32 * scale),
                  (x + math.cos(a) * 0.32 * scale, y + 0.09, z + math.sin(a) * 0.32 * scale),
                  0.028 * scale, 0.024 * scale, (0.55, 0.48, 0.40),
                  rings=3, seg=6, emission=(0.13, 0.09, 0.05))
    for i in range(3):
        h = (0.58 + 0.09 * math.sin(t * 7.0 + i * 2.0)) * scale * (1.0 - 0.16 * i)
        w = (0.15 - 0.03 * i) * scale
        sway = 0.05 * math.sin(t * 5.0 + i * 1.7)
        b.capsule((x + sway, y + 0.10, z), (x + sway * 2.2, y + 0.10 + h, z - 0.02),
                  w, 0.010, (0.80, 0.46, 0.18), rings=4, seg=8,
                  emission=(0.58, 0.27, 0.09))
    for i in range(16):
        ph = (t * 0.8 + i * 0.37) % 1.0
        fade = (1.0 - ph) ** 2
        b.mat = 0.0
        b.sphere((x + math.sin(t * 2.0 + i * 3.1) * 0.22 * ph,
                  y + 0.25 + ph * 1.4,
                  z + math.cos(t * 1.6 + i * 2.2) * 0.10 * ph),
                 0.011, INK, rings=2, seg=4,
                 emission=(0.70 * fade, 0.32 * fade, 0.08 * fade))


# -------------------------------------------------------------------- camera
def frame_subject(target, height: float, frac: float, fov: float,
                  side: float = 0.0, lens_y: float | None = None):
    """Camera placed so a `height`-tall subject fills `frac` of the frame.

    Straight from the projection: vertical extent h at distance d subtends
    2*atan(h / 2d), so d = h / (2 tan(fov/2) frac). Framing every shot this
    way means a close-up actually contains a head.
    """
    tx, ty, tz = target
    d = height / (2.0 * math.tan(fov * 0.5) * max(0.05, frac))
    cy = ty + height * 0.5 if lens_y is None else lens_y
    return (tx + side, cy, tz + d), (tx, ty + height * 0.5, tz)


def _env(fov: float, fire=None, exposure: float = 0.72, bloom: float = 0.10):
    e = dict(sun=(-0.45, 0.62, 0.40), sun_colour=(0.78, 0.86, 1.00),
             ambient=(0.10, 0.13, 0.22), ground=(0.03, 0.04, 0.06),
             fog=(0.010, 0.014, 0.026), fog_density=0.0045, exposure=exposure,
             night=1, moon=(-0.35, 0.55, 0.030), shadow=0.18,
             sky=((0.008, 0.011, 0.020), (0.0015, 0.002, 0.005)),
             milky=0.0, cloud=0.0, ao=0.55, bloom=bloom,
             dof_focus=0.0, dof=0.0, mist=None, mist_amount=0.0,
             mist_height=1.0, fov=fov)
    if fire is not None:
        fx, fy, fz = fire
        e.update(light=(fx, fy + 0.42, fz), light_colour=(1.0, 0.55, 0.22),
                 light_range=4.6,
                 light2=(fx, fy + 1.00, fz), light2_colour=(0.36, 0.17, 0.07),
                 light2_range=3.0)
    return e


# --------------------------------------------------------------------- shots
def shot_wide(t: float, p: float):
    """WIDE - the watch. Three-quarter, so both arms read against the dark."""
    b = Builder()
    add_floor(b)
    add_dust(b, t, (0.0, 0.0, 0.0), 26, 5.0)
    look = lambda tt: motion.curve(tt, [(0.0, -0.05), (0.7, -0.02),
                                        (1.3, -0.30), (2.0, -0.26)], ease=True)
    pose = motion.watch(t + 0.4, h=1.76, look_fn=look, lag=0.12)
    e = p * p * (3 - 2 * p)
    fov = 0.82
    cam, aim = frame_subject((0.0, 0.0, -0.2), 1.76, 0.60 + 0.05 * e, fov,
                             side=0.30 - 0.12 * e)
    # 48 degrees off the lens axis: the classic stick-figure three-quarter
    a = add_stick(b, pose, (0.0, 0.0, -0.2), 0.95, height=1.76, open_arms=1.4)
    add_spear(b, a["hand_r"], tilt=0.02, length=1.42, plant=0.30)
    return [b.arrays()], dict(cam=(cam, aim), env=_env(fov))


def shot_close(t: float, p: float):
    """CLOSE - the snap: the head goes first, the shoulders follow."""
    b = Builder()
    add_floor(b)
    add_dust(b, t, (0.0, 0.0, 0.0), 20, 3.4, seed=9)
    look = lambda tt: motion.curve(tt, [(0.0, -0.06), (0.45, -0.04),
                                        (0.78, -0.62), (1.15, -0.58),
                                        (2.0, -0.50)], ease=True)
    pose = motion.watch(t, h=1.76, look_fn=look, lag=0.11)
    e = p * p * (3 - 2 * p)
    fov = 0.74
    top = 1.76 * 0.985
    # chest to crown fills 90% of the frame: a real medium close-up
    cam, aim = frame_subject((0.0, 0.0, -0.3), 1.76, 0.80 + 0.04 * e, fov,
                             side=0.55 - 0.05 * e, lens_y=1.38)
    a = add_stick(b, pose, (0.0, 0.0, -0.3), 1.24, height=1.76, open_arms=1.0)
    add_spear(b, a["hand_r"], tilt=0.02, length=1.40, plant=0.26)
    return [b.arrays()], dict(cam=(cam, aim), env=_env(fov))


def shot_track(t: float, p: float):
    """TRACK - he walks across frame; the ground slides under the planted foot."""
    b = Builder()
    add_floor(b)
    add_dust(b, t, (0.0, 0.0, 0.0), 30, 5.5, seed=15)
    yaw = 1.57
    pose, wx, wz = motion.walk_forward(t, -1.05, 0.30, yaw, speed=0.55, h=1.76)
    fov = 0.80
    cam, aim = frame_subject((wx, 0.0, wz), 1.76, 0.50, fov, side=0.30)
    a = add_stick(b, pose, (wx, 0.0, wz), yaw, height=1.76, open_arms=0.0)
    add_spear(b, a["hand_r"], tilt=0.03, length=1.40, plant=0.22)
    return [b.arrays()], dict(cam=(cam, aim), env=_env(fov))


def shot_fire(t: float, p: float):
    """FIRE - hands to the heat, an orbit, and a light that lives."""
    b = Builder()
    add_floor(b)
    add_dust(b, t, (0.0, 0.0, 0.0), 22, 4.5, seed=21)
    fx, fz = 0.0, -0.55
    add_fire(b, (fx, 0.0, fz), t, 0.56)
    e = p * p * (3 - 2 * p)
    fov = 0.78
    # fit the pair (they stand behind the fire), then swing that camera round
    pair = (0.0, 0.0, fz - 0.70)
    cam0, aim = frame_subject(pair, 1.70, 0.60, fov, lens_y=1.10)
    d = cam0[2] - pair[2]
    ang = -0.20 + 0.24 * e
    cam = (math.sin(ang) * d, cam0[1], pair[2] + math.cos(ang) * d)
    p1 = motion.warm(t, h=1.70, seed=0.31)
    p2 = motion.warm(t + 1.1, h=1.66, seed=0.72)
    add_stick(b, p1, (-0.40, 0.0, fz - 0.74), 0.30, height=1.70, open_arms=0.0)
    add_stick(b, p2, (0.44, 0.0, fz - 0.66), -0.26, height=1.66, open_arms=0.0)
    return [b.arrays()], dict(cam=(cam, aim), env=_env(fov, fire=(fx, 0.0, fz)))


def shot_group(t: float, p: float):
    """GROUP - all three, wide, the camera rising out of the scene."""
    b = Builder()
    add_floor(b)
    add_dust(b, t, (0.0, 0.0, 0.0), 28, 6.0, seed=33)
    fx, fz = 0.0, -1.45
    add_fire(b, (fx, 0.0, fz), t + 0.7, 0.72)
    e = p * p * (3 - 2 * p)
    fov = 0.86
    # frame the three of them, not one of them: 0.44 of frame height each
    cam, aim = frame_subject((0.0, 0.0, fz + 0.66), 1.78, 0.40, fov,
                             side=0.26 - 0.44 * e, lens_y=1.22 + 0.30 * e)
    p1 = motion.warm(t, h=1.72, seed=0.2)
    look = lambda tt: motion.curve(tt, [(0.0, 0.0), (0.8, 0.22), (2.0, 0.26)])  # noqa: E731
    p3 = motion.watch(t, h=1.78, look_fn=look)
    p2 = motion.warm(t + 0.9, h=1.68, seed=0.66)
    add_stick(b, p1, (-0.62, 0.0, fz + 0.58), 0.30, height=1.72, open_arms=0.0)
    add_stick(b, p3, (0.06, 0.0, fz + 0.72), 0.18, height=1.78)
    add_stick(b, p2, (0.70, 0.0, fz + 0.50), -0.28, height=1.68, open_arms=0.0)
    return [b.arrays()], dict(cam=(cam, aim), env=_env(fov, fire=(fx, 0.0, fz)))


# exactly 2.0 s per shot
SHOTS = [
    (0.0, 2.0, shot_wide),
    (2.0, 4.0, shot_close),
    (4.0, 6.0, shot_track),
    (6.0, 8.0, shot_fire),
    (8.0, 10.0, shot_group),
]
