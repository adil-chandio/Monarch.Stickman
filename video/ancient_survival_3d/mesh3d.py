"""Procedural 3D geometry, humanoid rig and environments for the survival reel.

Everything here is generated: triangles, normals, vertex colours and emission.
No images, textures or pre-made models are read. The renderer in `raster.c`
consumes the buffers produced here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


# --------------------------------------------------------------------- maths
def rot_x(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[:3, :3] = [[1, 0, 0], [0, c, -s], [0, s, c]]
    return m


def rot_y(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[:3, :3] = [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return m


def rot_z(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    return m


def translation(v) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = v
    return m


def make_transform(pos=(0, 0, 0), yaw=0.0, pitch=0.0, roll=0.0, scale=1.0) -> np.ndarray:
    m = np.eye(4)
    r = rot_y(yaw) @ rot_x(pitch) @ rot_z(roll)
    m[:3, :3] = r[:3, :3] * scale
    m[:3, 3] = pos
    return m


# ------------------------------------------------------------------- builder
class Builder:
    """Accumulates triangles with per-vertex colour and emission."""

    def __init__(self) -> None:
        self.v: list[np.ndarray] = []
        self.n: list[np.ndarray] = []
        self.c: list[np.ndarray] = []
        self.e: list[np.ndarray] = []
        self.t: list[tuple[int, int, int]] = []

    # ---- primitives -----------------------------------------------------
    def tri(self, a, b, c, colour, normal=None, emission=(0, 0, 0)) -> None:
        base = len(self.v)
        if normal is None:
            normal = np.cross(np.subtract(b, a), np.subtract(c, a))
            length = np.linalg.norm(normal)
            normal = normal / length if length > 1e-9 else np.array([0, 1, 0], float)
        for p in (a, b, c):
            self.v.append(np.asarray(p, float))
            self.n.append(np.asarray(normal, float))
            self.c.append(np.asarray(colour, float))
            self.e.append(np.asarray(emission, float))
        self.t.append((base, base + 1, base + 2))

    def quad(self, a, b, c, d, colour, emission=(0, 0, 0)) -> None:
        self.tri(a, b, c, colour, emission=emission)
        self.tri(a, c, d, colour, emission=emission)

    def box(self, centre, size, colour, yaw=0.0, emission=(0, 0, 0)) -> None:
        cx, cy, cz = centre
        sx, sy, sz = (s / 2 for s in size)
        rot = rot_y(yaw)[:3, :3]
        corners = []
        for i in (-1, 1):
            for j in (-1, 1):
                for k in (-1, 1):
                    corners.append(np.array([i * sx, j * sy, k * sz]) @ rot.T + np.array([cx, cy, cz]))
        faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
                 (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
        for f in faces:
            self.tri(corners[f[0]], corners[f[1]], corners[f[2]], colour, emission=emission)

    def capsule(self, a, b, ra, rb, colour, rings: int = 5, seg: int = 7,
                emission=(0, 0, 0), taper_power: float = 1.0) -> None:
        """Tapered tube with rounded caps: the basic limb / torso volume."""
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        axis = b - a
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return
        d = axis / length
        helper = np.array([0.0, 1.0, 0.0]) if abs(d[1]) < 0.92 else np.array([1.0, 0.0, 0.0])
        u = np.cross(d, helper)
        u /= np.linalg.norm(u)
        w = np.cross(d, u)
        grid = []
        # cap rings, body rings, cap rings
        for i in range(rings + 1):
            t = i / rings
            r = (ra + (rb - ra) * t) * (0.80 + 0.20 * math.sin(math.pi * t) ** 0.5)
            centre = a + axis * t
            ring = []
            for j in range(seg):
                ang = 2 * math.pi * j / seg
                ring.append(centre + (u * math.cos(ang) + w * math.sin(ang)) * r)
            grid.append(ring)
        # top cap
        tip_a = a - d * ra * 0.85
        tip_b = b + d * rb * 0.85
        for j in range(seg):
            j2 = (j + 1) % seg
            self.tri(tip_a, grid[0][j2], grid[0][j], colour, emission=emission)
            self.tri(tip_b, grid[-1][j], grid[-1][j2], colour, emission=emission)
        for i in range(rings):
            for j in range(seg):
                j2 = (j + 1) % seg
                self.quad(grid[i][j], grid[i][j2], grid[i + 1][j2], grid[i + 1][j],
                          colour, emission=emission)

    def sphere(self, centre, radius, colour, rings: int = 8, seg: int = 10,
               scale=(1, 1, 1), emission=(0, 0, 0), squash=0.0) -> None:
        cx, cy, cz = centre
        sx, sy, sz = scale
        grid = []
        for i in range(rings + 1):
            phi = math.pi * i / rings
            row = []
            for j in range(seg):
                th = 2 * math.pi * j / seg
                wobble = 1.0 + squash * math.sin(3 * th + 1.1) * math.sin(2 * phi)
                row.append(np.array([cx + radius * sx * math.sin(phi) * math.cos(th) * wobble,
                                     cy + radius * sy * math.cos(phi) * wobble,
                                     cz + radius * sz * math.sin(phi) * math.sin(th) * wobble]))
            grid.append(row)
        for i in range(rings):
            for j in range(seg):
                j2 = (j + 1) % seg
                self.quad(grid[i][j], grid[i][j2], grid[i + 1][j2], grid[i + 1][j], colour,
                          emission=emission)

    def cone(self, base_centre, radius, height, colour, seg: int = 8,
             emission=(0, 0, 0), lean=(0.0, 0.0)) -> None:
        bx, by, bz = base_centre
        apex = np.array([bx + lean[0], by + height, bz + lean[1]])
        ring = [np.array([bx + radius * math.cos(2 * math.pi * j / seg), by,
                          bz + radius * math.sin(2 * math.pi * j / seg)]) for j in range(seg)]
        for j in range(seg):
            j2 = (j + 1) % seg
            self.tri(ring[j], ring[j2], apex, colour, emission=emission)
            self.tri(np.array([bx, by, bz]), ring[j2], ring[j], colour, emission=emission)

    def ground(self, size: float, cells: int, height_fn, colour_fn) -> None:
        """Displaced grid; flat enough to stand on, rolling enough to feel real."""
        step = size / cells
        pts = np.zeros((cells + 1, cells + 1, 3))
        for i in range(cells + 1):
            for j in range(cells + 1):
                x = -size / 2 + i * step
                z = -size / 2 + j * step
                pts[i, j] = (x, height_fn(x, z), z)
        for i in range(cells):
            for j in range(cells):
                a, b, c, d = pts[i, j], pts[i + 1, j], pts[i + 1, j + 1], pts[i, j + 1]
                colour = colour_fn((a[0] + c[0]) / 2, (a[2] + c[2]) / 2, (a[1] + c[1]) / 2)
                self.quad(a, d, c, b, colour)

    # ---- output ---------------------------------------------------------
    def arrays(self, jitter: float = 0.022):
        v = np.asarray(self.v, np.float32) if self.v else np.zeros((0, 3), np.float32)
        n = np.asarray(self.n, np.float32) if self.n else np.zeros((0, 3), np.float32)
        c = np.asarray(self.c, np.float32) if self.c else np.zeros((0, 3), np.float32)
        e = np.asarray(self.e, np.float32) if self.e else np.zeros((0, 3), np.float32)
        t = np.asarray(self.t, np.int32) if self.t else np.zeros((0, 3), np.int32)
        if jitter > 0 and len(c) and len(t):
            # per-triangle tonal noise: breaks up flat facets like brush work
            rng = np.random.default_rng(7)
            k = (1.0 + rng.normal(0.0, jitter, len(t))).astype(np.float32)
            c = c.copy()
            c[t.reshape(-1)] *= np.repeat(k, 3)[:, None]
            np.clip(c, 0.0, 1.6, out=c)
        return v, n, c, e, t


# ----------------------------------------------------------------------- rig
@dataclass
class Joint:
    name: str
    parent: str | None
    offset: tuple[float, float, float]
    length: float


@dataclass
class Bone:
    name: str
    joints: tuple[str, str]
    radius: tuple[float, float]
    colour: tuple[float, float, float]


# Proportions are in metres; the whole rig is roughly 1.75 m tall.
SKELETON = [
    Joint("pelvis", None, (0, 0.94, 0), 0.0),
    Joint("spine", "pelvis", (0, 0.20, 0), 0.20),
    Joint("chest", "spine", (0, 0.24, 0), 0.24),
    Joint("neck", "chest", (0, 0.20, 0), 0.12),
    Joint("head", "neck", (0, 0.12, 0), 0.22),
    Joint("shoulder_l", "chest", (-0.20, 0.14, 0), 0.28),
    Joint("elbow_l", "shoulder_l", (0, -0.28, 0), 0.26),
    Joint("wrist_l", "elbow_l", (0, -0.26, 0), 0.10),
    Joint("shoulder_r", "chest", (0.20, 0.14, 0), 0.28),
    Joint("elbow_r", "shoulder_r", (0, -0.28, 0), 0.26),
    Joint("wrist_r", "elbow_r", (0, -0.26, 0), 0.10),
    Joint("hip_l", "pelvis", (-0.105, -0.04, 0), 0.44),
    Joint("knee_l", "hip_l", (0, -0.44, 0), 0.42),
    Joint("ankle_l", "knee_l", (0, -0.42, 0), 0.09),
    Joint("hip_r", "pelvis", (0.105, -0.04, 0), 0.44),
    Joint("knee_r", "hip_r", (0, -0.44, 0), 0.42),
    Joint("ankle_r", "knee_r", (0, -0.42, 0), 0.09),
]

BONES = [
    Bone("pelvis", ("pelvis", "spine"), (0.155, 0.145), (0.52, 0.36, 0.24)),
    Bone("spine", ("spine", "chest"), (0.155, 0.175), (0.56, 0.39, 0.26)),
    Bone("chest", ("chest", "neck"), (0.175, 0.085), (0.58, 0.41, 0.27)),
    Bone("neck", ("neck", "head"), (0.060, 0.058), (0.72, 0.52, 0.36)),
    Bone("upperarm_l", ("shoulder_l", "elbow_l"), (0.062, 0.050), (0.67, 0.47, 0.31)),
    Bone("forearm_l", ("elbow_l", "wrist_l"), (0.050, 0.038), (0.70, 0.49, 0.32)),
    Bone("upperarm_r", ("shoulder_r", "elbow_r"), (0.062, 0.050), (0.67, 0.47, 0.31)),
    Bone("forearm_r", ("elbow_r", "wrist_r"), (0.050, 0.038), (0.70, 0.49, 0.32)),
    Bone("thigh_l", ("hip_l", "knee_l"), (0.082, 0.058), (0.63, 0.44, 0.29)),
    Bone("shin_l", ("knee_l", "ankle_l"), (0.058, 0.036), (0.66, 0.46, 0.30)),
    Bone("thigh_r", ("hip_r", "knee_r"), (0.082, 0.058), (0.63, 0.44, 0.29)),
    Bone("shin_r", ("knee_r", "ankle_r"), (0.058, 0.036), (0.66, 0.46, 0.30)),
]


class Rig:
    """Forward kinematics for the procedural humanoid."""

    def __init__(self) -> None:
        self.joints = {j.name: j for j in SKELETON}

    def solve(self, pose: dict[str, tuple[float, float, float]],
              root=(0, 0, 0), yaw=0.0, scale=1.0, lean=(0.0, 0.0)) -> dict[str, np.ndarray]:
        world: dict[str, np.ndarray] = {}
        root_m = make_transform(root, yaw=yaw, scale=scale)
        for joint in SKELETON:
            m = np.eye(4)
            angles = pose.get(joint.name, (0.0, 0.0, 0.0))
            if joint.parent is None:
                m = root_m @ translation(joint.offset)
            else:
                m = world[joint.parent] @ translation(joint.offset) @ _euler(angles)
                if joint.name in ("spine", "chest"):
                    m = world[joint.parent] @ translation(joint.offset) @ rot_x(lean[0]) @ rot_z(lean[1]) @ _euler(angles)
            world[joint.name] = m
        return world

    def mesh(self, b: Builder, world: dict[str, np.ndarray],
             palette: dict[str, tuple[float, float, float]] | None = None,
             hair: tuple[float, float, float] = (0.10, 0.08, 0.07),
             tunic: tuple[float, float, float] = (0.55, 0.34, 0.13),
             skin: tuple[float, float, float] = (0.80, 0.58, 0.40),
             grey_hair: bool = False, kind: str = "man") -> None:
        p = {bone.name: bone.colour for bone in BONES}
        if palette:
            p.update(palette)
        for bone in BONES:
            a = world[bone.joints[0]][:3, 3]
            bpos = world[bone.joints[1]][:3, 3]
            shade = p[bone.name]
            b.capsule(a, bpos, bone.radius[0], bone.radius[1], shade, rings=5, seg=8)
        # ---- head: skull, face planes, eyes, brows, nose, mouth, ears, hair ----
        head = world["head"][:3, 3]
        fwd = _facing(world)
        side = np.array([fwd[2], 0.0, -fwd[0]])
        up = np.array([0.0, 1.0, 0.0])

        def hp(sx: float, sy: float, sz: float) -> np.ndarray:
            return head + side * sx + up * sy + fwd * sz

        hair_col = (0.66, 0.65, 0.63) if grey_hair else hair
        hair_dark = tuple(c * 0.72 for c in hair_col)
        lip_col = (skin[0] * 0.86, skin[1] * 0.52, skin[2] * 0.48)
        shade_skin = (skin[0] * 0.80, skin[1] * 0.66, skin[2] * 0.62)

        # cranial mass, face plate and tapered jaw give a real head silhouette
        b.sphere(hp(0, 0.018, -0.010), 0.105, skin, rings=12, seg=16,
                 scale=(0.93, 1.06, 0.99))
        b.sphere(hp(0, -0.028, 0.040), 0.078, skin, rings=9, seg=14,
                 scale=(0.90, 0.88, 0.84))
        b.sphere(hp(0, -0.082, 0.034), 0.056, skin, rings=8, seg=12,
                 scale=(0.78, 0.64, 0.84))
        b.sphere(hp(0, -0.092, 0.060), 0.024, skin, rings=6, seg=9,
                 scale=(1.10, 0.85, 0.92))
        for sd in (-1, 1):
            b.sphere(hp(sd * 0.052, -0.024, 0.052), 0.022, skin, rings=6, seg=9,
                     scale=(1.05, 0.85, 0.72))

        # brow ridge + glabella
        b.capsule(hp(-0.046, 0.026, 0.076), hp(0.046, 0.026, 0.076), 0.010, 0.010,
                  skin, rings=4, seg=7)
        b.sphere(hp(0, 0.023, 0.080), 0.012, skin, rings=5, seg=8, scale=(1.2, 0.8, 0.7))

        # nose: bridge, tip, wings and dark nostrils
        b.capsule(hp(0, 0.012, 0.076), hp(0, -0.010, 0.088), 0.010, 0.013, skin,
                  rings=4, seg=8)
        b.sphere(hp(0, -0.013, 0.090), 0.0135, skin, rings=6, seg=9,
                 scale=(1.0, 0.85, 0.95))
        for sd in (-1, 1):
            b.sphere(hp(sd * 0.012, -0.019, 0.086), 0.0075, skin, rings=5, seg=7,
                     scale=(0.9, 0.8, 0.8))
            b.sphere(hp(sd * 0.008, -0.023, 0.087), 0.0040, (0.28, 0.18, 0.14),
                     rings=4, seg=6)

        # eyes: socket shadow, sclera, iris, pupil, glint, lids
        for sd in (-1, 1):
            b.sphere(hp(sd * 0.035, -0.002, 0.068), 0.026, shade_skin, rings=6, seg=10,
                     scale=(1.0, 0.92, 0.72))
            b.sphere(hp(sd * 0.035, -0.002, 0.080), 0.0148, (0.84, 0.82, 0.78),
                     rings=6, seg=10, scale=(1.0, 0.80, 0.68))
            b.sphere(hp(sd * 0.035, -0.002, 0.0902), 0.0074, (0.24, 0.14, 0.07),
                     rings=5, seg=9, scale=(1.0, 1.0, 0.5))
            b.sphere(hp(sd * 0.035, -0.002, 0.0928), 0.0036, (0.03, 0.02, 0.02),
                     rings=4, seg=7, scale=(1.0, 1.0, 0.45))
            b.sphere(hp(sd * 0.040, 0.001, 0.0940), 0.0022, (1.0, 0.98, 0.94),
                     rings=3, seg=6, emission=(0.7, 0.7, 0.66))
            b.sphere(hp(sd * 0.035, 0.006, 0.081), 0.0155, skin, rings=5, seg=9,
                     scale=(1.05, 0.40, 0.60))
            b.sphere(hp(sd * 0.035, -0.015, 0.081), 0.0135, skin, rings=5, seg=9,
                     scale=(1.0, 0.30, 0.55))
            b.capsule(hp(sd * 0.014, 0.026, 0.086), hp(sd * 0.050, 0.024, 0.079),
                      0.0052, 0.0042, hair_dark, rings=3, seg=6)

        # mouth: upper lip, lower lip, shadow line
        b.capsule(hp(-0.017, -0.044, 0.082), hp(0.017, -0.044, 0.082), 0.0060, 0.0060,
                  lip_col, rings=4, seg=7)
        b.sphere(hp(0, -0.053, 0.080), 0.0125, lip_col, rings=5, seg=9,
                 scale=(1.45, 0.50, 0.55))
        b.box(hp(0, -0.048, 0.086), (0.030, 0.0034, 0.010), (0.24, 0.12, 0.10),
              yaw=math.atan2(fwd[0], fwd[2]))

        # ears with lobes
        for sd in (-1, 1):
            b.sphere(hp(sd * 0.095, -0.008, 0.000), 0.027, skin, rings=6, seg=9,
                     scale=(0.26, 0.95, 0.70))
            b.sphere(hp(sd * 0.093, -0.026, 0.002), 0.011, skin, rings=4, seg=7,
                     scale=(0.5, 0.8, 0.7))

        # ---- hair: cap, hairline sweep, back mass, braid / beard ----
        b.sphere(hp(0, 0.030, -0.020), 0.110, hair_col, rings=11, seg=15,
                 scale=(1.00, 1.02, 1.00))
        b.sphere(hp(0, -0.004, -0.066), 0.092, hair_col, rings=8, seg=12,
                 scale=(1.0, 0.98, 0.72))
        b.sphere(hp(0, 0.056, 0.052), 0.070, hair_col, rings=6, seg=12,
                 scale=(1.32, 0.42, 0.62))
        for sd in (-1, 1):
            b.capsule(hp(sd * 0.070, 0.050, 0.034), hp(sd * 0.086, -0.010, 0.006),
                      0.022, 0.015, hair_col, rings=4, seg=7)
            b.capsule(hp(sd * 0.082, 0.000, 0.022), hp(sd * 0.086, -0.068, -0.014),
                      0.021, 0.015, hair_col, rings=4, seg=7)
        if kind == "woman":
            b.capsule(hp(0, -0.052, -0.104), hp(0, -0.230, -0.108), 0.038, 0.019,
                      hair_col, rings=5, seg=9)
            b.sphere(hp(0, -0.242, -0.108), 0.022, hair_col, rings=4, seg=7)
        elif kind == "elder":
            b.capsule(hp(0, -0.060, -0.096), hp(0, -0.150, -0.104), 0.032, 0.019,
                      hair_col, rings=4, seg=8)
            for sd in (-1, 1):
                b.capsule(hp(sd * 0.028, -0.086, 0.058), hp(sd * 0.018, -0.158, 0.066),
                          0.024, 0.015, hair_col, rings=4, seg=7)
            b.capsule(hp(-0.026, -0.050, 0.080), hp(0.026, -0.050, 0.080), 0.0070,
                      0.0070, hair_col, rings=3, seg=6)
        else:
            b.capsule(hp(0, -0.052, -0.102), hp(0, -0.120, -0.100), 0.028, 0.015,
                      hair_col, rings=4, seg=7)

        # neck + trapezius blend
        neck_top = world["neck"][:3, 3]
        b.capsule(neck_top + np.array([0, 0.02, 0]), hp(0, -0.070, 0.006), 0.052, 0.048,
                  skin, rings=4, seg=9)
        for sd in (-1, 1):
            b.sphere(hp(sd * 0.115, -0.190, 0.006), 0.062, skin, rings=5, seg=8,
                     scale=(1.2, 0.7, 0.9))

        # ---- torso: one smooth hide tunic from thigh to collarbone ----
        chest = world["chest"][:3, 3]
        pelvis = world["pelvis"][:3, 3]
        hip = pelvis + np.array([0, -0.16, 0])
        b.capsule(hip + np.array([0, -0.02, 0]), chest + np.array([0, 0.05, 0]),
                  0.170, 0.152, tunic, rings=7, seg=16, taper_power=0.6)
        # hide hem sits over the thighs like a short skirt
        b.capsule(hip + np.array([0, 0.06, 0]), hip - np.array([0, 0.10, 0]), 0.168, 0.176,
                  tunic, rings=2, seg=16)
        # kneeling/sitting support: a folded calf volume that reaches the floor
        for side in ("l", "r"):
            knee = world[f"knee_{side}"][:3, 3]
            ankle = world[f"ankle_{side}"][:3, 3]
            fold = (knee + ankle) / 2 + np.array([0, -0.055, 0])
            b.capsule(knee, fold, 0.062, 0.070, skin if not tunic else skin, rings=3, seg=7)
        # ---- hands and feet ----
        for side in ("l", "r"):
            wrist = world[f"wrist_{side}"][:3, 3]
            m = world[f"elbow_{side}"]
            hand_dir = wrist - m[:3, 3]
            n_ = np.linalg.norm(hand_dir)
            hand_dir = hand_dir / n_ if n_ > 1e-6 else np.array([0, -1.0, 0])
            b.capsule(wrist, wrist + hand_dir * 0.085, 0.042, 0.030, skin, rings=3, seg=7)
            ankle = world[f"ankle_{side}"][:3, 3]
            toe = ankle + fwd * 0.16 - np.array([0, 0.062, 0])
            b.capsule(ankle - np.array([0, 0.045, 0]) - fwd * 0.03, toe, 0.052, 0.038,
                      skin, rings=3, seg=7)


def _facing(world) -> np.ndarray:
    """Unit forward vector of the chest, so face details follow body yaw."""
    m = world["chest"]
    f = np.array([m[0, 2], 0.0, m[2, 2]])
    n = np.linalg.norm(f)
    return f / n if n > 1e-6 else np.array([0.0, 0.0, 1.0])


def _euler(angles) -> np.ndarray:
    x, y, z = angles
    m = np.eye(4)
    m[:3, :3] = (rot_y(y) @ rot_x(x) @ rot_z(z))[:3, :3]
    return m


# --------------------------------------------------------------------- poses
def pose_idle(t: float) -> dict[str, tuple[float, float, float]]:
    breathe = math.sin(t * 2.1) * 0.03
    return {
        "spine": (breathe, 0, 0), "chest": (-breathe * 0.5, 0, 0),
        "shoulder_l": (0.05, 0, -0.26), "shoulder_r": (0.05, 0, 0.26),
        "elbow_l": (-0.28, 0, 0), "elbow_r": (-0.28, 0, 0),
        "hip_l": (0.03, 0, 0.03), "hip_r": (-0.03, 0, -0.03),
        "knee_l": (0.03, 0, 0), "knee_r": (0.03, 0, 0),
        "neck": (math.sin(t * 0.7) * 0.05, math.sin(t * 0.5) * 0.18, 0),
    }


def pose_walk(phase: float) -> dict[str, tuple[float, float, float]]:
    """Four-key walk: contact, passing, opposite contact, passing."""
    s = math.sin(2 * math.pi * phase)
    c = math.cos(2 * math.pi * phase)
    swing = 0.62
    lift = max(0.0, math.sin(2 * math.pi * phase)) * 0.75
    lift_o = max(0.0, -math.sin(2 * math.pi * phase)) * 0.75
    return {
        "pelvis": (0.02, 0, math.sin(4 * math.pi * phase) * 0.03),
        "spine": (0.06, math.sin(2 * math.pi * phase) * 0.06, 0),
        "chest": (-0.02, -math.sin(2 * math.pi * phase) * 0.10, 0),
        "neck": (0.02, 0, 0),
        "hip_l": (-swing * s, 0, 0.02),
        "knee_l": (max(0.06, lift * 1.1), 0, 0),
        "ankle_l": (-0.15 * s, 0, 0),
        "hip_r": (swing * s, 0, -0.02),
        "knee_r": (max(0.06, lift_o * 1.1), 0, 0),
        "ankle_r": (0.15 * s, 0, 0),
        "shoulder_l": (swing * 0.85 * s, 0, -0.22),
        "elbow_l": (-0.35 - 0.18 * s, 0, 0),
        "shoulder_r": (-swing * 0.85 * s, 0, 0.22),
        "elbow_r": (-0.35 + 0.18 * s, 0, 0),
    }


def pose_point(t: float) -> dict[str, tuple[float, float, float]]:
    p = pose_idle(t)
    p.update({
        "shoulder_r": (-2.35 + math.sin(t * 2.2) * 0.10, 0.25, 0.30),
        "elbow_r": (-0.12, 0, 0),
        "shoulder_l": (0.15, 0, -0.22),
        "elbow_l": (-0.55, 0, 0),
        "chest": (0, 0.16, 0),
        "hip_r": (-0.10, 0, 0),
    })
    return p


def pose_crouch(t: float) -> dict[str, tuple[float, float, float]]:
    work = math.sin(t * 6.5) * 0.16
    return {
        "pelvis": (0.34, 0, 0),
        "spine": (0.32, 0, 0), "chest": (0.22, 0, 0), "neck": (-0.45, 0, 0),
        "hip_l": (-1.35, 0, 0.22), "knee_l": (2.05, 0, 0), "ankle_l": (-0.80, 0, 0),
        "hip_r": (-1.20, 0, -0.26), "knee_r": (1.95, 0, 0), "ankle_r": (-0.72, 0, 0),
        "shoulder_l": (-0.95 - work, 0, -0.40), "elbow_l": (-1.15 + work, 0, 0),
        "shoulder_r": (-1.05 + work, 0, 0.40), "elbow_r": (-1.05 - work, 0, 0),
    }


def pose_warm(t: float) -> dict[str, tuple[float, float, float]]:
    """Standing at the fire, hands held out to the flames."""
    sway = math.sin(t * 1.6) * 0.05
    rub = math.sin(t * 3.1) * 0.06
    return {
        "pelvis": (0.04, 0, sway * 0.4),
        "spine": (0.10, sway * 0.5, 0), "chest": (0.04, -sway * 0.4, 0),
        "neck": (-0.14, 0, 0),
        "hip_l": (-0.12, 0, 0.10), "knee_l": (0.16, 0, 0), "ankle_l": (-0.05, 0, 0),
        "hip_r": (-0.06, 0, -0.10), "knee_r": (0.10, 0, 0), "ankle_r": (-0.03, 0, 0),
        "shoulder_l": (-0.95 + rub, 0.10, -0.24), "elbow_l": (-0.85 - rub, 0, 0),
        "shoulder_r": (-0.92 - rub, -0.10, 0.24), "elbow_r": (-0.88 + rub, 0, 0),
    }


def pose_knap(t: float) -> dict[str, tuple[float, float, float]]:
    """Crouched knapper: holds the core in the left hand, strikes with the right."""
    beat = math.sin(t * 7.0)
    return {
        "pelvis": (1.25, 0, 0), "spine": (-0.05, 0, 0), "chest": (0.18, 0, 0),
        "neck": (-0.30, 0, 0),
        "hip_l": (-1.55, 0, 0.30), "knee_l": (2.25, 0, 0), "ankle_l": (-0.60, 0, 0),
        "hip_r": (-1.48, 0, -0.34), "knee_r": (2.20, 0, 0), "ankle_r": (-0.58, 0, 0),
        "shoulder_l": (-1.15, 0.10, -0.35), "elbow_l": (-0.75, 0, 0),
        "shoulder_r": (-1.05 - 0.45 * max(0.0, beat), -0.10, 0.55),
        "elbow_r": (-1.25 + 0.35 * max(0.0, beat), 0, 0),
    }


def pose_pick(t: float) -> dict[str, tuple[float, float, float]]:
    reach = 0.5 + 0.5 * math.sin(t * 2.6)
    return {
        "pelvis": (0.20, 0, 0),
        "spine": (0.26 + 0.10 * reach, 0, 0), "chest": (0.10, -0.18, 0),
        "neck": (-0.30, 0.22, 0),
        "hip_l": (-1.05, 0, 0.16), "knee_l": (1.55, 0, 0), "ankle_l": (-0.52, 0, 0),
        "hip_r": (-0.95, 0, -0.18), "knee_r": (1.45, 0, 0), "ankle_r": (-0.48, 0, 0),
        "shoulder_r": (-1.15 - 0.55 * reach, 0.18, 0.34),
        "elbow_r": (-0.55 + 0.30 * reach, 0, 0),
        "shoulder_l": (-0.55, 0, -0.24), "elbow_l": (-0.75, 0, 0),
    }


def pose_sit_warm(t: float) -> dict[str, tuple[float, float, float]]:
    rub = math.sin(t * 5.0) * 0.10
    return {
        "pelvis": (1.20, 0, 0), "spine": (-0.10, 0, 0), "chest": (0.28, 0, 0),
        "neck": (-0.30, 0, 0),
        "hip_l": (-1.55, 0, 0.34), "knee_l": (2.35, 0, 0), "ankle_l": (-0.55, 0, 0),
        "hip_r": (-1.55, 0, -0.34), "knee_r": (2.35, 0, 0), "ankle_r": (-0.55, 0, 0),
        "shoulder_l": (-1.35 + rub, 0.22, -0.62), "elbow_l": (-1.05 - rub, 0, 0),
        "shoulder_r": (-1.35 - rub, -0.22, 0.62), "elbow_r": (-1.05 + rub, 0, 0),
    }


def pose_sit_tend(t: float) -> dict[str, tuple[float, float, float]]:
    stir = math.sin(t * 1.7) * 0.16
    return {
        "pelvis": (1.15, 0, 0), "spine": (-0.02, 0, 0), "chest": (0.20, 0, 0),
        "neck": (-0.18, 0, 0),
        "hip_l": (-1.50, 0, 0.30), "knee_l": (2.30, 0, 0), "ankle_l": (-0.50, 0, 0),
        "hip_r": (-1.50, 0, -0.30), "knee_r": (2.30, 0, 0), "ankle_r": (-0.50, 0, 0),
        "shoulder_r": (-1.15 + stir, -0.10, 0.30), "elbow_r": (-0.62 - stir, 0, 0),
        "shoulder_l": (-0.55, 0, -0.22), "elbow_l": (-0.85, 0, 0),
    }


def pose_raise(t: float) -> dict[str, tuple[float, float, float]]:
    p = pose_idle(t)
    p.update({"shoulder_r": (0.05, 0, 0.30), "elbow_r": (-0.20, 0, 0)})
    return p
