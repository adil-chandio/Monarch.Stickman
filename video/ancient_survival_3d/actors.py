#!/usr/bin/env python3
"""Actors: photo cards with a skeleton, and the bind pose they were shot in.

Every AI plate is already in *some* pose. Rotating a plate's limbs again on
top of the pose it was drawn in is what made the first skinned test stretch an
arm into a smear. So each card is bound to the pose it was photographed in and
the motion layer only ever supplies the delta from there:

    bind "stand"  hunter_stand, woman_stand, elder_stand
    bind "walk"   hunter_walk        (mid-stride plate)
    bind "warm"   woman_warm, elder_warm  (hands already out to the fire)

`add()` therefore takes the *absolute* motion pose and subtracts the plate's
own pose internally, which keeps the photoreal texture exactly where the
photographer put it while the body still moves.
"""

from __future__ import annotations

import numpy as np

import motion
import photopeople as PP
from rig import Rig

BINDS = {
    "stand": None,                 # neutral skeleton: plates shot standing
    "warm": None,                  # resolved lazily (motion.warm(0.0))
    "walk": None,
}

_CACHE: dict[tuple[str, str], Rig] = {}


def _bind_pose(tag: str):
    if tag == "stand":
        return None
    cached = BINDS.get(tag)
    if cached is not None:
        return cached
    pose = motion.warm(0.0) if tag == "warm" else motion.walk(0.0)
    BINDS[tag] = pose
    return pose


def rig_for(name: str, bind: str = "stand") -> Rig:
    key = (name, bind)
    r = _CACHE.get(key)
    if r is None:
        r = Rig(name, bind=_bind_pose(bind))
        _CACHE[key] = r
    return r


def add(b, name: str, pos, yaw: float, pose, bind: str = "stand",
        height: float | None = None, gain: float = 0.92, tint: float = 0.0,
        contact_shadow: bool = True, shadow_strength: float = 0.5) -> dict:
    """Emit one skinned figure; returns anchors (head, mouth, hands, feet)."""
    r = rig_for(name, bind)
    return r.build(b, pos, yaw, pose, height=height, gain=gain, tint=tint,
                   contact_shadow=contact_shadow, shadow_strength=shadow_strength)
