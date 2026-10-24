#!/usr/bin/env python3
"""
sfx_v8.py — the new MonarchVoice sound-effect engine (built from scratch).

Nothing here is sampled. Every sound is synthesized in numpy from a physical
model, then optionally rendered to `audio_v8/sfx/*.wav` for inspection.

Design goals
------------
* **Typing that sounds typed.** A keystroke is modelled as four layers:
    click   – 2–7 kHz noise transient, 2–5 ms, damped
    body    – 2–3 resonant modes of a plastic/steel case (150–420 Hz, Q 6–14)
    thock   – low-passed noise burst that gives the "bottom" of the key
    release – a much quieter second click when the finger lifts (~70–110 ms)
  Six key variants + runtime randomisation (pitch, level, pan, brightness) are
  what stop it sounding like one sample fired 300 times.
* **Premium, not cartoony.** Pops are short pitch-glides with a soft click, not
  sine "boings"; whooshes are decorrelated noise through a sliding band-pass;
  metals are inharmonic modal sums (FM-free) so they ring instead of beep.
* **Every sound carries a `sync` point** — the moment it should land on the
  frame — so placement in `audio_v8.py` is frame-accurate, not approximate.
"""
from __future__ import annotations

import json
import os

import numpy as np
from scipy import signal

SR = 48000
ROOT = os.path.dirname(os.path.abspath(__file__))
KIT_DIR = os.path.join(ROOT, "audio_v8", "sfx")

rng = np.random.default_rng(2024)


# --------------------------------------------------------------------- helpers
def T(sec: float) -> int:
    return int(round(sec * SR))


def nz(n: int) -> np.ndarray:
    return rng.normal(0, 1, n).astype(np.float32)


def _sos(kind: str, f1: float, f2: float | None = None, order: int = 2):
    ny = SR / 2
    if kind == "low":
        return signal.butter(order, min(f1, ny - 200) / ny, "low", output="sos")
    if kind == "high":
        return signal.butter(order, max(20.0, f1) / ny, "high", output="sos")
    lo = max(20.0, f1) / ny
    hi = min(ny - 200.0, max(f1 + 40, f2 or f1 * 2)) / ny
    return signal.butter(order, [lo, hi], "band", output="sos")


def F(x, kind, f1, f2=None, order=2):
    return signal.sosfilt(_sos(kind, f1, f2, order), x, axis=0).astype(np.float32)


def env_exp(n: int, decay: float, attack: float = 0.0008) -> np.ndarray:
    t = np.arange(n) / SR
    e = np.exp(-t / max(decay, 1e-5))
    a = max(1, T(attack))
    e[:a] *= np.linspace(0, 1, a)
    return e.astype(np.float32)


def env_ar(n: int, attack: float, release: float, hold: float = 0.0) -> np.ndarray:
    """attack → hold → release, all in seconds, shaped with smooth curves."""
    a = max(1, T(attack))
    r = max(1, T(release))
    h = max(0, n - a - r)
    e = np.concatenate([
        np.linspace(0, 1, a) ** 0.7,
        np.ones(h) if h else np.empty(0),
        np.linspace(1, 0, r) ** 1.6,
    ])
    if h == 0 and hold:
        pass
    return e[:n].astype(np.float32)


def modal(dur: float, modes, seed_gain: float = 1.0) -> np.ndarray:
    """Sum of damped sinusoids. modes = [(freq, amp, decay_s), ...]"""
    n = T(dur)
    t = np.arange(n) / SR
    out = np.zeros(n, dtype=np.float32)
    for f, a, d in modes:
        out += (a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
                * np.exp(-t / max(d, 1e-4))).astype(np.float32)
    out[:max(1, T(0.0005))] *= np.linspace(0, 1, max(1, T(0.0005)))
    return out * seed_gain


def saturate(x: np.ndarray, drive: float = 2.0) -> np.ndarray:
    return (np.tanh(x * drive) / np.tanh(drive)).astype(np.float32)


def norm(x: np.ndarray, peak: float = 1.0) -> np.ndarray:
    m = float(np.abs(x).max())
    return (x * (peak / m) if m > 0 else x).astype(np.float32)


def stereo(x: np.ndarray, width: float = 0.0) -> np.ndarray:
    """width>0 decorrelates the channels with a tiny Haas + tilt."""
    if width <= 0:
        return np.stack([x, x], axis=1).astype(np.float32)
    d = max(1, int(width * 0.006 * SR))
    L = x.copy()
    R = np.concatenate([np.zeros(d, dtype=np.float32), x[:-d]]) if d < len(x) else x
    return np.stack([L * 0.99 + R * 0.03, R * 0.99 + L * 0.03], axis=1).astype(np.float32)


