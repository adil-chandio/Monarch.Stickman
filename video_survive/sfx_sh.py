#!/usr/bin/env python3
"""
sfx_sh.py — sound design for "How Ancient Humans Survived".

Every cue is tied to a real animation trigger in render_sh.py, so the hit lands
on the frame the shape appears (the same rule as the Law videos). There is no
narration in this cut, so the effects are allowed to be 0.9/s instead of 0.35/s:
they *are* the story here.

New voices designed for this film (all synthesized, no samples):

    roar     pitch-dropping saw cluster + growl AM + convolution — the mammoth
    cloth    band-swept noise swell with a soft attack — the hide dropping
    crackle  short band-passed ticks — embers, deliberately sparse (6 in 46 s)
    stone    bright transient + 1.8 kHz ring — stone knapping

Run: python sfx_sh.py -> out/sfx_sh.wav
"""
from __future__ import annotations

import os

import numpy as np

import audio_v3 as A
import premium_audio as P
from audio_v3 import SR
from timeline_sh import BEATS, TOTAL

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
rng = np.random.default_rng(4646)
B = {b["n"]: b["start"] for b in BEATS}

_CACHE: dict = {}


def gen(kind: str, **kw) -> np.ndarray:
    key = (kind, tuple(sorted(kw.items())))
    if key not in _CACHE:
        _CACHE[key] = globals()["_" + kind](**kw)
    return _CACHE[key]


# ------------------------------------------------------------------ the voices
def _boom(root=48.0, dur=1.5, bright=.7, seed=1):
    return P.impact(root, dur, bright, seed)


def _whoosh(dur=.55, up=True, seed=1):
    return P.whoosh(dur, up, seed)


def _ping(freq=880.0, dur=.6, seed=1):
    return P.marker(freq, dur, seed)


def _crack(seed=7):
    """Lightning: a saturated click, a torn noise tail, no musical pitch."""
    from pedalboard import Pedalboard, Distortion, HighpassFilter
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    nz = rng.normal(0, 1, n).astype(np.float32)
    body = nz * np.exp(-t * 26)
    body = np.ascontiguousarray(
        Pedalboard([HighpassFilter(700), Distortion(drive_db=12.0)])(
            np.ascontiguousarray(body[None, :]), SR)[0])
    stereo = np.stack([body, np.roll(body, 41)], axis=1)
    wet = P.convolve(stereo, P.make_ir(.6, 7.0, .004, 8000, seed), wet=.30)
    out = _mix2(P.fit_peak(stereo, -8.0), P.fit_peak(wet, -20.0))
    return P.fit_peak(out, -4.0)


def _crackle(dur=.30, seed=3):
    """Embers: two or three tiny dry ticks, high band, very short."""
    n = int(dur * SR)
    out = np.zeros((n, 2), dtype=np.float32)
    r = np.random.default_rng(seed)
    for _ in range(r.integers(2, 4)):
        at = int(r.uniform(0, n * .7))
        ln = int(r.uniform(.004, .012) * SR)
        pop = r.normal(0, 1, ln).astype(np.float32) * np.hanning(ln)
        pop = A.bp(pop, 1800, 9000).astype(np.float32)
        pan = float(r.uniform(-.5, .5))
        out[at:at + ln, 0] += pop * (1 - pan) * .5
        out[at:at + ln, 1] += pop * (1 + pan) * .5
    return P.fit_peak(out, -14.0)


