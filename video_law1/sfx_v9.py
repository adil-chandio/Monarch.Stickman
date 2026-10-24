#!/usr/bin/env python3
"""
sfx_v9.py — the animation-driven sound kit.

v8's kit covered UI + impacts + typing. v9 adds the families the *animation
map* needs: materialise / stamp / glint / fire / ember bed / metal / cloth /
digital stutter / air burst / shimmer / dust / confetti flutter / panel pop.

Everything is still synthesized from scratch (no samples) and every family
carries a `sync` point so placement is frame-exact.

Tonal elements are quantised to A-minor pentatonic (A C D E G) so unrelated
hits still sound like one palette.
"""
from __future__ import annotations

import json
import os

import numpy as np

import sfx_v8 as V8
from sfx_v8 import (SR, T, nz, F, env_exp, env_ar, modal, saturate, norm,
                    keystroke, ui_pop, whoosh, riser, impact, slam, clank, bell, sparkle)

ROOT = os.path.dirname(os.path.abspath(__file__))
KIT_DIR = os.path.join(ROOT, "audio_v9", "sfx")
rng = np.random.default_rng(9091)

# A minor pentatonic (Hz) — one palette for every pitched element
PENT = [220.0, 261.63, 293.66, 329.63, 392.0, 440.0, 523.25, 587.33, 659.25,
        783.99, 880.0, 1046.5, 1174.66, 1318.5, 1567.98, 1760.0]
rng_pent = np.random.default_rng(31)


def note(lo=0, hi=7) -> float:
    return float(PENT[rng_pent.integers(lo, hi)])


# ------------------------------------------------------------------ materialise
def materialize(big: bool = False) -> tuple[np.ndarray, float]:
    """An object arriving: sliding air + soft sub thump + a small contact tick."""
    dur = 0.80 if big else 0.45
    n = T(dur)
    lo, hi = (180, 1500) if big else (420, 3200)
    out = np.zeros(n, dtype=np.float32)
    seg = T(0.02)
    pos = 0
    while pos < n:
        end = min(n, pos + seg)
        frac = pos / max(1, n - 1)
        f = hi * (lo / hi) ** frac                      # falls: "lands"
        out[pos:end] = F(nz(end - pos), "band", f * .75, f * 1.5)[:end - pos]
        pos = end
    env = (np.sin(np.linspace(0, np.pi, n)) ** 1.1).astype(np.float32)
    out *= env * 0.55
    # contact thump at ~55 % of the swell
    t0 = int(n * 0.55)
    th = modal(0.30, [(58 if big else 92, .8, .07), (108 if big else 168, .45, .05)])
    end = min(n, t0 + len(th))
    out[t0:end] += norm(th[:end - t0], 1.0) * (0.62 if big else 0.45)
    tick = F(nz(T(0.006)) * env_exp(T(0.006), 0.0016, 0.0002), "band", 1600, 6500)
    e2 = min(n, t0 + len(tick))
    out[t0:e2] += norm(tick, 1.0) * 0.32
    out = saturate(out, 1.3)
    return norm(out, 0.9), dur * 0.55


def stamp() -> tuple[np.ndarray, float]:
    """A display word landing: thud + body + paper crack + air, 0.5 s."""
    n = T(0.55)
    out = np.zeros(n, dtype=np.float32)
    body = modal(0.34, [(96, .75, .085), (188, .45, .052), (322, .26, .030)])
    mid = modal(0.20, [(612, .34, .034), (980, .18, .020)])
    crack = F(nz(T(0.012)) * env_exp(T(0.012), 0.0022, 0.0002), "band", 1800, 7000)
    air = F(nz(T(0.18)) * env_exp(T(0.18), 0.045, 0.0015), "band", 700, 5200)
    out[:len(body)] += norm(body, 1.0)
    out[:len(mid)] += norm(mid, 1.0) * 0.55
    out[:len(crack)] += norm(crack, 1.0) * 0.50
    out[:len(air)] += norm(air, 1.0) * 0.26
    out = saturate(out, 1.6)
    return norm(out, 0.95), 0.006


def glint() -> tuple[np.ndarray, float]:
    """Glass/metallic sparkle for crowns, credit, 'aha'."""
    n = T(0.9)
    f1 = note(8, 15)
    out = modal(0.9, [(f1, .5, .34), (f1 * 2.02, .3, .18), (f1 * 3.01, .16, .10),
                      (f1 * 4.98, .08, .05)])
    out = F(out, "high", 900)
    sh = F(nz(T(0.14)) * env_exp(T(0.14), 0.035, 0.001), "band", 6000, 12000)
    out[:len(sh)] += norm(sh, 1.0) * 0.18
    return norm(out, 0.72), 0.004


