#!/usr/bin/env python3
"""Motion library: a physical gait and living idles for the skinned cards.

The motion is authored against anatomy and mechanics, not as sine waves:

* every leg is solved with two-bone IK, so the stance foot is *planted* - it
  never slides, and the knee bends exactly as far as the hip height requires
* the pelvis leads the chain (hips -> knees -> ankles), the shoulders counter-
  rotate against the hips, the arms swing opposite the legs and the elbows lag
  the shoulders
* the pelvis bobs twice per stride (lowest at double support) and sways over
  the supporting leg; the head counter-rotates to stay level
* a figure leans into acceleration and rocks back when it decelerates
* standing figures breathe, shift weight foot to foot and micro-settle

Units: the pose is in person space, +Y up, +X to the figure's right, +Z
forward. Bone angles are radians, `h` is the figure's height in metres.
"""

from __future__ import annotations

import math

import numpy as np

from rig import Pose

TAU = math.pi * 2.0

# proportions as a fraction of height (matching rig.BONES)
L_THIGH = 0.235
L_SHIN = 0.240
HIP_Y = 0.520
ANKLE_Y = 0.045
SHOULDER_Y = 0.800


# ------------------------------------------------------------------ helpers
def np3(x, y, z):
    return np.array([x, y, z], float)


def smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * k


def blend(a: Pose, b: Pose, k: float) -> Pose:
    """Cross-fade two poses (walk settling into a stand, arm reaches, ...)."""
    k = max(0.0, min(1.0, k))
    out = Pose()
    for bone in set(a.rot) | set(b.rot):
        ra = a.rot.get(bone, (0.0, 0.0, 0.0))
        rb = b.rot.get(bone, (0.0, 0.0, 0.0))
        out.rot[bone] = tuple(lerp(ra[i], rb[i], k) for i in range(3))
    out.root = a.root * (1.0 - k) + b.root * k
    out.root_rot = tuple(lerp(a.root_rot[i], b.root_rot[i], k) for i in range(3))
    return out


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


def leg_ik(hip_y: float, ankle_z: float, ankle_y: float, h: float,
           ankle_x: float = 0.0, hip_x: float = 0.0):
    """Solve one leg: returns (thigh_rx, shin_rx, thigh_rz).

    hip_y / ankle_y in metres above the ground, ankle_z / ankle_x relative to
    the hip in metres. Two-bone IK with the knee pointing forward; the reach
    is clamped so the leg never hyper-extends into a lock.
    """
    l1, l2 = L_THIGH * h, L_SHIN * h
    dz = ankle_z
    dy = ankle_y - hip_y                     # negative: ankle below the hip
    d = math.hypot(dz, dy)
    d = _clamp(d, abs(l1 - l2) + 1e-4, l1 + l2 - 1e-3)
    # knee flexion (positive = heel towards the buttock)
    cos_k = _clamp((l1 * l1 + l2 * l2 - d * d) / (2.0 * l1 * l2), -1.0, 1.0)
    knee = math.pi - math.acos(cos_k)
    # hip angle measured from straight-down towards forward
    alpha = math.atan2(dz, -dy)
    cos_b = _clamp((l1 * l1 + d * d - l2 * l2) / (2.0 * l1 * d), -1.0, 1.0)
    beta = math.acos(cos_b)
    thigh = alpha - beta
    # lateral swing so the foot can stay under a splayed stance
    lateral = math.asin(_clamp((ankle_x - hip_x) / max(d, 1e-4), -1.0, 1.0))
    return -(alpha + beta), knee, lateral


def _foot(pose: Pose, side: str, thigh_rx: float, shin_rx: float,
          pitch: float = 0.0) -> None:
    """Keep the sole on the ground: the ankle absorbs the leg's rotations.

    `pitch` is the extra world-space foot angle (negative = toes up at heel
    strike, positive = toes down at toe-off), so the foot rolls heel -> flat ->
    toe like a real one instead of hinging with the shin.
    """
    pose.set("foot_" + side, rx=pitch - (thigh_rx + shin_rx))


def _arm_chain(pose: Pose, side: str, shoulder: float, elbow: float,
               shoulder_out: float = 0.0) -> None:
    """Set one arm: reverse-pendulum swing + elbow follow-through."""
    sgn = 1.0 if side == "r" else -1.0
    pose.set("upperarm_" + side, rx=shoulder, rz=-sgn * (0.055 + shoulder_out))
    pose.set("forearm_" + side, rx=elbow)


