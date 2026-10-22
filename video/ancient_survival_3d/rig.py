#!/usr/bin/env python3
"""Skinned photo cards: photoreal humans with real skeletal movement.

A photo card is normally a flat billboard. Here the card is turned into a
subdivided mesh whose vertices are bound to a 15-bone skeleton (linear blend
skinning, exactly like a game character). Bones rotate in three dimensions, so
a limb can swing *out of the card plane*: legs step forward and back, arms
swing, the torso twists. Because the vertices really move in world space, the
rasteriser's depth buffer, fire light, shadows and fog all follow along.

The motion itself is written as animation principles, not sine waves:

    contact -> down -> passing -> up -> contact      (a real gait cycle)

  * stride phase drives hips, then knees, then ankles (proximal -> distal, the
    way momentum actually travels down a limb),
  * the pelvis bobs at twice the stride rate (lowest at double support) and
    sways toward whichever leg is carrying the weight,
  * shoulders counter-rotate against the hips, arms swing opposite the legs
    with a small phase lag and an elbow that lags the shoulder,
  * the head counter-rotates to stay level and leads turns by a few frames
    (anticipation), then settles (follow-through),
  * the whole body leans into acceleration and settles back when decelerating,
  * breathing, weight shifts and micro-settles keep a standing figure alive.

Public API
----------
    rig = Rig("hunter_stand")
    mesh, anchors = rig.build(pos, yaw, pose, height=1.76, gain=0.9)
    poses = walk(t, speed=...) / watch(t) / warm(t)          # dict / Pose
"""

from __future__ import annotations

import math

import numpy as np

import photopeople as PP

GRID_U = 18          # quads across the body
GRID_V = 40          # quads up the body

# --------------------------------------------------------------------- maths
def _rot(rx: float, ry: float, rz: float) -> np.ndarray:
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], float)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], float)
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], float)
    return Rz @ Ry @ Rx


def _mat(R: np.ndarray, t) -> np.ndarray:
    m = np.eye(4)
    m[:3, :3] = R
    m[:3, 3] = t
    return m


