"""Procedural 3D geometry, humanoid rig and environments for the survival reel.

Everything here is generated: triangles, normals, vertex colours and emission.
No images, textures or pre-made models are read. The renderer in `raster.c`
consumes the buffers produced here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

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
MAT_DEFAULT, MAT_SKIN, MAT_CLOTH, MAT_HAIR, MAT_STONE, MAT_LEAF, MAT_EYE, MAT_WOOD, MAT_GROUND = (
    0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)


class Builder:
    """Accumulates triangles with per-vertex colour, emission, uv and material."""

    def __init__(self) -> None:
        self.v: list[np.ndarray] = []
        self.n: list[np.ndarray] = []
        self.c: list[np.ndarray] = []
        self.e: list[np.ndarray] = []
        self.uv: list[tuple[float, float]] = []
        self.m: list[float] = []
        self.t: list[tuple[int, int, int]] = []
        self.mat: float = MAT_DEFAULT

    # ---- primitives -----------------------------------------------------
    def tri(self, a, b, c, colour, normal=None, emission=(0, 0, 0), uvs=None,
            mat: float | None = None) -> None:
        base = len(self.v)
        if normal is None:
            normal = np.cross(np.subtract(b, a), np.subtract(c, a))
            length = np.linalg.norm(normal)
            normal = normal / length if length > 1e-9 else np.array([0, 1, 0], float)
        if uvs is None:
            uvs = tuple((float(p[0]) * 0.7, float(p[1]) * 0.5 + float(p[2]) * 0.7)
                        for p in (a, b, c))
        elif len(uvs) == 2 and not hasattr(uvs[0], "__len__"):
            uvs = (uvs, uvs, uvs)      # broadcast one uv over the triangle
        use_mat = self.mat if mat is None else mat
        for p, uv in zip((a, b, c), uvs):
            self.v.append(np.asarray(p, float))
            self.n.append(np.asarray(normal, float))
            self.c.append(np.asarray(colour, float))
            self.e.append(np.asarray(emission, float))
            self.uv.append((float(uv[0]), float(uv[1])))
            self.m.append(float(use_mat))
        self.t.append((base, base + 1, base + 2))

    def quad(self, a, b, c, d, colour, emission=(0, 0, 0), uvs=None) -> None:
        if uvs is None:
            uvs = [(float(v[0]) * 0.7, float(v[1]) * 0.5 + float(v[2]) * 0.7)
                   for v in (a, b, c, d)]
        self.tri(a, b, c, colour, emission=emission,
                 uvs=(uvs[0], uvs[1], uvs[2]))
        self.tri(a, c, d, colour, emission=emission,
                 uvs=(uvs[0], uvs[2], uvs[3]))

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

    def capsule(self, a, b, ra, rb, colour, rings: int = 8, seg: int = 18,
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
        grid, uvg = [], []
        for i in range(rings + 1):
            t = i / rings
            r = (ra + (rb - ra) * t) * (0.80 + 0.20 * math.sin(math.pi * t) ** 0.5)
            centre = a + axis * t
            ring, ring_uv = [], []
            for j in range(seg):
                ang = 2 * math.pi * j / seg
                ring.append(centre + (u * math.cos(ang) + w * math.sin(ang)) * r)
                # uv in metres so pore/weave scale is constant over the body
                ring_uv.append((j / seg * 2 * math.pi * max(r, 1e-3), t * length))
            grid.append(ring)
            uvg.append(ring_uv)
        tip_a = a - d * ra * 0.85
        tip_b = b + d * rb * 0.85
        for j in range(seg):
            j2 = (j + 1) % seg
            self.tri(tip_a, grid[0][j2], grid[0][j], colour, emission=emission,
                     uvs=(((j + 0.5) / seg * 2 * math.pi * ra, -0.10),
                          uvg[0][j2], uvg[0][j]))
            self.tri(tip_b, grid[-1][j], grid[-1][j2], colour, emission=emission,
                     uvs=(((j + 0.5) / seg * 2 * math.pi * rb, 1.10),
                          uvg[-1][j], uvg[-1][j2]))
        for i in range(rings):
            for j in range(seg):
                j2 = (j + 1) % seg
                self.quad(grid[i][j], grid[i][j2], grid[i + 1][j2], grid[i + 1][j],
                          colour, emission=emission,
                          uvs=[uvg[i][j], uvg[i][j2], uvg[i + 1][j2], uvg[i + 1][j]])

    def sphere(self, centre, radius, colour, rings: int = 10, seg: int = 16,
               scale=(1, 1, 1), emission=(0, 0, 0), squash=0.0) -> None:
        cx, cy, cz = centre
        sx, sy, sz = scale
        grid, uvg = [], []
        for i in range(rings + 1):
            phi = math.pi * i / rings
            row, row_uv = [], []
            for j in range(seg):
                th = 2 * math.pi * j / seg
                wobble = 1.0 + squash * math.sin(3 * th + 1.1) * math.sin(2 * phi)
                row.append(np.array([cx + radius * sx * math.sin(phi) * math.cos(th) * wobble,
                                     cy + radius * sy * math.cos(phi) * wobble,
                                     cz + radius * sz * math.sin(phi) * math.sin(th) * wobble]))
                # uv in metres, so pore size is constant across every primitive
                row_uv.append((th / (2 * math.pi) * 2 * math.pi * radius,
                               phi * radius))
            grid.append(row)
            uvg.append(row_uv)
        for i in range(rings):
            for j in range(seg):
                j2 = (j + 1) % seg
                self.quad(grid[i][j], grid[i][j2], grid[i + 1][j2], grid[i + 1][j], colour,
                          emission=emission,
                          uvs=[uvg[i][j], uvg[i][j2], uvg[i + 1][j2], uvg[i + 1][j]])

    def cone(self, base_centre, radius, height, colour, seg: int = 8,
             emission=(0, 0, 0), lean=(0.0, 0.0)) -> None:
        bx, by, bz = base_centre
        apex = np.array([bx + lean[0], by + height, bz + lean[1]])
        ring = [np.array([bx + radius * math.cos(2 * math.pi * j / seg), by,
                          bz + radius * math.sin(2 * math.pi * j / seg)]) for j in range(seg)]
        for j in range(seg):
            j2 = (j + 1) % seg
            self.tri(ring[j], ring[j2], apex, colour, emission=emission,
                     uvs=((j / seg) * 2 * math.pi * radius, 0.0))
            self.tri(np.array([bx, by, bz]), ring[j2], ring[j], colour, emission=emission,
                     uvs=(0.0, 0.0))

    def ground(self, size: float, cells: int, height_fn, colour_fn) -> None:
        """Displaced grid; flat enough to stand on, rolling enough to feel real."""
        step = size / cells
        pts = np.zeros((cells + 1, cells + 1, 3))
        for i in range(cells + 1):
            for j in range(cells + 1):
                x = -size / 2 + i * step
                z = -size / 2 + j * step
                pts[i, j] = (x, height_fn(x, z), z)
        old = self.mat
        self.mat = MAT_GROUND
        for i in range(cells):
            for j in range(cells):
                a, b, c, d = pts[i, j], pts[i + 1, j], pts[i + 1, j + 1], pts[i, j + 1]
                colour = colour_fn((a[0] + c[0]) / 2, (a[2] + c[2]) / 2, (a[1] + c[1]) / 2)
                self.quad(a, d, c, b, colour)
        self.mat = old

    # ---- output ---------------------------------------------------------
    def arrays(self, jitter: float = 0.006):
        v = np.asarray(self.v, np.float32) if self.v else np.zeros((0, 3), np.float32)
        n = np.asarray(self.n, np.float32) if self.n else np.zeros((0, 3), np.float32)
        c = np.asarray(self.c, np.float32) if self.c else np.zeros((0, 3), np.float32)
        e = np.asarray(self.e, np.float32) if self.e else np.zeros((0, 3), np.float32)
        t = np.asarray(self.t, np.int32) if self.t else np.zeros((0, 3), np.int32)
        uv = np.asarray(self.uv, np.float32) if self.uv else np.zeros((0, 2), np.float32)
        m = np.asarray(self.m, np.float32) if self.m else np.zeros((0,), np.float32)
        if len(v) and len(t):
            # weld coincident vertices and average their face normals: this is what
            # turns faceted primitives into smooth, organic-looking surfaces
            key = np.round(v * 2000.0).astype(np.int64)
            _, inv = np.unique(key, axis=0, return_inverse=True)
            fn = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
            acc = np.zeros((inv.max() + 1, 3), np.float64)
            for k in range(3):
                np.add.at(acc, inv[t[:, k]], fn)
            ln = np.linalg.norm(acc, axis=1, keepdims=True)
            acc = acc / np.maximum(ln, 1e-9)
            n = acc[inv].astype(np.float32)
        if jitter > 0 and len(c) and len(t):
            # per-triangle tonal noise: breaks up flat facets like brush work
            rng = np.random.default_rng(7)
            k = (1.0 + rng.normal(0.0, jitter, len(t))).astype(np.float32)
            c = c.copy()
            c[t.reshape(-1)] *= np.repeat(k, 3)[:, None]
            np.clip(c, 0.0, 1.6, out=c)
        return v, n, c, e, t, uv, m


# ------------------------------------------------------------- scanned heads
# Geometry from Google's GNM Head (Apache-2.0, Copyright 2026 Google LLC),
# baked to a compact npz by tools/bake_gnm_heads.py. Four identities.
_HEADS: dict | None = None
_HEAD_INDEX = {"man": 0, "woman": 1, "elder": 2, "woman2": 3}
HEAD_ANCHOR = np.array([0.0, 0.2100, 0.0176])     # model-space head joint


def _heads() -> dict:
    global _HEADS
    if _HEADS is None:
        data = np.load(Path(__file__).resolve().parent / "heads.npz")
        groups = {str(n): data["groups"][i] for i, n in enumerate(data["group_names"])}
        names = [str(n) for n in data["names"]]
        cache = {}
        for i, name in enumerate(names):
            V = data["v"][i].astype(np.float64)
            T = data["t"].astype(np.int32)
            fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
            nrm = np.zeros_like(V)
            for k in range(3):
                np.add.at(nrm, T[:, k], fn)
            ln = np.linalg.norm(nrm, axis=1, keepdims=True)
            nrm /= np.maximum(ln, 1e-9)
            cache[name] = dict(v=V, t=T, n=nrm, g=groups)
        _HEADS = cache
    return _HEADS


def add_gnm_head(b: Builder, world: dict, kind: str, skin, hair_col, blink: float = 0.0,
                 head_pos=None, fwd=None, side=None, up=None) -> None:
    """Place a scanned human head on the rig, with procedural hair and brows."""
    heads = _heads()
    key = kind if kind in heads else "man"
    H = heads[key]
    V, T, N, G = H["v"], H["t"], H["n"], H["g"]
    if head_pos is None:
        head_pos = world["head"][:3, 3]
    if fwd is None:
        fwd = _facing(world)
    if side is None:
        side = np.array([fwd[2], 0.0, -fwd[0]])
    if up is None:
        up = np.array([0.0, 1.0, 0.0])

    L = V - HEAD_ANCHOR                      # local head space, metres
    # tiny blink: squeeze the lid vertices towards the eye centre
    for gname, sd in (("scleras", 0),):
        pass
    W = (head_pos[None, :] + side[None, :] * L[:, 0:1] + up[None, :] * L[:, 1:2]
         + fwd[None, :] * L[:, 2:3])
    Nw = (side[None, :] * N[:, 0:1] + up[None, :] * N[:, 1:2] + fwd[None, :] * N[:, 2:3])

    sclera = G["scleras"] > 0.5
    iris = G["irises"] > 0.5
    pupil = G["pupils"] > 0.5
    eyelid = G["eye_interiors"] > 0.5
    lip_u = G["upper_lip"] > 0.5
    lip_l = G["lower_lip"] > 0.5
    teeth = G["teeth"] > 0.5
    gums = G["gums"] > 0.5
    tongue = G["tongue"] > 0.5

    base = np.array(skin, np.float64)
    lip_col = np.array([skin[0] * 0.94, skin[1] * 0.66, skin[2] * 0.63])
    col = np.tile(base, (len(V), 1))
    # per-vertex shading: lips, eye sockets, brow ridge, stubble
    y = L[:, 1]
    col[lip_u | lip_l] = lip_col
    # brow band tint (dark hair colour blended over the ridge)
    # eyebrow band sits on the brow ridge, just above the eye centre
    eye_y = float(np.mean(y[G["pupils"] > 0.5])) if (G["pupils"] > 0.5).any() else 0.093
    brow = ((y > eye_y + 0.012) & (y < eye_y + 0.030) & (np.abs(L[:, 0]) > 0.010)
            & (np.abs(L[:, 0]) < 0.052) & (L[:, 2] > 0.055))
    bb = np.clip(1.0 - np.abs(np.abs(L[:, 0]) - 0.028) / 0.026, 0.0, 1.0)
    col[brow] = (col[brow] * (1.0 - 0.80 * bb[brow, None])
                 + np.array(hair_col) * 0.30 * bb[brow, None])
    if key in ("man", "elder"):
        stub = (y < 0.0) & (L[:, 2] > 0.0)
        col[stub] *= np.array([0.94, 0.915, 0.905])
    # eyes and mouth interior
    col[sclera] = (0.50, 0.455, 0.435)
    col[iris] = (0.20, 0.10, 0.045)
    col[pupil] = (0.012, 0.009, 0.008)
    col[teeth] = (0.66, 0.62, 0.55)
    col[gums] = (0.38, 0.17, 0.16)
    col[tongue] = (0.36, 0.14, 0.14)
    col[eyelid & ~(sclera | iris | pupil)] *= 0.86

    mat = np.full(len(V), MAT_SKIN, np.float64)
    mat[sclera | iris | pupil] = MAT_EYE

    uv = np.stack([np.arctan2(L[:, 0], L[:, 2]) * 0.11, L[:, 1] - 0.21], axis=1)

    # ---- push the vertices into the global builder ----------
    off = len(b.v)
    for i in range(len(V)):
        b.v.append(W[i])
        b.n.append(Nw[i])
        b.c.append(col[i])
        b.e.append(np.zeros(3))
        b.uv.append((float(uv[i, 0]), float(uv[i, 1])))
        b.m.append(float(mat[i]))
    keep = ((L[T[:, 0], 1] > -0.022) | (L[T[:, 1], 1] > -0.022) | (L[T[:, 2], 1] > -0.022))
    for tri in T[keep]:
        b.t.append((off + int(tri[0]), off + int(tri[1]), off + int(tri[2])))

    # ---- hair: a shell grown off the skull above the hairline ----------
    fwd_l = L[:, 2]
    ax = L[:, 0]
    udir = np.arctan2(ax, fwd_l)                     # 0 = front, pi = back
    crown = y
    # hairline height as a function of the azimuth: high at the brow, low at the nape
    front = np.clip(np.cos(udir), 0.0, 1.0) ** 0.7
    back = np.clip(-np.cos(udir), 0.0, 1.0) ** 0.6
    hl = 0.142 * front + 0.060 * (1.0 - front) * (1.0 - back) - 0.010 * back
    hl += 0.016 * np.clip(1.0 - np.abs(ax) / 0.055, 0.0, 1.0) * front ** 2
    hl += 0.004 * np.sin(udir * 5.0)
    hair_mask = (crown > hl) & (L[:, 2] < 0.115) & (np.abs(ax) < 0.105)
    if key in ("woman", "woman2"):
        # longer at the sides and nape
        hair_mask |= (crown > -0.020) & (np.abs(ax) > 0.056) & (L[:, 2] < -0.01)
    else:
        # keep the ears and jaw clear for the men
        hair_mask &= ~((crown < 0.030) & (np.abs(ax) > 0.050))
    # grow the shell along the normal, thicker over the crown
    thick = (0.009 + 0.013 * np.clip((crown - hl) / 0.10, 0.0, 1.0)) \
        * np.clip((crown - hl) / 0.010, 0.0, 1.0)
    HW = W + Nw * (thick[:, None] * hair_mask[:, None])
    hair_col_v = np.array(hair_col)
    hcol = np.tile(hair_col_v, (len(V), 1))
    hcol *= (0.82 + 0.30 * np.clip((crown - hl) / 0.12, 0.0, 1.0))[:, None]
    off2 = len(b.v)
    remap = np.full(len(V), -1, np.int64)
    for i in range(len(V)):
        if not hair_mask[i]:
            continue
        remap[i] = len(b.v) - off2
        b.v.append(HW[i])
        b.n.append(Nw[i])
        b.c.append(hcol[i])
        b.e.append(np.zeros(3))
        b.uv.append((float(uv[i, 0]), float(uv[i, 1])))
        b.m.append(MAT_HAIR)
    for tri in T:
        i0, i1, i2 = int(tri[0]), int(tri[1]), int(tri[2])
        if hair_mask[i0] and hair_mask[i1] and hair_mask[i2]:
            b.t.append((off2 + int(remap[i0]), off2 + int(remap[i1]),
                        off2 + int(remap[i2])))
    # ---- beard shading for the elder: a soft jaw tint, no extra shell ----
    if key == "elder":
        w = np.clip((0.004 - y) / 0.030, 0.0, 1.0) * np.clip((y + 0.058) / 0.020, 0.0, 1.0)
        w *= np.clip((np.abs(L[:, 0]) - 0.014) / 0.022, 0.0, 1.0)
        w *= np.clip((L[:, 2] + 0.030) / 0.030, 0.0, 1.0)
        w *= (G["ears"] < 0.5) * 0.75
        col = col * (1.0 - w[:, None]) + np.array(hair_col) * w[:, None]
    b.mat = MAT_SKIN


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
             grey_hair: bool = False, kind: str = "man", blink: float = 0.0) -> None:
        p = {bone.name: bone.colour for bone in BONES}
        b.mat = MAT_SKIN
        if palette:
            p.update(palette)
        for bone in BONES:
            a = world[bone.joints[0]][:3, 3]
            bpos = world[bone.joints[1]][:3, 3]
            shade = p[bone.name]
            rings = 12 if bone.name in ("pelvis", "spine", "chest", "neck") else 10
            b.capsule(a, bpos, bone.radius[0], bone.radius[1], shade, rings=rings, seg=22)
        # ---- head: Google GNM Head geometry (Apache-2.0), scanned anatomy ----
        head = world["head"][:3, 3]
        fwd = _facing(world)
        side = np.array([fwd[2], 0.0, -fwd[0]])
        up = np.array([0.0, 1.0, 0.0])
        hair_col = (0.66, 0.65, 0.63) if grey_hair else hair
        add_gnm_head(b, world, kind=kind, skin=skin, hair_col=hair_col,
                     blink=blink, head_pos=head, fwd=fwd, side=side, up=up)

        # neck: a smooth column from the chest up into the scanned head
        b.mat = MAT_SKIN
        neck_top = world["neck"][:3, 3]
        b.capsule(neck_top - up * 0.02, head - up * 0.040, 0.060, 0.058,
                  tuple(c * 0.90 for c in skin), rings=8, seg=26)
        # shoulders: soft deltoid masses under the tunic
        for sd in (-1, 1):
            b.sphere(head + side * (sd * 0.135) - up * 0.235 + fwd * 0.005, 0.052, skin,
                     rings=10, seg=16, scale=(1.25, 0.70, 0.92))

        # joints: spheres that blend the capsules into limbs
        b.mat = MAT_SKIN
        for name, rr in (("elbow_l", 0.058), ("elbow_r", 0.058), ("knee_l", 0.070),
                         ("knee_r", 0.070), ("wrist_l", 0.044), ("wrist_r", 0.044),
                         ("ankle_l", 0.054), ("ankle_r", 0.054)):
            jp = world[name][:3, 3]
            b.sphere(jp, rr, skin, rings=10, seg=18, scale=(1.0, 1.0, 1.0))
        for sd in (-1, 1):
            sh = world["shoulder_l" if sd < 0 else "shoulder_r"][:3, 3]
            b.sphere(sh, 0.072, skin, rings=10, seg=18, scale=(1.0, 1.02, 1.0))
        # ---- torso: one smooth hide tunic from thigh to collarbone ----
        b.mat = MAT_CLOTH
        chest = world["chest"][:3, 3]
        pelvis = world["pelvis"][:3, 3]
        hip = pelvis + np.array([0, -0.16, 0])
        b.capsule(hip + np.array([0, -0.06, 0]), chest + np.array([0, 0.04, 0]),
                  0.168, 0.150, tunic, rings=16, seg=34, taper_power=0.6)
        # hide hem flares over the thighs like a short skirt
        hem_dark = tuple(c * 0.86 for c in tunic)
        b.capsule(hip + np.array([0, 0.02, 0]), hip - np.array([0, 0.14, 0]), 0.164, 0.178,
                  hem_dark, rings=8, seg=34)
        b.mat = MAT_SKIN
        # kneeling/sitting support: a folded calf volume that reaches the floor
        for side in ("l", "r"):
            knee = world[f"knee_{side}"][:3, 3]
            ankle = world[f"ankle_{side}"][:3, 3]
            fold = (knee + ankle) / 2 + np.array([0, -0.055, 0])
            b.capsule(knee, fold, 0.062, 0.070, skin, rings=6, seg=14)
        # ---- hands and feet ----
        for side in ("l", "r"):
            wrist = world[f"wrist_{side}"][:3, 3]
            m = world[f"elbow_{side}"]
            hand_dir = wrist - m[:3, 3]
            n_ = np.linalg.norm(hand_dir)
            hand_dir = hand_dir / n_ if n_ > 1e-6 else np.array([0, -1.0, 0])
            # palm
            b.capsule(wrist, wrist + hand_dir * 0.062, 0.040, 0.034, skin, rings=5, seg=12)
            # fingers: four splayed capsules plus a thumb, cheap but reads as a hand
            palm_end = wrist + hand_dir * 0.060
            across = np.cross(hand_dir, np.array([0.0, 1.0, 0.0]))
            n_ac = np.linalg.norm(across)
            across = across / n_ac if n_ac > 1e-6 else np.array([1.0, 0.0, 0.0])
            for fi in range(4):
                t = (fi - 1.5) / 1.5
                root = palm_end + across * (t * 0.030)
                tip = root + hand_dir * (0.052 - 0.008 * abs(t) + 0.004 * (1.0 - abs(t))) \
                    + across * (t * 0.010)
                b.capsule(root, tip, 0.0092, 0.0068, skin, rings=4, seg=8)
            thumb_root = wrist + hand_dir * 0.020 + across * 0.030
            b.capsule(thumb_root, thumb_root + hand_dir * 0.030 + across * 0.020,
                      0.0105, 0.0080, skin, rings=4, seg=8)
            ankle = world[f"ankle_{side}"][:3, 3]
            toe = ankle + fwd * 0.16 - np.array([0, 0.062, 0])
            b.capsule(ankle - np.array([0, 0.045, 0]) - fwd * 0.03, toe, 0.052, 0.038,
                      skin, rings=6, seg=16)


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
