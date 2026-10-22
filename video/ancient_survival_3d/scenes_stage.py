#!/usr/bin/env python3
"""The photoreal pass: AI plates as the set, skinned photo people in front.

This is the answer to "make the 3D as realistic as the reference". The
reference reel is not realistic because of its polygons - it is realistic
because the frame *looks photographic*: real sky, real ground, real people,
real depth of field. Geometry at this budget cannot buy that. So the set is
now two photographic plates hung in real 3D space (`stage.py`, material 22),
and everything that has to move is still honest 3D: skinned photo people with
skeletal motion, a fire's light, embers, contact shadows, haze.

    shot_watch  0.0 - 4.8 s   a hunter on watch in the treeline: the slow
                              sweep of his head, one deliberate step, a warm
                              campfire glowing behind the trunks
    shot_camp   4.8 - 10.0 s  the fire itself: two of them warming their
                              hands, firelight flickering across the coats,
                              embers climbing into the dark

Both plates are already graded photographs, so they are written to the frame
unlit; the people are lit by the same moon / fire the plates were lit by, so
the two layers share one light.
"""

from __future__ import annotations

import math
import random

import numpy as np

import actors
import motion
import photopeople as PP
import stage
from mesh3d import Builder

import os
GAIN = float(os.environ.get("STAGE_GAIN", "0.40"))
TINT = float(os.environ.get("STAGE_TINT", "0.22"))

# ------------------------------------------------------------------ helpers
def _match_plate(cam, plate_distance: float, plate_shift=(0.0, 0.0),
                 overscan: float = 1.0, name: str = "night", fov: float = 0.86,
                 aspect: float = 9 / 16) -> None:
    pass


def _embers(b: Builder, centre, t: float, count: int = 26, spread: float = 0.55,
            height: float = 1.5, seed: int = 5, heat: float = 1.0) -> None:
    """Sparks leaving the fire: each one is on its own little arc."""
    rng = random.Random(seed)
    cx, cy, cz = centre
    b.mat = 0.0
    for i in range(count):
        life = 2.1 + rng.random() * 1.9
        phase = rng.random()
        dx = (rng.random() - 0.5) * spread
        dz = (rng.random() - 0.5) * spread
        rise = height * (0.55 + rng.random() * 0.75)
        u = ((t / life) + phase) % 1.0
        y = cy + rise * (u ** 0.78)
        sway = 0.10 * math.sin(t * 1.7 + i * 2.3) * u
        fade = (1.0 - u) ** 1.5 * min(1.0, u * 9.0)
        if fade < 0.04:
            continue
        r = 0.008 + 0.004 * rng.random()
        b.sphere((cx + dx * u + sway, y, cz + dz * u + sway * 0.6), r,
                 (0.4, 0.16, 0.05), rings=3, seg=5,
                 emission=(2.6 * fade * heat, 1.15 * fade * heat, 0.30 * fade * heat))


def _haze_sprite(b, pos, radius, cam, strength):
    stage.glow_sprite(b, pos, radius, cam[0], cam[1], strength=strength)


