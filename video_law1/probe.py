#!/usr/bin/env python3
"""
probe.py — records *when every element appears and moves* in the render.

The sound design (audio_v9.py) is built from this file, not from guesswork: the
renderer is the single source of truth for timing, so every hit lands on the
exact frame where something happens on screen.

How it works
------------
`install(render_v3)` monkey-patches the drawing helpers the scenes use
(`put`, `put_host`, `halo`, `pill`, `put_text_scaled`, `T`, `draw_particles`)
in the render module's globals. Each call records the element's current
opacity / scale / size at the current frame time. A later pass (`onsets()`)
turns those per-frame series into *appearance* and *pulse* events.

Nothing is written to the frames themselves — with `probe.ENABLED = False` the
wrappers return immediately.
"""
from __future__ import annotations

import json
import os

ENABLED = False
T_NOW = 0.0
SERIES: dict[tuple, dict] = {}


def _rec(kind, key, opacity, scale=1.0, meta=None):
    if not ENABLED:
        return
    k = (kind, key)
    row = SERIES.get(k)
    if row is None:
        row = SERIES[k] = {"kind": kind, "key": key, "meta": meta or {}, "pts": []}
    pt = row["pts"]
    if pt and abs(pt[-1][0] - T_NOW) < 1e-6:
        pt[-1] = (T_NOW, max(pt[-1][1], opacity), max(pt[-1][2], scale))
    else:
        pt.append((T_NOW, opacity, scale))


# --------------------------------------------------------------------- wrappers
def install(mod):
    orig = {n: getattr(mod, n) for n in
            ("put", "put_host", "halo", "pill", "put_text_scaled", "T", "draw_particles")
            if hasattr(mod, n)}

    def put(base, name, cx=None, cy=None, max_w=None, max_h=None, scale=1.0,
            opacity=1.0, **kw):
        if "put" not in orig:
            return None
        _rec("image", name, float(opacity or 0), float(scale or 1),
             {"x": cx, "y": cy, "w": max_w, "h": max_h})
        return orig["put"](base, name, cx=cx, cy=cy, max_w=max_w, max_h=max_h,
                           scale=scale, opacity=opacity, **kw)

    def put_host(base, name, bottom=None, top=None, cx=None, left=None, right=None,
                 max_h=None, opacity=1.0, **kw):
        _rec("host", name, float(opacity or 0), 1.0, {"x": cx, "y": bottom or top})
        return orig["put_host"](base, name, bottom=bottom, top=top, cx=cx, left=left,
                                right=right, max_h=max_h, opacity=opacity, **kw)

    def halo(base, cx, cy, r, color=(232, 228, 218), opacity=1.0, falloff=0.8):
        _rec("halo", f"halo@{int(cx)}x{int(cy)}", float(opacity or 0),
             float(r) / 400.0, {"x": cx, "y": cy, "r": r})
        return orig["halo"](base, cx, cy, r, color, opacity, falloff)

    def pill(base, cx, cy, txt, **kw):
        _rec("pill", str(txt), float(kw.get("opacity", 1.0) or 0),
             float(kw.get("scale", 1.0) or 1), {"x": cx, "y": cy})
        return orig["pill"](base, cx, cy, txt, **kw)

    def put_text_scaled(base, text, f, color, cx, cy, scale=1.0, alpha=1.0,
                        anchor_mm=True):
        _rec("big", str(text), float(alpha or 0), float(scale or 1),
             {"x": cx, "y": cy, "fs": getattr(f, "size", 0)})
        return orig["put_text_scaled"](base, text, f, color, cx, cy, scale, alpha, anchor_mm)

    def T(base, xy, txt, f, fill=None, anchor="mm", alpha=1.0, **kw):
        _rec("text", str(txt), float(alpha or 0), 1.0,
             {"x": xy[0], "y": xy[1], "fs": getattr(f, "size", 0)})
        return orig["T"](base, xy, txt, f, **({"fill": fill} if fill is not None else {}),
                         anchor=anchor, alpha=alpha, **kw)

    def draw_particles(base, P, t, kind, density=1.0, tint=None, y_min=0):
        _rec("particles", kind, float(density or 0), 1.0, {})
        return orig["draw_particles"](base, P, t, kind, density, tint, y_min)

    # frame effects: each call is its own momentary event, keyed by its time
    orig_flash = getattr(mod, "flash", None)
    orig_glitch = getattr(mod, "glitch", None)
    orig_trans = getattr(mod, "transition", None)

    if orig_flash:
        def flash(img, color, amt=0.0):
            _rec("flash", f"{T_NOW:.2f}", float(amt or 0), 1.0, {})
            return orig_flash(img, color, amt)
        mod.flash = flash

    if orig_glitch:
        def glitch(img, t, amt=0.0):
            _rec("glitch", f"{T_NOW:.2f}", float(amt or 0), 1.0, {})
            return orig_glitch(img, t, amt)
        mod.glitch = glitch

    if orig_trans:
        def transition(a, b, kind="whoosh", p=0.0):
            _rec("transition", kind, float(cl01(p)), 1.0, {"kind": kind})
            return orig_trans(a, b, kind, p)
        mod.transition = transition

    for name, fn in (("put", put), ("put_host", put_host), ("halo", halo), ("pill", pill),
                     ("put_text_scaled", put_text_scaled), ("T", T),
                     ("draw_particles", draw_particles)):
        setattr(mod, name, fn)


def cl01(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


# ------------------------------------------------------------------- extraction
def onsets(min_alpha=0.16, pulse_rise=0.20):
    """Turn per-frame series into appearance / pulse events."""
    events = []
    for row in SERIES.values():
        pts = row["pts"]
        if not pts:
            continue
        amps = [p[1] for p in pts]
        peak = max(amps) if amps else 0
        if peak <= 0.02:
            continue
        thr = max(min_alpha, 0.30 * peak)
        prev_above = False
        last_ev = -9.9
        for (t, a, sc) in pts:
            above = a >= thr
            if above and not prev_above and t - last_ev > 0.12:
                events.append(_event(t, "appear", row, a, sc))
                last_ev = t
            prev_above = above
        # pulses: a sharp scale pop while the element is already visible
        for i in range(1, len(pts) - 1):
            t, a, sc = pts[i]
            if a < thr:
                continue
            before = pts[i - 1][2]
            if sc - before >= pulse_rise and t - last_ev > 0.12:
                events.append(_event(t, "pulse", row, a, sc))
                last_ev = t
    events.sort(key=lambda e: e["t"])
    return events


def _event(t, kind, row, a, sc):
    meta = row["meta"] or {}
    x, y = meta.get("x"), meta.get("y")
    return dict(t=round(t, 3), type=kind, el=row["kind"], label=row["key"],
                x=(round(float(x), 1) if isinstance(x, (int, float)) else None),
                y=(round(float(y), 1) if isinstance(y, (int, float)) else None),
                fs=int(meta.get("fs") or 0), amp=round(min(float(a), 1.0), 2),
                scale=round(float(sc), 3))


def dump(path, extra=None):
    data = {"events": onsets()}
    if extra:
        data.update(extra)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
    return data