# ---------------------------------------------------------------- the keystroke
KEY_PROFILES = {
    # name        body modes (Hz)                 click band      level decay
    # levels are tuned so a phone speaker still hears the *click*: the body
    # modes carry the weight, the 2–6 kHz click and 500–900 Hz "knock" carry
    # the intelligibility. Measured on the rendered kit (see README_v8).
    "soft": dict(modes=[(196, .50, .028), (338, .28, .018)], band=(2600, 6200), cdec=.0032, thock=.16, knock=(620, .16)),
    "mid": dict(modes=[(172, .55, .032), (352, .30, .020)], band=(2900, 7000), cdec=.0028, thock=.19, knock=(700, .19)),
    "hard": dict(modes=[(158, .58, .036), (392, .34, .022)], band=(3200, 8200), cdec=.0024, thock=.22, knock=(780, .22)),
    "space": dict(modes=[(120, .66, .048), (240, .32, .030)], band=(2100, 5200), cdec=.0040, thock=.26, knock=(520, .20)),
    "return": dict(modes=[(104, .70, .058), (212, .34, .036)], band=(1800, 4800), cdec=.0048, thock=.30, knock=(460, .22)),
    "tick": dict(modes=[(420, .38, .013), (760, .24, .009)], band=(3600, 9000), cdec=.0020, thock=.07, knock=(900, .10)),
}


def keystroke(kind: str = "mid", *, pitch: float = 1.0, bright: float = 1.0,
              upstroke: bool = True) -> tuple[np.ndarray, float]:
    """A single mechanically-modelled key press. Returns (mono, sync)."""
    p = KEY_PROFILES[kind]
    n = T(0.16)
    x = np.zeros(n, dtype=np.float32)

    # 1) click transient — very short filtered noise
    lc = T(p["cdec"] * 3.2)
    click = nz(lc) * env_exp(lc, p["cdec"], 0.0002)
    click = F(click, "band", p["band"][0] * bright, p["band"][1] * bright)
    x[:lc] += norm(click, 0.85) * 1.00

    # 2) body — resonant modes of the case (the "thock")
    modes = [(f * pitch, a, d) for f, a, d in p["modes"]]
    body = modal(0.14, modes)
    body = F(body, "low", 900)
    x[:len(body)] += norm(body, 1.0) * p["thock"]

    # 2b) knock — 450–900 Hz, this is what a phone speaker actually reproduces
    kf, kg = p["knock"]
    knock = modal(0.07, [(kf * pitch, .8, .016), (kf * 1.72 * pitch, .35, .010)])
    x[:len(knock)] += norm(knock, 1.0) * kg

    # 3) bottom end — tiny low noise burst, keeps it warm on phones
    nb = T(0.012)
    low = F(nz(nb) * env_exp(nb, 0.004, 0.0004), "low", 260)
    x[:nb] += norm(low, 1.0) * 0.18 * p["thock"]

    # 4) upstroke — the finger lifting, quieter and later (this is what makes a
    #    burst of keys read as *typing* rather than a machine gun)
    if upstroke:
        dly = int(rng.uniform(0.055, 0.085) * SR)
        nu = T(0.05)
        up = nz(nu) * env_exp(nu, 0.0028, 0.0002)
        up = F(up, "band", p["band"][0] * bright * 1.15, p["band"][1] * bright * 1.1)
        up = norm(up, 1.0) * rng.uniform(0.10, 0.20)
        end = min(n, dly + nu)
        x[dly:end] += up[:end - dly]

    x = saturate(x, 1.5)
    return x.astype(np.float32), 0.0


# --------------------------------------------------------------- one-shot kit
def ui_pop(big: bool = False) -> tuple[np.ndarray, float]:
    """A modern UI pop: pitch glide + soft click. Not a cartoon boing."""
    dur = 0.13 if big else 0.085
    n = T(dur)
    t = np.arange(n) / SR
    f0, f1 = (330, 720) if big else (430, 880)
    f = f0 * (f1 / f0) ** (t / dur) ** 0.55
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = (np.sin(ph) * env_exp(n, 0.045 if big else 0.028, 0.0006)).astype(np.float32)
    tick = F(nz(T(0.004)) * env_exp(T(0.004), 0.0012, 0.0002), "band", 2400, 7000)
    tone[:len(tick)] += norm(tick, 1.0) * 0.35
    return norm(tone, 0.9), 0.0


