#!/usr/bin/env python3
"""
events_an.py — the one-second pulse sheet.

The film is not allowed to sit still for more than about a second. This file is
the single source of truth for that pulse: the renderer reads it to snap the
camera, throw a shockwave ring or a sparkle, and the audio mix reads the *same*
list so the tick, thud or ping lands on the same frame as the picture.

Kinds
    snap    a 4-frame push on the whole frame (the edit "punches")
    ring    a shockwave ring at (x, y) — used where something just happened
    spark   a quick radial sparkle at (x, y)
    sweep   a diagonal light sliver crossing the frame (energy reset)
    pulse   a short contrast/saturation breath (silent emphasis)
"""
from timeline_an import BEATS, TOTAL

# ---------------------------------------------------------------- placement
# (offset inside the beat, kind, params). Hand-placed so that no beat runs for
# more than ~1.1 s without a visible change.
SPEC = {
    1: [(0.32, "snap", dict(amp=1.0)),
        (1.62, "ring", dict(x=886, y=1500, r=210, color="red")),
        (2.72, "spark", dict(x=470, y=1600, n=7)),
        (3.95, "snap", dict(amp=.7)),
        (4.95, "sweep", dict())],
    2: [(0.30, "snap", dict(amp=1.0)),
        (1.22, "ring", dict(x=556, y=946, r=180, color="red")),
        (2.30, "spark", dict(x=760, y=1520, n=6)),
        (3.30, "snap", dict(amp=.8)),
        (4.15, "sweep", dict())],
    3: [(0.30, "snap", dict(amp=1.0)),
        (1.12, "sweep", dict()),
        (2.20, "spark", dict(x=690, y=1380, n=8)),
        (3.25, "ring", dict(x=690, y=1420, r=230, color="gold")),
        (4.35, "snap", dict(amp=.7))],
    4: [(0.30, "snap", dict(amp=1.0)),
        (1.35, "spark", dict(x=540, y=1300, n=8)),
        (2.40, "sweep", dict()),
        (3.45, "snap", dict(amp=.8)),
        (4.60, "spark", dict(x=1010, y=1520, n=5))],
    5: [(0.30, "snap", dict(amp=1.0)),
        (2.55, "ring", dict(x=430, y=1330, r=200, color="gold")),
        (3.55, "spark", dict(x=812, y=1560, n=7)),
        (4.05, "snap", dict(amp=.8))],
    6: [(0.30, "snap", dict(amp=1.0)),
        (1.36, "ring", dict(x=672, y=1500, r=230, color="red")),
        (2.45, "spark", dict(x=980, y=1400, n=7)),
        (3.50, "snap", dict(amp=.8)),
        (4.45, "sweep", dict())],
    7: [(0.30, "snap", dict(amp=1.0)),
        (1.30, "spark", dict(x=336, y=1400, n=7)),
        (2.45, "ring", dict(x=700, y=1500, r=190, color="gold")),
        (3.70, "snap", dict(amp=.7))],
    8: [(0.30, "snap", dict(amp=1.0)),
        (1.40, "spark", dict(x=560, y=950, n=7)),
        (2.50, "sweep", dict()),
        (3.45, "snap", dict(amp=.8))],
    9: [(0.30, "snap", dict(amp=1.0)),
        (1.40, "ring", dict(x=330, y=1590, r=170, color="gold")),
        (2.45, "spark", dict(x=620, y=1120, n=8)),
        (3.45, "sweep", dict())],
    10: [(0.30, "snap", dict(amp=1.0)),
         (1.40, "spark", dict(x=679, y=1294, n=8)),
         (2.65, "sweep", dict()),
         (3.70, "pulse", dict())],
}

EVENTS: list[dict] = []
for _n, _rows in SPEC.items():
    _b = BEATS[_n - 1]
    for _off, _kind, _kw in _rows:
        if _off >= _b["dur"] - .18:          # never fire inside the cut
            continue
        _e = dict(t=round(_b["start"] + _off, 3), beat=_n, kind=_kind)
        _e.update(_kw)
        EVENTS.append(_e)
EVENTS.sort(key=lambda e: e["t"])

# how long each kind stays on screen / is audible
DUR = {"snap": .14, "ring": .46, "spark": .30, "sweep": .40, "pulse": .35}

if __name__ == "__main__":
    print(f"{len(EVENTS)} events over {TOTAL}s "
          f"({len(EVENTS) / TOTAL:.2f} per second)")
    for e in EVENTS[:12]:
        print(" ", e)
