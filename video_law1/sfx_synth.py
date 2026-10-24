#!/usr/bin/env python3
"""sfx_synth.py — synthesise a broadcast-grade sound-design library in pure numpy.

Everything is generated from oscillators and filtered noise, the same vocabulary
the reference packs use, but built clean: no long tails (nothing reads as echo),
no 3-6 kHz fizz, short controlled envelopes.

Writes audio_v4/sfx/*.wav + index.json (kind, dur, ...).
"""
import os, json, math
import numpy as np
import soundfile as sf
from scipy import signal

SR = 48000
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "audio_v4", "sfx")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)


# ------------------------------------------------------------------ helpers
def T(sec): return int(round(sec * SR))

def nz(n): return rng.normal(0, 1, n).astype(np.float32)

def filt(x, f1, f2=None, kind="band", order=2):
    ny = SR / 2
    if kind == "low":
        sos = signal.butter(order, min(f1, ny - 200) / ny, "low", output="sos")
    elif kind == "high":
        sos = signal.butter(order, max(20, f1) / ny, "high", output="sos")
    else:
        lo = max(20, f1) / ny
        hi = min(ny - 200, max(f1 + 40, f2)) / ny
        sos = signal.butter(order, [lo, hi], "band", output="sos")
    return signal.sosfilt(sos, x, axis=0).astype(np.float32)

def env_exp(n, decay):
    t = np.arange(n) / SR
    return np.exp(-t * decay).astype(np.float32)

def fade(y, ms=4):
    f = min(T(ms / 1000), max(1, len(y) // 4))
    y[:f] *= np.linspace(0, 1, f)[:, None] if y.ndim == 2 else np.linspace(0, 1, f)
    y[-f:] *= np.linspace(1, 0, f)[:, None] if y.ndim == 2 else np.linspace(1, 0, f)
    return y

def sat(x, drive=1.6, mix=.5):
    y = np.tanh(x * drive) / np.tanh(drive)
    return (x * (1 - mix) + y * mix).astype(np.float32)

def norm(y, peak=.70):
    return (y / max(float(np.abs(y).max()), 1e-9) * peak).astype(np.float32)

def stereo(y, width=.0, pan=0.0):
    """mono -> stereo with equal-power pan and optional Haas width"""
    if y.ndim == 2:
        return y
    a = (pan + 1) * math.pi / 4
    L, R = y * math.cos(a), y * math.sin(a)
    if width > 0:
        d = int(SR * .0022 * width)
        L = L + np.concatenate([np.zeros(d, np.float32), y[:-d]]) * .18 * width
        R = R + np.concatenate([np.zeros(d * 2, np.float32), y[:-d * 2]]) * .18 * width
    return np.stack([L, R], axis=1).astype(np.float32)


# ------------------------------------------------------------------ elements
def sub_boom(dur=1.1, f0=150, f1=42, drive=2.4):
    n = T(dur); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 22)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 4.2)
    body += .22 * np.sin(2 * ph) * np.exp(-t * 7.0)
    return sat(body.astype(np.float32), drive, .45)


def click_tone(f=1800, dur=.06, decay=90):
    n = T(dur); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * decay)
    s += filt(nz(n), 900, 5200) * np.exp(-t * 260) * .55
    return s.astype(np.float32)


def noise_band_riser(dur=1.0, lo=260, hi=6800, curve=1.6, lo_amt=.45):
    """crossfades three noise bands upward -> a smooth airy riser"""
    n = T(dur)
    bands = [(lo, lo * 3.2), (lo * 3.0, hi * .55), (hi * .5, hi)]
    out = np.zeros(n, np.float32)
    p = np.linspace(0, 1, n, dtype=np.float32) ** curve
    w = [np.clip(1 - np.abs(p - c) / .55, 0, 1) ** 1.4 for c in (.12, .5, .88)]
    for (a, b), ww in zip(bands, w):
        out += filt(nz(n), a, b) * ww
    amp = p ** 1.5
    return (out * amp).astype(np.float32)


def swept_noise(dur=.45, lo=380, hi=3200, up=True):
    """whoosh: noise whose band energy slides, with a fast arc envelope"""
    n = T(dur)
    bands = [(lo, lo * 2.4), (lo * 2.2, hi), (hi * .9, hi * 2.2)]
    out = np.zeros(n, np.float32)
    p = np.linspace(0, 1, n, dtype=np.float32)
    q = p if up else 1 - p
    for i, (a, b) in enumerate(bands):
        c = .1 + .8 * i / max(1, len(bands) - 1)
        w = np.clip(1 - np.abs(q - c) / .5, 0, 1) ** 1.3
        out += filt(nz(n), a, b) * w
    arc = np.clip(np.sin(np.pi * np.clip(p * 1.03, 0, 1)), 0, 1) ** 1.5
    return (out * arc).astype(np.float32)