def whoosh(kind: str = "mid", dur: float | None = None) -> tuple[np.ndarray, float]:
    """Noise through a sliding band-pass. sync = the swish peak."""
    cfg = {
        "soft": dict(dur=0.42, f=(500, 2400), q=1.6, peak=0.55),
        "mid": dict(dur=0.34, f=(700, 4200), q=1.4, peak=0.50),
        "hard": dict(dur=0.26, f=(900, 6500), q=1.2, peak=0.42),
    }[kind]
    n = T(dur or cfg["dur"])
    lo, hi = cfg["f"]
    out = np.zeros(n, dtype=np.float32)
    seg = T(0.02)
    pos = 0
    while pos < n:
        end = min(n, pos + seg)
        frac = pos / max(1, n - 1)
        f = lo * (hi / lo) ** frac
        blk = nz(end - pos)
        out[pos:end] = F(blk, "band", f * 0.62, f * 1.55)[:end - pos]
        pos = end
    env = np.sin(np.linspace(0, np.pi, n)) ** 1.35
    out *= env.astype(np.float32)
    out = F(out, "high", 260)
    return norm(out, 0.9), cfg["peak"] * (dur or cfg["dur"])


def riser(dur: float = 1.9, tone: bool = True) -> tuple[np.ndarray, float]:
    """Build-up: sliding noise band + a rising detuned saw, both crested at the end."""
    n = T(dur)
    t = np.arange(n) / SR
    noise = nz(n)
    out = np.zeros(n, dtype=np.float32)
    seg = T(0.025)
    pos = 0
    while pos < n:
        end = min(n, pos + seg)
        frac = pos / max(1, n - 1)
        f = 300 * (5200 / 300) ** (frac ** 1.5)
        out[pos:end] = F(noise[pos:end], "band", f * 0.7, f * 1.6)[:end - pos]
        pos = end
    env = (np.linspace(0, 1, n) ** 1.9).astype(np.float32)
    out *= env
    if tone:
        f0 = 110 * (3.2 ** (t / dur))
        ph = 2 * np.pi * np.cumsum(f0) / SR
        saw = (2 * ((ph / (2 * np.pi)) % 1.0) - 1).astype(np.float32)
        saw = F(saw, "low", 2600) * env * 0.28
        out += saw
    out = F(out, "high", 200)
    return norm(out, 0.9), dur * 0.93


def impact(hard: bool = False) -> tuple[np.ndarray, float]:
    """Sub hit: pitch-dropping sine + knock + air. The 'cinematic' accent."""
    dur = 1.1 if hard else 0.7
    n = T(dur)
    t = np.arange(n) / SR
    f = (108 if hard else 96) * ((34 if hard else 44) / (108 if hard else 96)) ** (t / 0.09)
    sub = (np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.24 if hard else 0.15)).astype(np.float32)
    knock = modal(0.10, [(88, .7, .045), (152, .4, .030)])
    # mid knock: without this the hit is pure sub and disappears on a phone
    mknock = modal(0.12, [(238, .55, .055), (412, .30, .032), (688, .16, .020)])
    mknock = F(mknock, "band", 200, 1600)
    crack = F(nz(T(0.02)) * env_exp(T(0.02), 0.0025, 0.0002), "band", 1400, 5200)
    air = F(nz(T(0.16)) * env_exp(T(0.16), 0.05, 0.002), "band", 2600, 9000)
    out = np.zeros(n, dtype=np.float32)
    out += norm(sub, 1.0) * 1.0
    out[:len(knock)] += norm(knock, 1.0) * (0.55 if hard else 0.40)
    out[:len(mknock)] += norm(mknock, 1.0) * (0.62 if hard else 0.52)
    out[:len(crack)] += norm(crack, 1.0) * (0.55 if hard else 0.40)
    out[:len(air)] += norm(air, 1.0) * (0.30 if hard else 0.20)
    out = saturate(out, 1.8)
    return norm(out, 0.95), 0.004


def slam() -> tuple[np.ndarray, float]:
    """Door / stamp: heavier knock, paper-ish body, short room."""
    n = T(0.85)
    out = np.zeros(n, dtype=np.float32)
    knock = modal(0.30, [(72, .80, .085), (124, .55, .055), (230, .30, .032)])
    mknock = modal(0.20, [(268, .50, .070), (455, .28, .040)])
    crack = F(nz(T(0.03)) * env_exp(T(0.03), 0.004, 0.0003), "band", 900, 4200)
    paper = F(nz(T(0.09)) * env_exp(T(0.09), 0.03, 0.004), "band", 3200, 9000)
    out[:len(knock)] += norm(knock, 1.0)
    out[:len(mknock)] += norm(mknock, 1.0) * 0.70
    out[:len(crack)] += norm(crack, 1.0) * 0.85
    out[:len(paper)] += norm(paper, 1.0) * 0.45
    out = saturate(out, 1.9)
    return norm(out, 0.97), 0.006


