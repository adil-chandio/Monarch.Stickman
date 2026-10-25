#!/usr/bin/env python3
"""
sfx_v13.py — the accent kit, rebuilt as layered sound design.

v9/v10's kit was one-shots: a filtered noise burst with an envelope. Every hit
was recognisably the same object. A designed film hit is five layers
(transient / sub / knock / air / convolution tail) and every cue gets its own
root note, length, seed and pan — so no two hits in a video are identical.

Mapping (placement policy unchanged from v10: cuts are priority, no two accents
closer than MIN_GAP, accents never louder than the voice):

  cut        whoosh, rising or falling, duration follows the transition weight
  big word   impact, tuned to the word (root 72-96 Hz), bright transient
  picture    marker ping (crown glint), rising whoosh (materialise), crackle
  punch      impact, root 44-60 Hz, heavier on the hard punches
  arrest     impact + metallic ring (the iron latch)
  end card   low bell, then a high sparkle

Typing is untouched: `audio_v9`'s keystrokes are diegetic and were signed off.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

import audio_v3 as A
import audio_v9 as V9
import premium_audio as P
from audio_v10 import CONFIG, Placer, rng
from timeline_v4 import BEATS

_CACHE: dict = {}


def _s(name: str, **kw) -> np.ndarray:
    """Generate-once cache: designing a hit costs ~20 ms, and cues repeat."""
    key = (name, tuple(sorted(kw.items())))
    if key not in _CACHE:
        _CACHE[key] = getattr(P, name)(**kw)
    return _CACHE[key]


def design(total: float):
    data = V9.load_events()
    ev = data["events"]
    n = A.T(total)
    keys = np.zeros((n, 2), dtype=np.float32)
    accents = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)
    pl = Placer(accents, send, CONFIG["MIN_GAP"])
    counts = defaultdict(int)
    log = []

    def put(sig, at, gain, pan, tag):
        A.place(accents, sig, at, gain=gain, pan=pan, rev=None)
        pl.times.append(at)
        log.append((round(at, 2), tag, ""))
        counts[tag] += 1

    # ------------------------------------------------------------------ 1 cuts
    CUT = {"slide": (.42, .75), "whoosh": (.55, .85), "flash": (.60, .95),
           "slam": (.70, 1.0), "punch": (.90, 1.0)}
    for k, e in enumerate(x for x in ev if x["el"] == "transition"):
        dur, g = CUT.get(e["label"], (.55, .85))
        up = k % 2 == 0
        sig = _s("whoosh", dur=dur, up=up, seed=100 + k)
        put(sig, e["t"], g, float(rng.uniform(-.3, .3)), "cut")

    # -------------------------------------------------------- 2 the big words
    for k, e in enumerate(x for x in ev if x["el"] == "big" and x["fs"] >= 90):
        sig = _s("impact", root_hz=float(72 + 8 * (k % 3)), dur=1.1,
                 bright=.85, seed=200 + k)
        put(sig, e["t"], .85, V9.pan_for(e["x"]), "bigword")

    # ----------------------------------------------------------- 3 the pictures
    PIC = {"icon_crown": ("marker", 1320), "icon_flame": ("impact", 96),
           "icon_scale": ("marker", 660), "icon_warning": ("marker", 990),
           "king_throne": ("whoosh", 0), "palace_party": ("whoosh", 1),
           "chained_hand": ("impact", 88)}
    for k, e in enumerate(x for x in ev if x["el"] == "image"):
        kind, arg = PIC.get(e["label"], ("whoosh", 1))
        if kind == "marker":
            sig = _s("marker", freq=float(arg), dur=.55, seed=300 + k)
        elif kind == "impact":
            sig = _s("impact", root_hz=float(arg), dur=1.0, bright=.9, seed=300 + k)
        else:
            sig = _s("whoosh", dur=.5, up=bool(arg), seed=300 + k)
        g = .8 if e["label"] in ("icon_crown", "icon_flame", "chained_hand") else .65
        put(sig, e["t"], g, V9.pan_for(e["x"]), "picture")

    # ------------------------------------------------------------- 4 the punches
    for k, e in enumerate(data["derived"]):
        if e["amp"] >= 0.6:
            heavy = e["amp"] >= 0.85
            sig = _s("impact", root_hz=float(44 + 6 * (k % 4)),
                     dur=1.5 if heavy else 1.1, bright=1.0 if heavy else .7,
                     seed=400 + k)
            put(sig, e["t"], 1.0 if heavy else .7, float(rng.uniform(-.15, .15)),
                "punch")

    # ---- the arrest: impact + a metallic ring (the story's turning point)
    arrest = [e for e in data["derived"] if abs(e["t"] - 29.52) < 0.05]
    if arrest:
        t = arrest[0]["t"]
        put(_s("impact", root_hz=120.0, dur=.9, bright=1.0, seed=501), t + .02,
            .55, .25, "arrest")
        put(_s("marker", freq=1740.0, dur=.8, seed=502), t + .06, .40, -.28,
            "arrest")

    # ------------------------------------------------------- 5 the end card
    end = BEATS[-1]["start"]
    put(_s("marker", freq=220.0, dur=2.6, seed=601), end + 1.55, .70, 0.0, "end")
    put(_s("marker", freq=1318.0, dur=1.4, seed=602), end + 4.10, .45, .18, "end")

    # ------------------------------------------------------------- 6 the typing
    text_events = [e for e in ev if e["el"] == "text"]
    runs = V9.typewriter_runs(text_events)
    in_run = {id(e) for r in runs for e in r}

    def key(t, weight, gain, pan):
        if pl.times and min(abs(t - u) for u in pl.times) < 0.25:
            return
        name = {"hard": "key_hard", "mid": "key_mid", "soft": "key_soft",
                "space": "key_space", "ret": "key_return"}[weight]
        sig, sync = V9.sound(name)
        V9.place(keys, sig, t - sync, gain=gain, pan=pan, rev=None,
                 semis=float(rng.uniform(-.8, .8)))
        counts["keys"] += 1

    for r in runs:
        for i, e in enumerate(r):
            ch = e["label"][-1:]
            w = "space" if ch == " " else ("hard" if (ch.isupper() and i) else "mid")
            key(e["t"], w, 1.0 if w == "space" else .85, V9.pan_for(e["x"]))
        key(r[-1]["t"] + .06, "ret", .8, V9.pan_for(r[-1]["x"]))
        counts["typed_runs"] += 1

    solo = [e for e in text_events if id(e) not in in_run and e["fs"] >= 44]
    solo.sort(key=lambda e: -e["fs"])
    for e in solo[:3]:
        for i in range(2):
            key(e["t"] - (2 - i) * .075, "mid" if i else "soft", .55, V9.pan_for(e["x"]))
        key(e["t"], "space", .7, V9.pan_for(e["x"]))
        counts["typed_reveals"] += 1

    return keys, accents, dict(counts), [(round(t, 2), "design", tag) for t, tag, _ in log] + \
        [(round(e["t"], 2), "cut", "cut") for e in ev[:0]]


if __name__ == "__main__":
    import os
    import soundfile as sf
    from timeline_v4 import TOTAL
    k, a, c, log = design(TOTAL + 0.25)
    print("counts:", c)
    print(f"accents rms {A.rms_db(a):.1f} peak {20 * np.log10(np.abs(a).max()):.1f}")
    sf.write(os.path.join("v3out", "sfx_v13.wav"), a, 48000, subtype="FLOAT")
    print("wrote v3out/sfx_v13.wav")