def metal_tick() -> tuple[np.ndarray, float]:
    """Short inharmonic 'ting' — warnings, badges."""
    n = T(0.35)
    f = note(9, 14)
    out = modal(0.35, [(f, .6, .10), (f * 2.41, .35, .06), (f * 3.87, .2, .035)])
    out = F(out, "band", 700, 9000)
    strike = F(nz(T(0.005)) * env_exp(T(0.005), 0.0012, 0.0002), "band", 2500, 9000)
    out[:len(strike)] += norm(strike, 1.0) * 0.7
    return norm(out, 0.8), 0.001


def sway_metal() -> tuple[np.ndarray, float]:
    """Two metal tones a beat apart — the scales of justice settling."""
    a, _ = metal_tick()
    b, _ = metal_tick()
    gap = T(0.14)
    n = len(a) + gap + len(b)
    out = np.zeros(n, dtype=np.float32)
    out[:len(a)] += a * 0.9
    out[gap:gap + len(b)] += b * 0.65
    return norm(out, 0.8), 0.01


# ------------------------------------------------------------------------ fire
def fire_ignite() -> tuple[np.ndarray, float]:
    """Whoomph: rising air, then a cluster of crackles that settles."""
    dur = 1.6
    n = T(dur)
    out = np.zeros(n, dtype=np.float32)
    seg = T(0.02)
    pos = 0
    while pos < n:
        end = min(n, pos + seg)
        frac = pos / max(1, n - 1)
        f = 260 * (2600 / 260) ** min(1.0, frac * 2.2)
        g = min(1.0, frac * 5.0)
        out[pos:end] = F(nz(end - pos), "band", f * .7, f * 1.8)[:end - pos] * g
        pos = end
    out *= np.concatenate([np.ones(int(n * .25)),
                           np.exp(-np.linspace(0, 3.2, n - int(n * .25)))]).astype(np.float32)
    out += _crackles(n, rate=48, lo=1200, hi=6500, amp=.55)
    out = F(out, "band", 220, 9000)
    return norm(out, 0.9), 0.30


def _crackles(n: int, rate: float, lo: float, hi: float, amp: float = 1.0) -> np.ndarray:
    """Sparse random impulse train through a band-pass = fire/embers/paper."""
    out = np.zeros(n, dtype=np.float32)
    count = int(rate * n / SR)
    for _ in range(count):
        p = rng.integers(0, max(1, n - T(0.02)))
        ln = int(rng.integers(T(0.002), T(0.014)))
        e = nz(ln) * env_exp(ln, float(rng.uniform(0.0015, 0.006)), 0.0002)
        out[p:p + ln] += e * float(rng.uniform(0.3, 1.0))
    out = F(out, "band", lo, hi)
    return norm(out, 1.0) * amp


def ember_bed(dur: float = 2.2) -> tuple[np.ndarray, float]:
    n = T(dur)
    bed = F(nz(n), "band", 180, 1400) * np.sin(np.linspace(0, np.pi, n)) ** 1.2 * 0.25
    bed += _crackles(n, rate=26, lo=900, hi=6000, amp=.7)
    bed = bed.astype(np.float32)
    return norm(bed, 0.7), dur * 0.5


# ------------------------------------------------------------------- micro-fx
def cloth() -> tuple[np.ndarray, float]:
    n = T(0.22)
    x = F(nz(n), "band", 300, 1800) * env_ar(n, 0.02, 0.12)
    return norm(x, 0.42), 0.05


def air_burst() -> tuple[np.ndarray, float]:
    n = T(0.18)
    x = envexp = nz(n) * env_exp(n, 0.035, 0.0015)
    x = F(x, "band", 900, 6500)
    return norm(x * 0.85, 0.7), 0.004


def shimmer() -> tuple[np.ndarray, float]:
    n = T(1.0)
    out = np.zeros(n, dtype=np.float32)
    for i in range(5):
        f = note(10, 16) * (1 + i * 0.002)
        out += modal(1.0, [(f, .30 / (i + 1), .30 / (i * .4 + 1))])[:n]
    out = F(out, "high", 1200)
    return norm(out, 0.55), 0.02


def dust_air() -> tuple[np.ndarray, float]:
    n = T(0.7)
    x = F(nz(n), "band", 400, 3200) * env_ar(n, 0.09, 0.45) ** 1.3
    return norm(x, 0.42), 0.20


def confetti_flutter() -> tuple[np.ndarray, float]:
    n = T(0.9)
    out = _crackles(n, rate=60, lo=2500, hi=9000, amp=.9)
    env = env_ar(n, 0.02, 0.7) ** 1.1
    out = (out * env).astype(np.float32)
    out += F(nz(n), "band", 1500, 6000) * env * 0.18
    return norm(out, 0.6), 0.06