# -------------------------------------------------------------------- gaits
def walk(t: float, stride: float = 1.10, speed: float = 1.0, h: float = 1.72,
         phase: float = 0.0, lean: float = 0.0, sway: float = 1.0) -> Pose:
    """One full gait cycle (two steps). `stride` = seconds per cycle."""
    p = (t / stride + phase) % 1.0
    S = (0.55 + 0.27 * speed) * h / 1.72      # metres travelled per cycle
    stance = 0.60                              # 60% stance, as in real walking
    pose = Pose()

    # ---- pelvis: bob twice per cycle, sway once, drop over the swing leg ---
    bob = -0.018 * h / 1.72 * math.cos(2.0 * TAU * p + 0.35) * (0.55 + 0.55 * speed)
    sway_x = 0.017 * math.sin(TAU * p) * (0.6 + 0.5 * speed) * sway
    # walking sits lower than standing: the pelvis drops so the front leg can
    # reach the ground without locking the knee (that drop is the bob you see)
    drop = -0.026 * h / 1.72
    pose.root = pose.root + (sway_x, drop + bob, 0.0)
    hip_y = HIP_Y * h + drop + bob

    # ---- legs: IK from the planted foot, both sides half a cycle apart -----
    for side, off in (("r", 0.0), ("l", 0.5)):
        q = (p + off) % 1.0
        if q < stance:                          # foot on the ground
            u = q / stance
            z = (0.5 - u) * stance * S          # travels back under the body
            lift = 0.0
        else:                                   # swing
            u = (q - stance) / (1.0 - stance)
            e = smooth(u)
            z = (-0.5 + e) * stance * S + (e - u) * 0.0
            lift = 0.085 * h / 1.72 * math.sin(math.pi * u) ** 1.15
        thigh, knee, lat = leg_ik(hip_y, z, ANKLE_Y * h + lift, h,
                                  ankle_x=(0.055 if side == "r" else -0.055) * h - sway_x,
                                  hip_x=(0.052 if side == "r" else -0.052) * h)
        pose.set("thigh_" + side, rx=thigh, rz=lat)
        pose.set("shin_" + side, rx=knee)
        if q < stance:                       # heel strike -> flat -> toe-off
            u = q / stance
            pitch = (-0.20 * (1.0 - smooth(u / 0.16))
                     + 0.52 * smooth((u - 0.72) / 0.28))
        else:                                # swing: toes clear the ground
            u = (q - stance) / (1.0 - stance)
            pitch = 0.20 * (1.0 - smooth(u / 0.35)) - 0.10 * smooth((u - 0.55) / 0.45)
        _foot(pose, side, thigh, knee, pitch)

    # ---- pelvis / torso counter-rotation ----------------------------------
    twist = 0.115 * math.cos(TAU * p)
    pose.add("pelvis", ry=-twist * 1.0, rz=-0.055 * math.sin(TAU * p),
             rx=0.05 * speed)
    pose.add("spine", ry=twist * 0.45, rx=-0.055 * speed + 0.018 * math.cos(2 * TAU * p))
    pose.add("chest", ry=twist * 0.85, rx=-0.03 * speed + 0.012 * math.cos(2 * TAU * p + 0.8))
    pose.root_rot = (lean + 0.05 * speed, -twist * 0.35, -0.5 * sway_x)

    # ---- head: level, a beat behind, small nod at each contact ------------
    pose.add("neck", ry=-twist * 0.55, rx=0.05 * speed - 0.018 * math.cos(2 * TAU * (p - 0.08)))
    pose.add("head", ry=-twist * 0.25, rx=-0.02 * math.cos(2 * TAU * (p - 0.10)))

    # ---- arms: opposite the legs, elbow lags, shoulder opens on the swing -
    amp = 0.19 + 0.15 * speed
    for side, off in (("r", 0.5), ("l", 0.0)):
        sh = amp * math.cos(TAU * ((p + off) % 1.0 - 0.055))
        el = -(0.20 + 0.20 * speed) - 0.16 * max(0.0, math.cos(TAU * ((p + off) % 1.0 - 0.16)))
        _arm_chain(pose, side, sh, el, shoulder_out=0.02 * speed)
    return pose


def walk_forward(t: float, x0: float, z0: float, yaw: float, speed: float = 1.0,
                 **kw):
    """Walk in a straight line: returns (pose, world_x, world_z).

    The root travels at the gait's own ground speed, so the planted foot stays
    nailed to the ground instead of skating.
    """
    stride = kw.get("stride", 1.10)
    S = (0.55 + 0.27 * speed) * kw.get("h", 1.72) / 1.72
    dist = S / stride * t
    pose = walk(t, **kw)
    return pose, x0 + math.sin(yaw) * dist, z0 + math.cos(yaw) * dist