def clank() -> tuple[np.ndarray, float]:
    """Metal latch / iron: inharmonic modal ring with a hard initial strike."""
    n = T(1.0)
    modes = [(512, .55, .12), (877, .45, .09), (1343, .34, .07),
             (1971, .26, .05), (2980, .18, .035), (4190, .12, .022)]
    out = modal(1.0, modes)
    out = F(out, "band", 380, 8200)
    strike = F(nz(T(0.008)) * env_exp(T(0.008), 0.0018, 0.0002), "band", 1200, 8000)
    out[:len(strike)] += norm(strike, 1.0) * 0.9
    out = saturate(out, 1.4)
    return norm(out, 0.85), 0.001


def bell(freq: float = 1046.5) -> tuple[np.ndarray, float]:
    """FM bell — used sparingly for title / end-card punctuation."""
    n = T(1.4)
    t = np.arange(n) / SR
    idx = 3.2 * np.exp(-t / 0.22)
    mod = np.sin(2 * np.pi * freq * 1.41 * t + rng.uniform(0, 6.28))
    car = np.sin(2 * np.pi * freq * t + idx * mod)
    tone = (car * env_exp(n, 0.45, 0.0015)).astype(np.float32)
    tone = F(tone, "high", 220)
    shimmer = F(nz(T(0.25)) * env_exp(T(0.25), 0.07, 0.002), "band", 5200, 11000)
    tone[:len(shimmer)] += norm(shimmer, 1.0) * 0.12
    return norm(tone, 0.8), 0.002


def sparkle() -> tuple[np.ndarray, float]:
    """Bright shimmer for 'aha' moments — stacked inharmonic partials."""
    n = T(1.1)
    out = np.zeros(n, dtype=np.float32)
    base = 1400
    for i, r in enumerate([1.0, 1.51, 2.03, 2.72, 3.41, 4.19]):
        f = base * r * rng.uniform(0.98, 1.02)
        out += modal(1.1, [(f, .5 / (i + 1), .28 / (i * 0.5 + 1))])[:n]
    out = F(out, "high", 900)
    return norm(out, 0.7), 0.01


def paper_swish() -> tuple[np.ndarray, float]:
    n = T(0.30)
    x = nz(n) * env_ar(n, 0.02, 0.16)
    x = F(x, "band", 1400, 7800, order=1)
    x = F(x, "high", 700)
    return norm(x, 0.55), 0.10


# --------------------------------------------------------------------- registry
KIT = {
    # name              factory                         variants
    "key_soft": (lambda: keystroke("soft"), 5),
    "key_mid": (lambda: keystroke("mid"), 5),
    "key_hard": (lambda: keystroke("hard"), 5),
    "key_space": (lambda: keystroke("space"), 3),
    "key_return": (lambda: keystroke("return"), 3),
    "key_tick": (lambda: keystroke("tick"), 4),
    "pop": (lambda: ui_pop(False), 3),
    "pop_big": (lambda: ui_pop(True), 3),
    "whoosh_soft": (lambda: whoosh("soft"), 3),
    "whoosh_mid": (lambda: whoosh("mid"), 3),
    "whoosh_hard": (lambda: whoosh("hard"), 3),
    "riser": (lambda: riser(1.9), 2),
    "riser_short": (lambda: riser(0.9), 2),
    "impact": (lambda: impact(False), 2),
    "impact_hard": (lambda: impact(True), 2),
    "slam": (slam, 2),
    "clank": (clank, 2),
    "bell": (lambda: bell(1046.5), 2),
    "bell_low": (lambda: bell(523.25), 2),
    "sparkle": (sparkle, 2),
    "swish": (paper_swish, 3),
}


def build_kit(write: bool = True) -> dict:
    """Synthesize every variant. Returns {name: [{wav, sync, dur}, ...]}."""
    os.makedirs(KIT_DIR, exist_ok=True)
    index: dict[str, list] = {}
    total = 0
    for name, (factory, count) in KIT.items():
        items = []
        for v in range(count):
            sig, sync = factory()
            sig = norm(sig, 0.98)
            if write:
                path = os.path.join(KIT_DIR, f"{name}_{v:02d}.wav")
                _write_wav(path, sig)
                items.append({"wav": os.path.basename(path), "sync": round(float(sync), 4),
                              "dur": round(len(sig) / SR, 4)})
            total += 1
        index[name] = items
    if write:
        with open(os.path.join(KIT_DIR, "index.json"), "w") as f:
            json.dump(index, f, indent=1)
    print(f"{total} sounds from {len(KIT)} families -> {KIT_DIR}")
    return index


def _write_wav(path: str, mono: np.ndarray) -> None:
    import struct
    import wave
    pcm = np.clip(mono, -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    import sys
    kit = build_kit(write=True)
    for name, items in kit.items():
        durs = [i["dur"] for i in items]
        print(f"  {name:<12} {len(items)} var  {min(durs):.3f}–{max(durs):.3f}s  sync {items[0]['sync']:.3f}")
    print(f"\nwrote {KIT_DIR}")
