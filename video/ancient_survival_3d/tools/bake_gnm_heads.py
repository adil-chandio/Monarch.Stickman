"""Bake a few distinct human heads from Google's GNM Head model (Apache-2.0).

Run once with the official `gnm_head.npz` in reach:

    PYTHONPATH=/tmp/monarch-deps python3 tools/bake_gnm_heads.py /path/to/gnm_head.npz

Writes `heads.npz` next to the renderer: only the baked vertices, triangle list,
per-vertex group masks and colours are stored, so the reel stays self-contained
and small. GNM Head: Copyright 2026 Google LLC, Apache License 2.0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent

# deterministic identities: (seed, identity coefficient strength, expression strength)
IDENTITIES = [("man", 0, 1.00, 0.0), ("woman", 1, 0.95, 0.0),
              ("elder", 2, 1.05, 0.0), ("woman2", 3, 0.90, 0.0)]


def _open_eyes(V: np.ndarray, groups: dict, fwd: float = 0.0028, spread: float = 0.88,
               a: float = 0.0158, b: float = 0.0089) -> None:
    """The template ships with the lids shut; part them into a natural almond.

    Lid-skin vertices are pushed radially away from the eye centre and the
    eyeball is nudged forward until the cornea just clears the lid margin.
    """
    eye = (groups["scleras"] > 0.5) | (groups["irises"] > 0.5) | \
        (groups["pupils"] > 0.5) | (groups["eye_interiors"] > 0.5)
    skin = groups["skin_exterior"] > 0.5
    for sd in (1, -1):
        sel = eye & ((V[:, 0] * sd) > 0)
        if not sel.any():
            continue
        c = V[sel].mean(0) + np.array([0.0, 0.0, fwd])
        V[sel, 2] += fwd
        dx = (V[:, 0] - c[0]) / a
        dy = (V[:, 1] - c[1]) / b
        r = np.sqrt(dx ** 2 + dy ** 2)
        m = skin & (r < 1.35) & (V[:, 2] > c[2] - 0.008) & ((V[:, 0] * sd) > 0)
        k = np.clip(1.0 - r / 1.35, 0.0, 1.0)
        sc = 1.0 + spread * k
        V[m, 0] = c[0] + (V[m, 0] - c[0]) * sc[m]
        V[m, 1] = c[1] + (V[m, 1] - c[1]) * sc[m]


def main(src: str) -> None:
    d = np.load(src)
    V0 = d["template_vertex_positions"].astype(np.float64)
    B = d["vertex_identity_basis"].astype(np.float64)
    E = d["expression_basis"].astype(np.float64)
    tris = d["triangles"].astype(np.int32)
    groups = {str(n): d["vertex_groups"][i].astype(np.float32)
              for i, n in enumerate(d["vertex_group_names"])}

    out_v, out_c, out_m, out_names = [], [], [], []
    for name, seed, strength, expr in IDENTITIES:
        rng = np.random.default_rng(1000 + seed)
        coeff = rng.normal(0.0, 1.0, B.shape[0]) * strength
        coeff[:12] *= 0.8
        V = V0 + np.tensordot(coeff, B, axes=(0, 0))
        if expr > 0:
            ec = rng.normal(0.0, 1.0, E.shape[0]) * expr
            V = V + np.tensordot(ec, E, axes=(0, 0))
        _open_eyes(V, groups)
        # trim the shoulder bell: the body supplies the neck below the jaw
        out_v.append(V.astype(np.float32))
        out_names.append(name)
    V = np.stack(out_v)
    np.savez_compressed(HERE / "heads.npz", v=V, t=tris,
                        groups=np.stack([groups[k] for k in
                                         ("skin_exterior", "ears", "scleras", "irises",
                                          "pupils", "eye_interiors", "teeth", "gums",
                                          "tongue", "upper_lip", "lower_lip")]),
                        group_names=np.array(["skin_exterior", "ears", "scleras", "irises",
                                              "pupils", "eye_interiors", "teeth", "gums",
                                              "tongue", "upper_lip", "lower_lip"]),
                        names=np.array(out_names))
    print("wrote", HERE / "heads.npz", V.shape, tris.shape)


if __name__ == "__main__":
    main(sys.argv[1])