# ------------------------------------------------------------------- idles
def stand(t: float, h: float = 1.72, breathe: float = 1.0, sway: float = 1.0,
          seed: float = 0.0, settle: float = 1.0,
          foot_r: float = 0.0, foot_l: float = 0.0) -> Pose:
    """Standing at rest: breathing, weight transfer foot to foot, micro-sway.

    The feet are solved with IK, so shifting the hips from one foot to the
    other bends the knees and rolls the pelvis instead of sliding the body.
    `foot_r` / `foot_l` are the ankles' forward offsets from the hips (metres),
    which is how a stepped or staggered stance is described.
    """
    pose = Pose()
    br = math.sin(TAU * (t / 4.15 + seed * 0.13))
    shift = math.sin(TAU * (t / 9.7 + seed * 0.21)) * sway
    micro = (0.6 * math.sin(TAU * (t / 2.9 + seed)) +
             0.4 * math.sin(TAU * (t / 6.3 + seed * 2.3))) * settle

    drop = -0.10 * max(abs(foot_r), abs(foot_l))
    hip_y = (HIP_Y * h + drop - 0.004 * h / 1.72
             - 0.006 * h / 1.72 * (0.5 + 0.5 * shift))
    hip_x = 0.014 * h / 1.72 * shift
    pose.root = pose.root + np3(hip_x, hip_y - HIP_Y * h, 0.0)
    pose.root_rot = (0.015 + 0.004 * br, 0.02 * shift, -0.030 * shift)
    for side, x, fz in (("r", 0.058, foot_r), ("l", -0.058, foot_l)):
        thigh, knee, lat = leg_ik(hip_y, fz, ANKLE_Y * h, h,
                                  ankle_x=x * h - hip_x,
                                  hip_x=(0.052 if side == "r" else -0.052) * h)
        pose.set("thigh_" + side, rx=thigh, rz=lat)
        pose.set("shin_" + side, rx=knee)
        _foot(pose, side, thigh, knee, 0.0)

    # weight rolls through the pelvis and up the spine
    pose.add("pelvis", ry=0.055 * shift, rz=0.048 * shift, rx=-0.012 * micro)
    pose.add("spine", ry=-0.030 * shift, rx=-0.020 + 0.007 * br * breathe,
             rz=-0.018 * shift)
    pose.add("chest", ry=-0.020 * shift, rx=-0.014 + 0.013 * br * breathe,
             rz=-0.010 * shift)
    pose.add("neck", ry=0.030 * shift, rx=0.020 - 0.005 * br)
    pose.add("head", ry=0.020 * shift, rx=-0.012 * micro)
    for side, sgn in (("r", 1.0), ("l", -1.0)):
        _arm_chain(pose, side, 0.03 * br + 0.02 * sgn * shift,
                   -(0.13 + 0.02 * br), shoulder_out=0.012 * shift * sgn)
    return pose


def curve(t: float, keys, ease: bool = True) -> float:
    """Piecewise smooth curve through (time, value) keys — for scripted beats."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            k = (t - t0) / max(1e-6, t1 - t0)
            k = smooth(k) if ease else k
            return v0 + (v1 - v0) * k
    return keys[-1][1]


def _default_sweep(t: float) -> float:
    """A guard's slow scan: hold right, swing left, hold, swing back."""
    cycle = 7.4
    k = (t / cycle) % 1.0
    if k < 0.28:
        return 0.40
    if k < 0.42:
        return lerp(0.40, -0.34, smooth((k - 0.28) / 0.14))
    if k < 0.58:
        return -0.34
    if k < 0.72:
        return lerp(-0.34, 0.40, smooth((k - 0.58) / 0.14))
    return 0.40


def watch(t: float, h: float = 1.72, scan: float = 1.0, seed: float = 0.0,
          look_fn=None, lag: float = 0.11) -> Pose:
    """Standing guard: head leads a turn, chest arrives a beat later.

    `look_fn(t)` returns the head's target yaw in radians (positive = towards
    the figure's screen right); sample it at earlier times for the body parts
    below the head and the whole figure turns with the timing of a real neck:
    eyes/head first, shoulders following, then settling.
    """
    pose = stand(t, h=h, seed=seed)
    fn = look_fn if look_fn is not None else (lambda tt: _default_sweep(tt) * scan)
    lead = fn(t)
    lag1 = fn(t - lag)
    lag2 = fn(t - lag * 2.1)
    pose.add("neck", ry=lead * 0.52, rx=0.02 - 0.05 * abs(lead),
             rz=-0.05 * (lead - lag1) * 3.0)
    pose.add("head", ry=lead * 0.16, rx=-0.03 * abs(lead))
    pose.add("chest", ry=lag1 * 0.22, rz=-0.03 * (lead - lag1) * 3.0)
    pose.add("spine", ry=lag2 * 0.12)
    pose.add("pelvis", ry=lag2 * 0.05)
    pose.add("upperarm_r", rz=-0.022 * abs(lead))
    pose.add("upperarm_l", rz=0.022 * abs(lead))
    return pose