def _seg_dist(px: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distance from every point px (N,2) to segment ab in the XY plane."""
    ab = b - a
    denom = float(ab @ ab) + 1e-9
    t = np.clip(((px - a) @ ab) / denom, 0.0, 1.0)
    proj = a[None, :] + t[:, None] * ab[None, :]
    return np.linalg.norm(px - proj, axis=1)


# ------------------------------------------------------------------ skeleton
class Pose:
    """Bone rotations (radians) + root offset, in person space.

    Person space: origin between the feet, +Y up, +X to the figure's right,
    +Z forward (out of the picture). Bone rotations are applied at the bone's
    head, so `thigh` rotates the whole leg about the hip.
    """

    def __init__(self) -> None:
        self.rot: dict[str, tuple[float, float, float]] = {}
        self.root = np.zeros(3)          # metres, added to every bone
        self.root_rot = (0.0, 0.0, 0.0)  # whole-body pitch / twist / lean

    def set(self, bone: str, rx: float = 0.0, ry: float = 0.0, rz: float = 0.0) -> "Pose":
        self.rot[bone] = (rx, ry, rz)
        return self

    def add(self, bone: str, rx: float = 0.0, ry: float = 0.0, rz: float = 0.0) -> "Pose":
        a = self.rot.get(bone, (0.0, 0.0, 0.0))
        self.rot[bone] = (a[0] + rx, a[1] + ry, a[2] + rz)
        return self


BONES = [
    # name,        parent,     head (fraction of height),   tail
    ("pelvis",     None,       (0.000, 0.520), (0.000, 0.600)),
    ("spine",      "pelvis",   (0.000, 0.600), (0.000, 0.700)),
    ("chest",      "spine",    (0.000, 0.700), (0.000, 0.800)),
    ("neck",       "chest",    (0.000, 0.800), (0.000, 0.845)),
    ("head",       "neck",     (0.000, 0.845), (0.000, 0.980)),
    ("upperarm_l", "chest",    (-0.105, 0.800), (-0.128, 0.645)),
    ("forearm_l",  "upperarm_l", (-0.128, 0.645), (-0.140, 0.505)),
    ("upperarm_r", "chest",    (0.105, 0.800), (0.128, 0.645)),
    ("forearm_r",  "upperarm_r", (0.128, 0.645), (0.140, 0.505)),
    ("thigh_l",    "pelvis",   (-0.052, 0.520), (-0.058, 0.285)),
    ("shin_l",     "thigh_l",  (-0.058, 0.285), (-0.058, 0.045)),
    ("thigh_r",    "pelvis",   (0.052, 0.520), (0.058, 0.285)),
    ("shin_r",     "thigh_r",  (0.058, 0.285), (0.058, 0.045)),
    # feet: short bones at the ankle so the sole can stay flat on the ground
    ("foot_l",     "shin_l",   (-0.058, 0.045), (-0.058, 0.008)),
    ("foot_r",     "shin_r",   (0.058, 0.045), (0.058, 0.008)),
]

BONE_NAMES = [b[0] for b in BONES]
PARENT = {b[0]: b[1] for b in BONES}


class Rig:
    """Bind pose + skin weights for one photo card."""

    def __init__(self, name: str, bind=None) -> None:
        self.name = name
        # the pose the photo itself is already in: motion angles are applied as
        # deltas from it, so a plate is never double-posed (an arm that is
        # already reaching forward must not be rotated forward twice)
        self.bind = bind if bind is not None else Pose()
        c = PP.CARDS[name]
        self.W = float(c["width_m"])
        self.H = float(c["height_m"])
        self.u = c["u"]
        self.v = c["v"]
        # bind bone segments in metres, plus the bone-local rest transforms
        self.head = {}
        self.tail = {}
        for bone, _, h, t in BONES:
            self.head[bone] = np.array([h[0] * self.H, h[1] * self.H])
            self.tail[bone] = np.array([t[0] * self.H, t[1] * self.H])
        self.rest = self._fk({})

        # ---- skin weights: inverse distance to each bone segment ----------
        nu, nv = GRID_U + 1, GRID_V + 1
        uu, vv = np.meshgrid(np.linspace(0.0, 1.0, nu), np.linspace(0.0, 1.0, nv))
        self.gu = uu.ravel()
        self.gv = vv.ravel()
        px = (self.gu - 0.5) * self.W
        py = self.gv * self.H
        pts = np.stack([px, py], axis=1)
        n = pts.shape[0]
        d = np.stack([_seg_dist(pts, self.head[b], self.tail[b]) for b in BONE_NAMES],
                     axis=1)
        # sharp inverse-distance weights keep limbs crisp while joints blend
        w = 1.0 / (d ** 3.2 + 1e-4)
        # keep the four strongest influences (as a game engine would)
        order = np.argsort(-w, axis=1)
        keep = order[:, :4]
        mask = np.zeros_like(w, bool)
        np.put_along_axis(mask, keep, True, axis=1)
        w = np.where(mask, w, 0.0)
        w /= w.sum(axis=1, keepdims=True)
        # ---- garment softening -------------------------------------------
        # the tunic hangs from the hips; if the thighs own it, a stride tears
        # it in half at the crotch. Hand the leg weight back to the pelvis as
        # the skirt rises, so the cloth swings as one piece.
        leg_idx = [i for i, b in enumerate(BONE_NAMES)
                   if b.split("_")[0] in ("thigh", "shin", "foot")]
        ip = BONE_NAMES.index("pelvis")
        f = np.clip((py - 0.340 * self.H) / (0.072 * self.H), 0.0, 1.0)
        legsum = w[:, leg_idx].sum(axis=1)
        w[:, leg_idx] *= (1.0 - f)[:, None]
        w[:, ip] += legsum * f
        w /= np.maximum(w.sum(axis=1, keepdims=True), 1e-9)

        # feet: the sole must belong to the foot bone alone, otherwise the
        # ankle counter-rotation is diluted and the foot floats off the ground
        below = (0.064 * self.H - py) / (0.020 * self.H)
        ff = np.clip(below, 0.0, 1.0) ** 0.7
        ir = BONE_NAMES.index("foot_r")
        il = BONE_NAMES.index("foot_l")
        side_r = (px > 0.0).astype(float)
        w = w * (1.0 - ff[:, None])
        w[:, ir] += ff * side_r
        w[:, il] += ff * (1.0 - side_r)
        w /= w.sum(axis=1, keepdims=True)
        self.weights = w                       # (N, nbones)
        # the bind position of every vertex, in person space (z = 0)
        self.bindpos = np.stack([px, py, np.zeros_like(px)], axis=1)

    # ------------------------------------------------------------------ FK
    def _fk(self, rot: dict[str, tuple[float, float, float]]) -> dict[str, np.ndarray]:
        world: dict[str, np.ndarray] = {}
        for bone in BONE_NAMES:
            parent = PARENT[bone]
            head = self.head[bone]
            local_rot = _rot(*rot.get(bone, (0.0, 0.0, 0.0)))
            if parent is None:
                world[bone] = _mat(local_rot, (head[0], head[1], 0.0))
            else:
                pw = world[parent]
                ph = self.head[parent]
                # translate from the parent joint to this joint, then rotate
                world[bone] = pw @ _mat(np.eye(3), (head[0] - ph[0], head[1] - ph[1], 0.0)) \
                    @ _mat(local_rot, np.zeros(3))
        return world

    def deform(self, pose: Pose, ground: bool = True) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        """Skinned vertex positions in person space + bone transforms."""
        rot = {}
        for bone in set(pose.rot) | set(self.bind.rot):
            a = pose.rot.get(bone, (0.0, 0.0, 0.0))
            b = self.bind.rot.get(bone, (0.0, 0.0, 0.0))
            rot[bone] = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
        world = self._fk(rot)
        # root motion: translate + whole-body rotation about the feet centre
        root_off = np.asarray(pose.root, float) - np.asarray(self.bind.root, float)
        root_euler = tuple(pose.root_rot[i] - self.bind.root_rot[i] for i in range(3))
        root_rot = _rot(*root_euler)
        root = _mat(root_rot, root_off)
        acc = np.zeros_like(self.bindpos)
        for i, bone in enumerate(BONE_NAMES):
            w = self.weights[:, i:i + 1]
            if not np.any(w > 1e-5):
                continue
            rest = self.rest[bone]
            cur = world[bone]
            # bone transform relative to bind, then the root transform
            m = root @ cur @ np.linalg.inv(rest)
            p = (m[:3, :3] @ self.bindpos.T).T + m[:3, 3]
            acc += w * p
        anchors = {}
        for bone in BONE_NAMES:
            m = root @ world[bone]
            t3 = np.append(self.tail[bone] - self.head[bone], 0.0)
            anchors[bone] = m[:3, :3] @ t3 + m[:3, 3]
            anchors[bone + "_head"] = m[:3, 3].copy()
        if ground:
            # never let a sole sink through the floor: the planted foot is the
            # lowest point, so lifting by that amount keeps contact exact
            low = float(acc[:, 1].min())
            if abs(low) > 1e-4:
                acc[:, 1] -= low
                for key in anchors:
                    anchors[key] = anchors[key] - np.array([0.0, low, 0.0])
        return acc, anchors

    # ---------------------------------------------------------------- build
    def build(self, b, pos, yaw: float, pose: Pose, height: float | None = None,
              gain: float = 0.9, tint: float = 0.0, contact_shadow: bool = True,
              shadow_strength: float = 0.5):
        """Emit the deformed card into `b`; returns world anchors."""
        verts, anchors = self.deform(pose)
        k = 1.0 if height is None else height / self.H
        x, y, z = (float(v) for v in pos)
        dx, dz = math.sin(yaw), math.cos(yaw)
        side = np.array([dz, 0.0, -dx])          # image right, in world
        up = np.array([0.0, 1.0, 0.0])
        fwd = np.array([dx, 0.0, dz])            # the card's normal

        wp = (np.array([x, y, z])[None, :]
              + side[None, :] * verts[:, 0:1] * k
              + up[None, :] * verts[:, 1:2] * k
              + fwd[None, :] * verts[:, 2:3] * k)

        # per-vertex normals of the *deformed* surface: a swinging limb really
        # does turn its lit side away, so the shading follows the silhouette
        nu, nv = GRID_U + 1, GRID_V + 1
        grid = wp.reshape(nv, nu, 3)
        gnorm = np.zeros_like(grid)
        du = grid[:, 1:] - grid[:, :-1]
        dv = grid[1:, :] - grid[:-1, :]
        quad_n = np.cross(du[:-1], dv[:, :-1])            # (nv-1, nu-1, 3)
        ln = np.linalg.norm(quad_n, axis=2, keepdims=True)
        quad_n = np.where(ln > 1e-9, quad_n / np.maximum(ln, 1e-9), fwd[None, None, :])
        gnorm[:-1, :-1] += quad_n
        gnorm[:-1, 1:] += quad_n
        gnorm[1:, :-1] += quad_n
        gnorm[1:, 1:] += quad_n
        ln = np.linalg.norm(gnorm, axis=2, keepdims=True)
        gnorm = np.where(ln > 1e-9, gnorm / np.maximum(ln, 1e-9), fwd[None, None, :])
        vnormals = gnorm.reshape(-1, 3)

        b.mat = PP.MAT_CARD
        base = len(b.v)
        for i in range(len(wp)):
            u = self.u[0] + (self.u[1] - self.u[0]) * self.gu[i]
            v = self.v[1] - (self.v[1] - self.v[0]) * self.gv[i]
            b.v.append(wp[i])
            b.n.append(vnormals[i])
            # the blue channel carries the card-local u for the body shading
            b.c.append(np.array([gain, tint, float(self.gu[i])]))
            b.e.append(np.zeros(3))
            b.uv.append((float(u), float(v)))
            b.m.append(PP.MAT_CARD)
        for j in range(GRID_V):
            for i in range(GRID_U):
                a = base + j * nu + i
                c = a + 1
                d = a + nu
                e = d + 1
                b.t.append((a, c, e))       # CCW seen from +Z (front)
                b.t.append((a, e, d))
        if contact_shadow:
            PP.add_card_shadow(b, self.name, pos, yaw, height=height,
                               strength=shadow_strength)
        out = {}
        for key, p in anchors.items():
            out[key] = np.array([x, y, z]) + side * p[0] * k + up * p[1] * k + fwd * p[2] * k
        out["head"] = 0.5 * (out["head_head"] + out["head"])
        out["mouth"] = out["head_head"] + fwd * 0.09 - up * 0.035
        return out