def digital_stutter() -> tuple[np.ndarray, float]:
    """Glitch: gated noise + bit-crush + tight echo, 0.35 s."""
    n = T(0.35)
    base = nz(n)
    gate = np.zeros(n, dtype=np.float32)
    pos = 0
    while pos < n:
        ln = int(rng.integers(T(0.012), T(0.045)))
        gate[pos:pos + ln] = 1.0
        pos += ln + int(rng.integers(T(0.004), T(0.020)))
    x = base * gate
    x = np.round(x * 8) / 8                       # bit crush
    x = F(x, "band", 900, 8000)
    d = T(0.045)
    out = x.copy()
    out[d:] += x[:-d] * 0.45
    out = saturate(out, 1.7)
    return norm(out, 0.62), 0.01


def panel_pop() -> tuple[np.ndarray, float]:
    """The blue caption bar landing — soft, round, never clicky."""
    n = T(0.10)
    t = np.arange(n) / SR
    f = 300 * (430 / 300) ** (t / 0.10)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.030, 0.001)
    x = F(x, "low", 2600)
    air = F(nz(T(0.02)) * env_exp(T(0.02), 0.005, 0.001), "band", 900, 4200)
    x[:len(air)] += norm(air, 1.0) * 0.18
    return norm(x, 0.55), 0.002


# --------------------------------------------------------------- big transition
def whoosh_huge() -> tuple[np.ndarray, float]:
    x, _ = whoosh("soft", dur=0.9)
    n = len(x)
    sub = modal(0.9, [(52, .8, .30), (78, .5, .20)])
    out = x.copy()
    out[:len(sub)] += norm(sub, 1.0) * 0.55
    return norm(out, 0.9), 0.50


# ---------------------------------------------------------------------- registry
KIT = {
    # typing (reused from v8, same physical model)
    "key_soft": (lambda: keystroke("soft"), 5),
    "key_mid": (lambda: keystroke("mid"), 5),
    "key_hard": (lambda: keystroke("hard"), 5),
    "key_space": (lambda: keystroke("space"), 3),
    "key_return": (lambda: keystroke("return"), 3),
    "key_tick": (lambda: keystroke("tick"), 4),
    # UI
    "pop": (lambda: ui_pop(False), 3),
    "pop_big": (lambda: ui_pop(True), 3),
    "panel": (panel_pop, 3),
    # arrivals
    "materialize": (lambda: materialize(False), 3),
    "materialize_big": (lambda: materialize(True), 3),
    "stamp": (stamp, 3),
    "glint": (glint, 3),
    "metal_tick": (metal_tick, 3),
    "sway_metal": (sway_metal, 2),
    "cloth": (cloth, 3),
    # fire / particles
    "fire_ignite": (fire_ignite, 2),
    "ember_bed": (lambda: ember_bed(2.2), 2),
    "dust": (dust_air, 2),
    "confetti": (confetti_flutter, 2),
    "shimmer": (shimmer, 3),
    # air / motion
    "whoosh_soft": (lambda: whoosh("soft"), 3),
    "whoosh_mid": (lambda: whoosh("mid"), 3),
    "whoosh_hard": (lambda: whoosh("hard"), 3),
    "whoosh_huge": (whoosh_huge, 2),
    "air_burst": (air_burst, 3),
    "stutter": (digital_stutter, 3),
    # weight
    "riser": (lambda: riser(1.9), 2),
    "riser_short": (lambda: riser(0.9), 2),
    "impact": (lambda: impact(False), 2),
    "impact_hard": (lambda: impact(True), 2),
    "slam": (slam, 2),
    "clank": (clank, 2),
    "bell": (lambda: bell(1046.5), 2),
    "bell_low": (lambda: bell(523.25), 2),
    "sparkle": (sparkle, 3),
    "swish": (V8.paper_swish, 3),
}


def build_kit(write: bool = True) -> dict:
    os.makedirs(KIT_DIR, exist_ok=True)
    index: dict[str, list] = {}
    total = 0
    for name, (factory, count) in KIT.items():
        items = []
        for v in range(count):
            sig, sync = factory()
            sig = norm(sig, 0.98)
            if write:
                p = os.path.join(KIT_DIR, f"{name}_{v:02d}.wav")
                V8._write_wav(p, sig)
                items.append({"wav": os.path.basename(p), "sync": round(float(sync), 4),
                              "dur": round(len(sig) / SR, 4)})
            total += 1
        index[name] = items
    if write:
        json.dump(index, open(os.path.join(KIT_DIR, "index.json"), "w"), indent=1)
    print(f"{total} sounds from {len(KIT)} families -> {KIT_DIR}")
    return index


if __name__ == "__main__":
    kit = build_kit(True)
    for name, items in kit.items():
        d = [i["dur"] for i in items]
        print(f"  {name:<16} {len(items)} var  {min(d):.3f}–{max(d):.3f}s")