def warm(t: float, h: float = 1.72, seed: float = 0.0, k: float = 1.0,
         look_fn=None, lag: float = 0.12) -> Pose:
    """Hands out to the fire: a slow rub, bracing against the heat.

    The plate already has the arms out, so the arm angles here are the *bind*
    pose and only the rub and the lean vary: the motion rides on top of the
    photo instead of fighting it.
    """
    pose = stand(t, h=h, seed=seed, sway=0.55)
    pulse = math.sin(TAU * (t / 3.3 + seed))
    rub = math.sin(TAU * (t / 1.55 + seed))
    warmpose = Pose()
    warmpose.root = pose.root + np3(0.0, -0.010 * h / 1.72, 0.0)
    warmpose.root_rot = (0.055, pose.root_rot[1], pose.root_rot[2])
    for bone in ("pelvis", "spine", "chest", "neck", "head", "thigh_r", "thigh_l",
                 "shin_r", "shin_l", "foot_r", "foot_l"):
        warmpose.rot[bone] = pose.rot.get(bone, (0.0, 0.0, 0.0))
    warmpose.add("spine", rx=0.085 + 0.012 * pulse, ry=0.0)
    warmpose.add("chest", rx=0.055 + 0.008 * pulse)
    warmpose.add("neck", rx=-0.10 + 0.012 * pulse)
    # both arms reach forward and in; hands meet above the flames
    # hands rise and fall toward the heat, and rub against each other: enough
    # travel to read as movement, small enough that the plate keeps its shape
    heave = math.sin(TAU * (t / 2.6 + seed * 0.7))
    # the motion lives at the shoulder: rotating the whole arm keeps the clasped
    # hands intact (a wrist rotation would smear the plates' interlocked fingers)
    warmpose.set("upperarm_r", rx=-0.14 - 0.075 * heave - 0.018 * rub, rz=-0.20, ry=-0.10)
    warmpose.set("upperarm_l", rx=-0.14 - 0.075 * heave + 0.018 * rub, rz=0.20, ry=0.10)
    warmpose.set("forearm_r", rx=-1.28, ry=-0.08)
    warmpose.set("forearm_l", rx=-1.28, ry=0.08)
    if look_fn is not None:
        lead = look_fn(t)
        warmpose.add("neck", ry=lead * 0.55)
        warmpose.add("head", ry=lead * 0.18)
        warmpose.add("chest", ry=look_fn(t - lag) * 0.16)
        warmpose.add("spine", ry=look_fn(t - lag * 2.0) * 0.08)
    if k >= 0.999:
        return warmpose
    return blend(stand(t, h=h, seed=seed), warmpose, smooth(k * 1.12))


def reach(t: float, k: float, h: float = 1.72, seed: float = 0.0) -> Pose:
    """Stand -> hands to the fire, with an anticipatory overshoot."""
    base = stand(t, h=h, seed=seed)
    target = warm(t, h=h, seed=seed)
    ease = smooth(min(1.0, k * 1.15))
    out = blend(base, target, ease)
    overshoot = 0.09 * math.sin(math.pi * min(1.0, k)) * (1.0 - k)
    for bone in ("upperarm_r", "upperarm_l", "forearm_r", "forearm_l"):
        a = out.rot.get(bone, (0.0, 0.0, 0.0))
        out.rot[bone] = (a[0] - overshoot * 0.8, a[1], a[2])
    out.root_rot = (out.root_rot[0] + 0.035 * math.sin(math.pi * min(1.0, k)),
                    out.root_rot[1], out.root_rot[2])
    return out