def _mix2(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Sum two sounds of different lengths (a later version of numpy refuses
    to broadcast (n,2)+(m,2), which used to work by accident)."""
    n = max(len(a), len(b))
    out = np.zeros((n, 2), dtype=np.float32)
    out[:len(a)] += a
    out[:len(b)] += b
    return out


def _stone(seed=5):
    """Stone on stone: bright transient + a brief mineral ring."""
    hit = P.impact(140.0, .45, 1.0, seed)
    ring = P.marker(1760.0, .35, seed + 1)
    return _mix2(P.fit_peak(hit, -5.0), P.fit_peak(ring, -17.0))


def _roar(seed=9):
    """Mammoth: detuned saws an octave down, slow AM growl, long dark tail."""
    n = int(1.9 * SR)
    t = np.arange(n) / SR
    f0 = 68 * (1 - .18 * np.clip(t / 1.9, 0, 1))
    ph = 2 * np.pi * np.cumsum(f0) / SR
    x = np.zeros(n, dtype=np.float32)
    for k, amp in ((1, 1.0), (2, .55), (3, .32), (4.5, .18), (6.2, .10)):
        x += amp * np.sin(ph * k + rng.uniform(0, 2 * np.pi)).astype(np.float32)
    x *= 1 + .35 * np.sin(2 * np.pi * 7.3 * t)              # growl
    env = np.clip(t / .22, 0, 1) * np.exp(-np.maximum(t - .5, 0) * 1.7)
    x = (x * env).astype(np.float32)
    x = A.lp(x, 900)
    st = np.stack([x, np.roll(x, 33)], axis=1)
    wet = P.convolve(st, P.make_ir(.9, 5.0, .012, 3000, seed), wet=.35)
    return P.fit_peak(_mix2(P.fit_peak(st, -6.0), P.fit_peak(wet, -14.0)), -4.0)


def _cloth(seed=11):
    """Hide dropping: a soft noise swell with a low thump at the end."""
    n = int(.85 * SR)
    t = np.arange(n) / SR
    nz = rng.normal(0, 1, n).astype(np.float32)
    swell = A.bp(nz, 300, 2600) * np.sin(np.pi * np.clip(t / .7, 0, 1)) ** 1.6
    thump = A.lp(rng.normal(0, 1, n).astype(np.float32), 220) * np.exp(-np.maximum(t - .5, 0) * 22)
    st = lambda v: np.stack([v, np.roll(v, 27)], axis=1).astype(np.float32)   # noqa: E731
    return P.fit_peak(_mix2(P.fit_peak(st(swell), -9.0), P.fit_peak(st(thump), -12.0)), -6.0)


def _sprout(seed=13):
    """A rising, filtered chime — things starting to grow."""
    from pedalboard import Pedalboard, Reverb
    n = int(1.3 * SR)
    t = np.arange(n) / SR
    f = 420 * (1 + 1.1 * np.clip(t / 1.1, 0, 1))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    x += .3 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * np.exp(-t * 2.4)
    st = np.stack([x, np.roll(x, 51)], axis=1).astype(np.float32)
    room = Pedalboard([Reverb(room_size=.4, damping=.7, wet_level=.18, dry_level=.82)])
    st = np.ascontiguousarray(room(np.array(st.T, dtype=np.float32, order="C"), SR).T)
    return P.fit_peak(st, -8.0)


# ------------------------------------------------------------------ the cue sheet
def cues() -> list[tuple[float, str, dict, float, float]]:
    """(time, kind, kwargs, gain, pan) — times are the animation triggers."""
    c: list[tuple[float, str, dict, float, float]] = []

    def add(t, kind, g, pan=0.0, **kw):
        c.append((round(float(t), 3), kind, kw, g, pan))

    # 1 · hook — the frame slams in, one lonely marker under it
    add(B[1], "boom", .9, 0, root=44.0, dur=1.6, bright=.5, seed=11)
    add(B[1] + .02, "whoosh", .7, -.2, dur=.6, up=True, seed=12)
    add(B[1] + .55, "ping", .45, .1, freq=196.0, dur=1.5, seed=13)

    # 2 · threat — eyes open one by one
    add(B[2], "boom", .8, 0, root=40.0, dur=1.4, bright=.35, seed=21)
    add(B[2] + .02, "whoosh", .8, .25, dur=.55, up=False, seed=22)
    for i in range(3):
        add(B[2] + .5 + i * .45, "roar", .30 + .05 * i, (.25, -.25, 0)[i], seed=23 + i)

    # 3 · lightning, then the first fire
    add(B[3], "whoosh", .75, -.2, dur=.5, up=True, seed=31)
    add(B[3] + .18, "crack", .95, 0, seed=32)
    add(B[3] + .90, "whoosh", .85, .15, dur=.7, up=True, seed=33)
    add(B[3] + 1.00, "crackle", .5, .1, dur=.45, seed=34)
    add(B[3] + 1.50, "ping", .5, 0, freq=294.0, dur=1.2, seed=35)

    # 4 · warmth — sparse embers, nothing continuous
    add(B[4], "whoosh", .6, .2, dur=.5, up=False, seed=41)
    for i, dt in enumerate((.9, 1.7, 2.8)):
        add(B[4] + dt, "crackle", .34, (-.3, .35, 0)[i], dur=.30, seed=42 + i)

    # 5 · knapping — four strikes, each slightly different
    add(B[5], "whoosh", .65, -.15, dur=.45, up=True, seed=51)
    for i, at in enumerate((.75, 1.55, 2.35, 3.15)):
        add(B[5] + at, "stone", .62 + .05 * (i % 2), (-.2, .2, -.15, .15)[i], seed=52 + i)
    add(B[5] + 1.20, "ping", .40, 0, freq=330.0, dur=.5, seed=57)
    add(B[5] + 2.00, "ping", .42, 0, freq=392.0, dur=.5, seed=58)

    # 6 · the hunt — the peak of the film
    add(B[6], "boom", 1.0, 0, root=36.0, dur=1.8, bright=.85, seed=61)
    add(B[6] + .02, "whoosh", .85, .3, dur=.6, up=False, seed=62)
    add(B[6] + .80, "roar", .70, 0, seed=63)
    for i in range(3):
        add(B[6] + 1.10 + i * .26, "whoosh", .5, (-.35, 0, .35)[i], dur=.36, up=True, seed=64 + i)

    # 7 · shelter — the cloak falls, the cave settles
    add(B[7], "whoosh", .6, -.2, dur=.5, up=True, seed=71)
    add(B[7] + .55, "cloth", .75, 0, seed=72)
    add(B[7] + 1.60, "crackle", .30, .25, dur=.25, seed=73)

    # 8 · language — the rings are the cue
    add(B[8], "whoosh", .6, .2, dur=.5, up=True, seed=81)
    for i in range(3):
        add(B[8] + .35 + i * .50, "ping", .34, (-.2, .2, 0)[i], freq=(660.0, 880.0, 740.0)[i],
            dur=.6, seed=82 + i)

    # 9 · seeds, sprout, harvest
    add(B[9], "whoosh", .7, -.25, dur=.5, up=True, seed=91)
    for i in range(4):
        add(B[9] + .2 + i * .13, "ping", .22, (-.3 + .2 * i), freq=1400.0 + 120 * i,
            dur=.30, seed=92 + i)
    add(B[9] + .45, "sprout", .55, .1, seed=96)
    add(B[9] + 2.80, "ping", .48, 0, freq=392.0, dur=1.6, seed=97)

    # 10 · the payoff
    add(B[10], "boom", .95, 0, root=44.0, dur=1.7, bright=.75, seed=101)
    add(B[10] + .70, "ping", .35, .2, freq=1046.0, dur=.9, seed=102)
    add(B[10] + 1.90, "ping", .55, 0, freq=293.7, dur=1.9, seed=103)
    add(B[10] + 2.60, "whoosh", .45, .15, dur=.9, up=True, seed=104)
    add(B[10] + 4.10, "ping", .5, .1, freq=587.0, dur=2.0, seed=105)
    return c


def build(total: float = TOTAL) -> np.ndarray:
    n = A.T(total)
    out = np.zeros((n, 2), dtype=np.float32)
    for t, kind, kw, g, pan in cues():
        if t >= total:
            continue
        A.place(out, gen(kind, **kw), t, gain=g, pan=pan)
    return P.fit_peak(out, -7.0)


if __name__ == "__main__":
    import soundfile as sf
    a = build()
    path = os.path.join(OUT, "sfx_sh.wav")
    sf.write(path, a, SR, subtype="FLOAT")
    print(f"wrote {path} {len(a)/SR:.2f}s rms {P.rms_db(a):.1f} peak "
          f"{20*np.log10(np.abs(a).max()):.1f} cues {len(cues())}")