# --------------------------------------------------------------------- shots
def shot_watch(t: float, p: float):
    b = Builder()
    e = p * p * (3 - 2 * p)

    # ---- camera: a slow creep in, with a breath of hand-held drift
    drift = (0.0060 * math.sin(t * 1.7 + 0.4), 0.0040 * math.sin(t * 2.3 + 1.1),
             0.0045 * math.sin(t * 1.3 + 2.2))
    cam_pos = (0.36 - 0.09 * e + drift[0], 1.46 - 0.02 * e + drift[1],
               3.05 - 0.42 * e + drift[2])
    aim = (-0.05, 1.30 + drift[1] * 0.6, -2.6)
    fov = 0.84
    cam = (cam_pos, aim)

    # ---- the set: the forest, hung at 11 m so it has real parallax
    stage.add_plate(b, "night", cam_pos, aim, fov, 9 / 16, distance=11.0,
                    overscan=1.02, shift=(0.02, -0.055))

    # ---- a camp fire far behind the trunks: only sparks and a breath of
    #      light in the haze reach this far
    fire_at = (-2.55, 0.16, -9.2)
    flick = 0.82 + 0.18 * math.sin(t * 9.1) * math.sin(t * 3.3 + 1.2)
    _embers(b, fire_at, t, count=12, spread=0.42, height=0.95, seed=11, heat=0.7)

    # ---- the hunter: a card with a skeleton, watching the treeline
    hx, hz = 0.12, -0.45
    hyaw = PP.yaw_for((hx, 0.0, hz), cam_pos, aim=(-1.10, 0.0, -2.4), max_dev=0.30)
    look = lambda tt: motion.curve(tt, [
        (0.00, -0.06), (1.10, -0.10), (1.85, -0.02),
        (2.25, -0.46), (2.55, -0.52), (3.80, -0.50),
        (4.15, -0.18), (4.80, -0.08)], ease=True)
    idle = lambda tt: motion.watch(tt, h=1.78, look_fn=look, lag=0.13)  # noqa: E731
    # ...and then he takes one step: weight back, push-off, a swinging foot that
    # clears the ground, heel-strike, and the mass rolling over the new stance.
    # The legs are IK-locked to their planted feet, so nothing skates.
    pose, travel = motion.step(t, 2.55, h=1.78, length=0.26, dwell=1.00, base=idle)
    tense = motion.curve(t, [(0.0, 0.0), (2.30, 0.0), (2.46, 1.0),
                             (3.30, 0.82), (4.10, 0.22), (4.8, 0.0)])
    if tense > 0.01:
        pose.add("spine", rx=0.05 * tense)
        pose.add("chest", rx=0.032 * tense)
        pose.add("neck", rx=-0.032 * tense)
        pose.add("upperarm_r", rz=-0.03 * tense)
        pose.add("upperarm_l", rz=0.03 * tense)
    fwd = np.array([math.sin(hyaw), 0.0, math.cos(hyaw)])
    hx2 = hx + float(fwd[0]) * travel
    hz2 = hz + float(fwd[2]) * travel
    stage.contact_shadow(b, hx2, hz2, 0.0, 0.62, cam_pos=cam_pos, target=aim,
                         strength=1.0)
    stage.contact_shadow(b, hx2, hz2, 0.0, 0.30, cam_pos=cam_pos, target=aim,
                         strength=1.0)
    anc = actors.add(b, "hunter_stand", (hx2, 0.0, hz2), hyaw, pose,
                     bind="stand", height=1.78, gain=GAIN, tint=TINT,
                     contact_shadow=False)

    # ---- cold night, warm fire behind him: the two lights of the shot
    env = dict(sun=(-0.52, 0.40, 0.34), sun_colour=(0.52, 0.62, 0.95),
               ambient=(0.11, 0.14, 0.25), ground=(0.05, 0.06, 0.09),
               fog=(0.10, 0.13, 0.21), fog_density=0.0016, exposure=1.06,
               night=1, moon=(-0.34, 0.44, 0.10), shadow=0.55,
               light=(fire_at[0] + 0.4, 0.55, fire_at[2] + 1.6),
               light_colour=(1.0, 0.52, 0.20), light_range=7.0,
               light2=(fire_at[0], 0.95, fire_at[2] + 1.0),
               light2_colour=(0.55, 0.24, 0.08), light2_range=4.0,
               sky=((0.05, 0.07, 0.13), (0.01, 0.02, 0.05)),
               milky=0.9, cloud=0.0, ao=0.70, bloom=0.55,
               dof_focus=3.9, dof=0.22,
               mist=(0.30, 0.37, 0.55), mist_amount=0.30, mist_height=1.15,
               fov=fov)
    return [b.arrays()], dict(cam=cam, env=env)