def step(t: float, t_start: float, h: float = 1.72, length: float = 0.28,
         dwell: float = 0.95, seed: float = 0.0, base=None) -> tuple[Pose, float]:
    """One deliberate step forward, from stance to stance.

    Anticipation (the weight rolls back), push-off, a swinging foot that arcs
    over the ground, heel-strike, then the whole body's mass travelling over
    the new front foot. `base(t)` supplies the idle on top (breathing, head
    scan, arms), so a figure can keep watching while it steps.
    Returns (pose, forward travel in metres).
    """
    if base is None:
        def base(tt):
            return stand(tt, h=h, seed=seed)
    if t <= t_start:
        return base(t), 0.0
    tt = t - t_start
    if tt >= dwell:
        pose = base(t)
        hip_y = HIP_Y * h - 0.055 * length
        for side, fz, x in (("r", 0.0, 0.055), ("l", -length, -0.058)):
            thigh, knee, lat = leg_ik(hip_y, fz, ANKLE_Y * h, h,
                                      ankle_x=x * h,
                                      hip_x=(0.052 if side == "r" else -0.052) * h)
            pose.set("thigh_" + side, rx=thigh, rz=lat)
            pose.set("shin_" + side, rx=knee)
            _foot(pose, side, thigh, knee, 0.0)
        return pose, length
    u = tt / dwell
    pose = base(t)
    stance_hip = HIP_Y * h - 0.020 * h / 1.72

    if u < 0.18:                                  # settle back before pushing
        k = smooth(u / 0.18)
        pose.root = pose.root + np3(0.0, -0.030 * k, -0.028 * k)
        for side, x in (("r", 0.055), ("l", -0.058)):
            thigh, knee, lat = leg_ik(stance_hip - 0.030 * k, 0.0, ANKLE_Y * h, h,
                                      ankle_x=x * h,
                                      hip_x=(0.052 if side == "r" else -0.052) * h)
            pose.set("thigh_" + side, rx=thigh + 0.05 * k, rz=lat)
            pose.set("shin_" + side, rx=knee + 0.10 * k)
            _foot(pose, side, thigh, knee, 0.0)
        return pose, 0.0

    if u < 0.62:                                  # swing the right foot through
        sw = (u - 0.18) / 0.44
        e = smooth(sw)
        lift = 0.090 * h / 1.72 * math.sin(math.pi * sw) ** 0.85
        thigh, knee, lat = leg_ik(stance_hip, length * e, ANKLE_Y * h + lift, h,
                                  ankle_x=0.056 * h, hip_x=0.052 * h)
        pose.set("thigh_r", rx=thigh, rz=lat)
        pose.set("shin_r", rx=knee)
        _foot(pose, "r", thigh, knee,
              0.16 * math.sin(math.pi * sw) ** 0.7 - 0.14 * (1.0 - e))
        thigh, knee, lat = leg_ik(stance_hip + 0.012 * e, -0.045 * length * e,
                                  ANKLE_Y * h, h, ankle_x=-0.058 * h, hip_x=-0.052 * h)
        pose.set("thigh_l", rx=thigh, rz=lat)
        pose.set("shin_l", rx=knee)
        _foot(pose, "l", thigh, knee, 0.34 * math.sin(math.pi * sw) ** 2)
        swing = math.sin(math.pi * sw)
        pose.add("pelvis", ry=-0.14 * swing, rz=-0.06 * swing)
        pose.add("chest", ry=0.15 * swing)
        pose.add("neck", ry=-0.05 * swing)
        pose.add("upperarm_r", rx=-0.36 * swing)
        pose.add("upperarm_l", rx=0.36 * swing)
        pose.add("forearm_r", rx=-0.14 * swing)
        pose.root = pose.root + np3(0.0, -0.016 * swing, 0.0)
        return pose, length * 0.06 * e

    # ---- heel strike, then the weight rolls forward onto the new front foot
    lk = smooth((u - 0.62) / 0.38)
    heel = 1.0 - lk
    hip_y = stance_hip - 0.030 * h / 1.72 * heel
    for side, fz, x in (("r", length * heel, 0.055), ("l", -length * lk, -0.058)):
        thigh, knee, lat = leg_ik(hip_y, fz, ANKLE_Y * h, h,
                                  ankle_x=x * h,
                                  hip_x=(0.052 if side == "r" else -0.052) * h)
        pose.set("thigh_" + side, rx=thigh, rz=lat)
        pose.set("shin_" + side, rx=knee)
        _foot(pose, side, thigh, knee, 0.0)
    pose.root = pose.root + np3(0.0, -0.030 * h / 1.72 * heel, 0.0)
    pose.root_rot = (pose.root_rot[0] + 0.060 * heel - 0.022 * math.sin(math.pi * lk),
                     pose.root_rot[1], pose.root_rot[2])
    pose.add("chest", rx=0.05 * heel)
    pose.add("upperarm_r", rx=-0.12 * heel)
    pose.add("upperarm_l", rx=0.12 * heel)
    return pose, length * lk