def bell(f=660, dur=1.3, ratio=3.4, index=2.2):
    n = T(dur); t = np.arange(n) / SR
    mod = index * np.exp(-t * 6.5)
    s = np.sin(2 * np.pi * f * t + mod * np.sin(2 * np.pi * f * ratio * t))
    s *= np.exp(-t * 3.4)
    s += np.sin(2 * np.pi * f * 2.005 * t) * np.exp(-t * 6.0) * .25
    return s.astype(np.float32)


def ui_tick(f=1100, dur=.09, pan=.0):
    n = T(dur); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * 120)
    s += filt(nz(n), 1500, 4500) * np.exp(-t * 320) * .35
    return s.astype(np.float32)


# ------------------------------------------------------------------ library
def build():
    items = []

    def add(name, kind, y, width=0.0, pan=0.0, peak=.66):
        y = norm(y, peak)
        y = stereo(y, width, pan) if y.ndim == 1 else y
        y = fade(y, 5)
        p = os.path.join(OUT, name + ".wav")
        sf.write(p, y, SR, subtype="FLOAT")
        items.append(dict(name=name, kind=kind, dur=round(len(y) / SR, 3), chan=int(y.shape[1])))

    # ---- impacts
    add("impact_deep", "impact",
        np.concatenate([click_tone(1500, .07, 150) * .5, sub_boom(1.25, 160, 40, 2.6)]))
    add("impact_tight", "impact", sub_boom(.75, 200, 52, 2.1))
    add("impact_huge", "impact",
        np.concatenate([filt(nz(T(.05)), 60, 900) * .8, sub_boom(1.6, 140, 34, 3.0)]))
    add("impact_soft", "impact", sub_boom(.9, 120, 46, 1.3) * .85)
    add("impact_metal", "impact",
        np.concatenate([click_tone(2600, .18, 55) * .7, sub_boom(.6, 180, 60, 1.8) * .6]))

    # ---- risers
    add("riser_air", "riser", noise_band_riser(1.15, 240, 7200, 1.5), width=.45)
    add("riser_dark", "riser", noise_band_riser(1.4, 120, 2600, 1.9, .35), width=.3)
    add("riser_short", "riser", noise_band_riser(.62, 380, 6800, 1.2), width=.35)
    add("riser_tonal", "riser",
        (noise_band_riser(1.05, 300, 5200, 1.4, .3) * .7 +
         np.sin(2 * np.pi * np.cumsum(np.linspace(220, 880, T(1.05))) / SR) *
         np.linspace(0, 1, T(1.05)) ** 2 * .25).astype(np.float32), width=.25)
    add("riser_suck", "riser", noise_band_riser(.9, 180, 3600, 2.6, .5)[::-1].copy(), width=.5)

    # ---- whooshes
    add("whoosh_fast", "whoosh", swept_noise(.38, 420, 3600), width=.85, pan=.1)
    add("whoosh_wide", "whoosh", swept_noise(.55, 300, 3000), width=1.0)
    add("whoosh_soft", "whoosh", swept_noise(.62, 260, 1800), width=.7, pan=-.1)
    add("whoosh_rev", "whoosh", swept_noise(.45, 500, 4200, up=False), width=.8, pan=.15)
    add("whoosh_thin", "whoosh", swept_noise(.30, 900, 5200), width=.6, pan=-.15)

    # ---- downlifters
    add("down_soft", "downlifter", swept_noise(.55, 200, 2600, up=False) * .9, width=.5)
    add("down_deep", "downlifter",
        (swept_noise(.7, 120, 1800, up=False) +
         np.sin(2 * np.pi * np.cumsum(np.linspace(180, 60, T(.7))) / SR) *
         np.linspace(1, 0, T(.7)) ** 1.4 * .35).astype(np.float32), width=.3)
    add("down_quick", "downlifter", swept_noise(.32, 400, 3200, up=False), width=.4)

    # ---- clicks / ticks
    add("tick_ui", "click", ui_tick(1250), pan=.25, peak=.5)
    add("tick_soft", "click", ui_tick(900, .11), pan=-.25, peak=.45)
    add("tick_bright", "click", ui_tick(1900, .07), pan=.15, peak=.5)
    add("tick_low", "click", ui_tick(620, .13), pan=.0, peak=.45)

    # ---- tonal accents
    add("bell_a", "tonal", bell(880, 1.4), width=.35, peak=.5)
    add("bell_e", "tonal", bell(659.3, 1.6), width=.4, peak=.45)
    add("bell_hi", "tonal", bell(1318.5, .9, 2.1, 1.2), width=.5, peak=.38)
    add("marimba", "tonal", bell(440, .7, 4.0, 1.0) * .9, width=.2, peak=.5)

    json.dump(items, open(os.path.join(OUT, "index.json"), "w"), indent=1)
    print(f"wrote {len(items)} sounds to {OUT}")
    for it in items:
        print(f"  {it['kind']:10s} {it['name']:14s} {it['dur']:5.2f}s")


if __name__ == "__main__":
    build()