def shot_camp(t: float, p: float):
    b = Builder()
    e = p * p * (3 - 2 * p)

    drift = (0.0050 * math.sin(t * 1.9 + 2.0), 0.0038 * math.sin(t * 2.5 + 0.6),
             0.0040 * math.sin(t * 1.5 + 1.3))
    cam_pos = (0.22 - 0.20 * e + drift[0], 1.34 + 0.02 * e + drift[1],
               2.35 - 0.26 * e + drift[2])
    aim = (-0.06, 1.16 + drift[1] * 0.6, -3.2)
    fov = 0.82
    cam = (cam_pos, aim)

    if os.environ.get("SKIP_PLATE") is None:
        stage.add_plate(b, "camp", cam_pos, aim, fov, 9 / 16, distance=6.6,
                        overscan=1.02, shift=(0.0, -0.10))

    flick = 0.80 + 0.16 * math.sin(t * 9.7) + 0.09 * math.sin(t * 23.3 + 1.0)
    fire_at = (0.02, 0.10, -5.4)
    _haze_sprite(b, (0.02, 0.42, -5.30), 0.80, cam, 0.26 * flick)
    _embers(b, (0.0, 0.24, -5.15), t, count=30, spread=0.62, height=1.7,
            seed=23, heat=1.0)

    # ---- the woman, warming her hands; the elder, further round the fire
    wx, wz = -0.92, -2.72
    wyaw = PP.yaw_for((wx, 0.0, wz), cam_pos, aim=(0.0, 0.0, -5.4), max_dev=0.30)
    wlook = lambda tt: motion.curve(tt, [(0.0, 0.05), (1.4, 0.10),
                                        (2.4, 0.02), (3.6, -0.05), (5.2, 0.0)])
    wk = motion.curve(t, [(0.0, 1.0), (3.2, 1.0), (4.4, 0.55), (5.2, 0.62)])
    wpose = motion.warm(t, h=1.66, seed=0.31, k=wk, look_fn=wlook)
    stage.contact_shadow(b, wx, wz, 0.0, 0.42, cam_pos=cam_pos, target=aim)
    actors.add(b, "woman_warm", (wx, 0.0, wz), wyaw, wpose, bind="warm",
               height=1.66, gain=GAIN * 0.86, tint=TINT * 0.75, contact_shadow=False)

    ex, ez = 0.90, -3.12
    eyaw = PP.yaw_for((ex, 0.0, ez), cam_pos, aim=(-0.6, 0.0, -3.2), max_dev=0.32)
    elook = lambda tt: motion.curve(tt, [(0.0, -0.06), (1.0, -0.12),
                                         (2.2, -0.02), (3.4, 0.06), (5.2, 0.0)])
    epose = motion.warm(t, h=1.70, seed=0.77, k=0.85, look_fn=elook)
    stage.contact_shadow(b, ex, ez, 0.0, 0.44, cam_pos=cam_pos, target=aim)
    actors.add(b, "elder_warm", (ex, 0.0, ez), eyaw, epose, bind="warm",
               height=1.70, gain=GAIN * 0.9, tint=TINT * 0.75, contact_shadow=False)

    env = dict(sun=(-0.50, 0.42, 0.30), sun_colour=(0.40, 0.50, 0.78),
               ambient=(0.19, 0.22, 0.33), ground=(0.07, 0.07, 0.09),
               fog=(0.10, 0.11, 0.17), fog_density=0.0016, exposure=1.05,
               night=1, moon=(-0.30, 0.44, 0.06), shadow=0.55,
               light=(0.02, 0.30, -5.25), light_colour=(0.86, 0.44, 0.15),
               light_range=4.4,
               light2=(0.02, 0.85, -5.15), light2_colour=(0.60, 0.26, 0.09),
               light2_range=3.0,
               sky=((0.05, 0.06, 0.11), (0.01, 0.02, 0.05)),
               milky=0.8, cloud=0.0, ao=0.70, bloom=0.60,
               dof_focus=3.4, dof=0.30,
               mist=(0.30, 0.35, 0.50), mist_amount=0.26, mist_height=1.0,
               fov=fov)
    return [b.arrays()], dict(cam=cam, env=env)


SHOTS = [
    (0.0, 4.8, shot_watch),
    (4.8, 10.0, shot_camp),
]
