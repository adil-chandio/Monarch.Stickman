#!/usr/bin/env python3
"""sfx_synth2.py — design a premium SFX library entirely in numpy.

Every sound is built from layers (sub + body + crack + ring + tail), the way a
sound designer builds a hit, then mixed, saturated and placed in stereo.

Writes audio_v4/sfx_py/*.wav + index.json (name/kind/dur/sync/note), the same
shape sfx_pack.py produces, so audio_v3.py only has to point at this folder.
"""
import os, json, math
import numpy as np
import soundfile as sf
from scipy import signal

SR = 48000
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "audio_v4", "sfx_py")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(11)


# ------------------------------------------------------------------ helpers
def T(sec): return int(round(sec * SR))

def nz(n): return rng.normal(0, 1, n).astype(np.float32)

def filt(x, f1, f2=None, kind="band", order=2, q=None):
    ny = SR / 2
    if kind == "low":
        sos = signal.butter(order, min(f1, ny - 200) / ny, "low", output="sos")
    elif kind == "high":
        sos = signal.butter(order, max(20.0, f1) / ny, "high", output="sos")
    else:
        lo = max(20.0, f1) / ny
        hi = min(ny - 200.0, max(f1 + 60, f2)) / ny
        sos = signal.butter(order, [lo, hi], "band", output="sos")
    return signal.sosfilt(sos, x, axis=0).astype(np.float32)


def env_exp(n, decay):
    t = np.arange(n) / SR
    return np.exp(-t * decay).astype(np.float32)


def arc(n, power=1.5, up=True):
    p = np.linspace(0, 1, n, dtype=np.float32)
    base = np.abs(np.sin(np.pi * (p if up else (1 - p))))
    return (base ** power).astype(np.float32)


def fade(y, ms=5):
    f = min(T(ms / 1000), max(1, len(y) // 4))
    ramp = np.linspace(0, 1, f, dtype=np.float32)
    if y.ndim == 2:
        y[:f] *= ramp[:, None]; y[-f:] *= ramp[::-1][:, None]
    else:
        y[:f] *= ramp; y[-f:] *= ramp[::-1]
    return y


def sat(x, drive=1.8, mix=.5):
    y = np.tanh(x * drive) / np.tanh(drive)
    return (x * (1 - mix) + y * mix).astype(np.float32)


def phone_tilt(y, k=.55):
    """presence lift so low hits still read on phone speakers"""
    return y + filt(y, 240, 2800, "band") * k


def pad_to(x, n):
    x = np.asarray(x, np.float32).reshape(-1)
    return np.pad(x, (0, max(0, n - len(x))))[:n] if len(x) < n else x[:n]


def norm(y, peak=.70):
    return (y / max(float(np.abs(y).max()), 1e-9) * peak).astype(np.float32)


def stereo(y, width=.0, pan=0.0, haas_ms=None):
    if y.ndim == 2:
        return y
    a = (pan + 1) * math.pi / 4
    L, R = y * math.cos(a), y * math.sin(a)
    d = int(SR * (haas_ms if haas_ms is not None else 2.2) / 1000.0 * max(0.0, width))
    if d > 0:
        L = L + np.concatenate([np.zeros(d, np.float32), y[:-d]]) * .16
        R = R + np.concatenate([np.zeros(d * 2, np.float32), y[:-d * 2]]) * .16
    return np.stack([L, R], axis=1).astype(np.float32)


# ------------------------------------------------------------------ layers
def sub_glide(f0, f1, dur, decay, drive=2.4, harm=.16):
    """saturated sub with an exponential pitch drop"""
    n = T(dur); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 6.0)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) + harm * np.sin(2 * ph)
    return sat(y.astype(np.float32), drive, .45) * env_exp(n, decay)


def knock(f, dur, decay, drive=1.4):
    n = T(dur); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) + .30 * np.sin(4 * np.pi * f * t)
    return sat(y.astype(np.float32), drive, .35) * env_exp(n, decay)


def crack(dur=.045, decay=260.0, hp=1400.0, lp=9000.0):
    """short filtered-noise transient"""
    n = T(dur)
    return filt(nz(n), hp, lp) * env_exp(n, decay)


def fm(f, ratio, index, dur, decay, harm=0.0):
    n = T(dur); t = np.arange(n) / SR
    mod = index * np.exp(-t * decay * .35)
    y = np.sin(2 * np.pi * f * t + mod * np.sin(2 * np.pi * f * ratio * t))
    if harm:
        y = y + harm * np.sin(2 * np.pi * f * 2.0 * t + mod * .5 * np.sin(2 * np.pi * f * ratio * t))
    return (y * env_exp(n, decay)).astype(np.float32)


def tone_glide(f0, f1, dur, decay, harm=.2):
    n = T(dur); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 3.0)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) + harm * np.sin(2 * ph)
    return (y * env_exp(n, decay)).astype(np.float32)


def swept_band(n, f_lo, f_hi, segments=36, curve=1.0, q=1.3):
    """noise whose band slides from f_lo to f_hi (spectral sweep)"""
    src = nz(n)
    p = (np.arange(segments) / max(1, segments - 1)) ** curve
    seg = n // segments
    out = np.zeros(n, np.float32)
    w = np.zeros(n, np.float32)
    for i, c in enumerate(p):
        a = i * seg
        b = n if i == segments - 1 else (i + 1) * seg
        if b - a < 64:
            continue
        f = f_lo * (f_hi / f_lo) ** c
        out[a:b] += filt(src[a:b], f / q, f * q, "band", order=2)
        w[a:b] += 1.0
    return (out / np.maximum(w, 1e-6)).astype(np.float32)


def shimmer(n, f0, decay, bright=.35, spread=1.0):
    """high partials + air sparkle"""
    t = np.arange(n) / SR
    parts = []
    for i, mult in enumerate([1, 1.5, 2, 3, 4.2]):
        f = f0 * mult * spread
        parts.append(np.sin(2 * np.pi * f * t) * env_exp(n, decay * (1.0 + .35 * i)) * (1.0 - .18 * i))
    y = np.zeros(n, np.float32)
    for part in parts:
        y += part
    y += filt(nz(n), 6000, 13000) * env_exp(n, decay * .8) * bright
    return y


def clap_layer(n, delay=.055, decay=9.0, hp=1200.0):
    """layered hand-clap approximation"""
    out = np.zeros(n, np.float32)
    for k in range(4):
        st = int(k * delay * SR)
        if st >= n:
            break
        m = n - st
        burst = filt(nz(m), hp, 7500) * np.exp(-np.arange(m) / SR * (decay + 14 * k))
        out[st:] += burst * (1.0 - .16 * k)
    return out


def mix(*layers):
    """sum weighted mono layers, padding shorter ones to the longest"""
    bufs = [(float(g), np.asarray(y, np.float32).reshape(-1)) for g, y in layers]
    n = max(b.shape[0] for _, b in bufs)
    out = None
    for g, y in bufs:
        if y.shape[0] < n:
            y = np.pad(y, (0, n - y.shape[0]))
        out = y * g if out is None else out + y * g
    return out.astype(np.float32)


# ------------------------------------------------------------------ designs
def d_slam(big=True):
    dur = 2.4 if big else 1.6
    n = T(dur)
    y = mix(
        (.80, sub_glide(150, 36, dur, 3.4, 2.6)),
        (1.00, knock(86, .9, 13.0)),
        (1.15, knock(190, .5, 22.0)),
        (1.35, crack(.05, 320)),
        (1.15, fm(2300, 1.42, 2.4, 1.1, 9.0, .18)),
        (.45, filt(nz(n), 90, 420, "band") * env_exp(n, 2.6)),
        (1.00, filt(nz(n), 1400, 5200, "band") * env_exp(n, 4.0)),
    )
    if big:
        y = y * env_exp(n, .9)
    return norm(y, .78)


def d_impact(depth="medium", drive=2.0):
    cfg = {"deep": (150, 46, 1.3, 4.2, 120), "medium": (190, 62, .8, 6.0, 150),
           "light": (240, 90, .4, 9.0, 190), "heavy": (140, 40, 1.1, 4.0, 95)}[depth]
    f0, f1, dur, decay, kf = cfg
    n = T(dur + .5)
    y = mix(
        (.75, sub_glide(f0, f1, dur + .4, decay, drive)),
        (.85, knock(kf, .7, decay * 1.6)),
        (.80, knock(kf * 2.2, .4, decay * 3.0)),
        (1.10, crack(.035, 340)),
        (.75, fm(1900, 1.6, 1.8, .5, 12.0)),
        (.85, filt(nz(n), 1200, 4800, "band") * env_exp(n, 6.0)),
    )
    return norm(y, .74)


def d_boom(strong=True):
    dur = 3.6 if strong else 2.2
    n = T(dur)
    y = mix(
        (.85, sub_glide(96, 30, dur, 1.35, 2.6)),
        (.50, sub_glide(190, 60, dur * .5, 2.4, 1.6)),
        (.95, knock(120, 1.0, 3.2)),
        (.55, filt(nz(n), 60, 260, "band") * env_exp(n, 1.05)),
        (.60, fm(320, 1.0, 1.2, 1.4, 4.0, .12)),
        (.95, filt(nz(n), 1500, 5500, "band") * env_exp(n, 2.4)),
    )
    return norm(y, .80)


def d_bass(short=True):
    f = 55 if short else 110
    dur = .68 if short else 1.5
    n = T(dur + .3); t = np.arange(n) / SR
    fm_t = f * np.exp(-t * .9) if not short else f
    ph = 2 * np.pi * np.cumsum(fm_t) / SR
    y = sat(np.sin(ph).astype(np.float32), 2.0, .45) * env_exp(n, 1.5)
    y = y + pad_to(knock(f * 2, .3, 14.0), n) * .30
    return norm(y, .80)


def d_rumble(long=False):
    dur = 4.4 if long else 2.4
    n = T(dur)
    y = filt(nz(n), 40, 150, "band") * env_exp(n, .62)
    y = y + filt(nz(n), 150, 500, "band") * env_exp(n, 1.1) * .55
    y = y + filt(nz(n), 900, 3000, "band") * env_exp(n, 1.8) * .22
    return norm(y, .62)


def d_riser(strong=True, dur=None):
    dur = dur or (2.2 if strong else 1.2)
    n = T(dur)
    y = mix(
        (.85, swept_band(n, 190, 6200, 44, 1.55)),
        (.30, tone_glide(110, 760, dur, 1.6, .22)),
        (.22, filt(nz(n), 4200, 11000, "band") * arc(n, 1.8)),
    )
    y = y * arc(n, 1.6)
    y = y + filt(nz(n), 2600, 5200, "band") * (arc(n, 1.2) ** 2) * .22
    return norm(y, .66)


def d_faller(strong=True, dur=None):
    dur = dur or (2.0 if strong else 1.0)
    n = T(dur)
    y = mix(
        (.85, swept_band(n, 3000, 150, 40, 1.0)[::-1].copy()),
        (.26, tone_glide(760, 110, dur, 1.4, .2)),
    )
    y = y * arc(n, 1.4, up=False)
    return norm(y, .62)


def d_whoosh(fast=True, hard=True):
    if fast:
        dur, seg = (.25, 26) if hard else (.25, 22)
        lo, hi = (500, 6200) if hard else (700, 3800)
    elif hard:
        dur, seg, lo, hi = .55, 34, 260, 5200
    else:
        dur, seg, lo, hi = .54, 30, 300, 3000
    n = T(dur)
    y = swept_band(n, lo, hi, seg, 1.3)
    y = y * arc(n, 1.5)
    y = y + filt(nz(n), hi * .9, min(14000, hi * 2.0), "band") * arc(n, 1.9) * .35
    return norm(y, .66)


def d_reverse(strong=True):
    dur = 1.36 if strong else .84
    n = T(dur)
    y = swept_band(n, 900, 6200, 36, 1.0)[::-1].copy()
    p = np.linspace(0, 1, n, dtype=np.float32) ** 2.2
    y = y * p
    return norm(y, .62)


def d_swish(hard=True):
    dur = .17 if hard else .22
    n = T(dur)
    y = swept_band(n, 900 if hard else 700, 5200 if hard else 3000, 22, 1.1)
    y = y * arc(n, 1.1)
    return norm(y, .58)


def d_zip(hard=True):
    dur = .28 if hard else .41
    n = T(dur)
    y = swept_band(n, 1400, 3200 if hard else 1800, 26, 1.2)
    y = y * arc(n, 1.4)
    st = int(dur * .82 * SR)
    if n - st > 0:
        y[st:] += pad_to(crack(.02, 400, hp=1800), n - st) * .5
    return norm(y, .58)


def d_pop(big=True, bubble=False):
    if bubble:
        n = T(.21 if big else .13)
        t = np.arange(n) / SR
        y = np.sin(2 * np.pi * (300 - 120 * t / .21) * t) * np.exp(-t * 14)
        return norm((y + filt(nz(n), 700, 2200, "band") * np.exp(-t * 40) * .35).astype(np.float32), .6)
    n = T(.11 if big else .06)
    t = np.arange(n) / SR
    f = (420 if big else 620) * np.exp(-t * 26)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (70 if big else 120))
    return norm(y.astype(np.float32), .58)


def d_click(kind="button", drive=1.3):
    if kind == "snap":
        n = T(.13); t = np.arange(n) / SR
        n = T(.13)
        y = fm(1900, 1.0, 1.6, .13, 26.0, .2) + pad_to(crack(.02, 380, hp=2000), n) * .6
        return norm(y.astype(np.float32), .58)
    if kind == "latch":
        n = T(.045); t = np.arange(n) / SR
        y = np.sin(2 * np.pi * 1250 * t) * np.exp(-t * 90)
        y = y + pad_to(crack(.012, 500, hp=2200), n) * .5
        return norm(y.astype(np.float32), .55)
    n = T(.022); t = np.arange(n) / SR
    f = 1250 if kind == "button" else 900
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 210)
    y = y + pad_to(crack(.008, 620, hp=2600), n) * .45
    return norm(y.astype(np.float32), .52)


def d_shimmer(bright=True, sparkle=False):
    dur = 1.5 if bright else 2.2
    n = T(dur)
    y = shimmer(n, 784 if bright else 523, 2.4, .4 if bright else .25)
    if sparkle:
        y = y + filt(nz(n), 8000, 14000, "band") * env_exp(n, 5.0) * .3
    return norm(y, .48)


def d_tonal(kind="ding"):
    if kind.startswith("step"):
        k = int(kind[-1])
        f = 220 * 2 ** ((k - 1) / 5.0)
        n = T(.5)
        y = fm(f, 2.0, 1.4, .5, 6.0, .18)
        return norm(y, .52)
    f = {"high": 1318, "mid": 880, "low": 587}[kind]
    dur = {"high": .9, "mid": 1.1, "low": 1.2}[kind]
    n = T(dur)
    y = fm(f, 2.01, 2.6, dur, 3.2, .22)
    y = y + fm(f * 2, 3.0, 1.0, dur, 5.0, .1) * .3
    return norm(y, .50)


def d_stinger(bold=True):
    dur = 1.7 if bold else 1.3
    n = T(dur)
    notes = [(0, 220, .5), (.22, 330, .5), (.44, 440, .6)] if bold else [(0, 330, .4), (.2, 440, .5)]
    y = np.zeros(n, np.float32)
    for st, f, d in notes:
        i0 = T(st)
        if i0 >= n:
            break
        m = min(n - i0, T(d + .5))
        y[i0:i0 + m] += fm(f, 1.5, 2.0, m / SR, 4.0, .16) * .62
    y += filt(nz(n), 3000, 9000, "band") * arc(n, 1.8) * .16
    return norm(y, .58)


def d_move(kind="spring"):
    if kind == "zoom-in":
        n = T(.57)
        y = swept_band(n, 300, 3600, 30, 1.4) * arc(n, 1.2)
        return norm(y, .6)
    if kind == "zoom-out":
        n = T(.55)
        y = swept_band(n, 3600, 300, 28, 1.0)[::-1].copy() * arc(n, 1.0)
        return norm(y, .56)
    if kind == "spin":
        n = T(1.14)
        y = filt(nz(n), 900, 4200, "band") * env_exp(n, 2.2)
        y = y + tone_glide(660, 990, 1.14, 2.4, .15) * .25
        return norm(y, .55)
    n = T(.9)
    f = 330
    src = nz(n)
    y = filt(src, f * .6, f * 1.7, "band", order=2, q=None) * env_exp(n, 5.0)
    t = np.arange(n) / SR
    y = y + np.sin(2 * np.pi * f * t * (1 + .12 * np.sin(2 * np.pi * 11 * t))) * env_exp(n, 6.0) * .4
    return norm(y, .58)


def d_transform(kind="grow"):
    if kind == "grow":
        n = T(.69)
        y = swept_band(n, 220, 1600, 26, 1.2) * arc(n, 1.2)
        return norm(y, .56)
    if kind == "shrink":
        n = T(.6)
        y = swept_band(n, 1600, 260, 24, 1.0)[::-1].copy() * arc(n, 1.0)
        return norm(y, .54)
    if kind == "morph":
        n = T(.8)
        y = filt(nz(n), 700, 2600, "band") * env_exp(n, 3.2)
        y = y + tone_glide(300, 480, .8, 3.0, .18) * .3
        return norm(y, .52)
    n = T(.6)
    t = np.arange(n) / SR
    y = filt(nz(n), 400, 2000, "band") * np.exp(-t * 6.0)
    return norm(y, .52)


def d_poof():
    """something vanishing in a puff of air"""
    n = T(.62)
    t = np.arange(n) / SR
    y = filt(nz(n), 300, 2600, "band") * np.exp(-t * 9.0)
    y = y + filt(nz(n), 800, 3400, "band") * np.exp(-t * 17.0) * .45
    return norm(y, .58)


def d_celebrate(big=False):
    n = T(2.0 if big else 1.2)
    y = clap_layer(n, .05, 8.0) * .55
    y = y + filt(nz(n), 1800, 6500, "band") * env_exp(n, 2.6) * .18
    if big:
        y = y + shimmer(n, 1046, 1.8, .3) * .3
    return norm(y, .58)


# ------------------------------------------------------------------ library
CUR = [
    ("slam", [("cinematic-slam-big", d_slam(True), .011, "heavy door slam"),
              ("cinematic-slam-massive", d_slam(True), .084, "massive slam")]),
    ("impact", [("impact-deep-hard", d_impact("deep"), .010, "crisp crack + heavy rumble"),
                ("impact-deep-firm", d_impact("deep"), .010, "big object landing"),
                ("impact-heavy-hard", d_impact("heavy"), .010, "solid heavy hit"),
                ("impact-medium-hard", d_impact("medium"), .010, "crisp panel landing"),
                ("impact-light-hard", d_impact("light"), .010, "light tick")]),
    ("boom", [("boom-drop-strong", d_boom(True), .095, "huge sinking drop"),
              ("boom-drop-medium", d_boom(False), .052, "deep boom sinking"),
              ("boom-hit-strong", d_boom(True), .047, "big deep boom"),
              ("bass-sub-drop-medium", d_boom(False), .021, "sub drop"),
              ("bass-sub-drop-short", d_boom(False), .021, "short sub drop"),
              ("bass-808-medium", d_bass(False), .011, "tuned 808 bass"),
              ("bass-808-short", d_bass(True), .011, "short punchy 808"),
              ("bass-rumble-medium", d_rumble(False), .017, "distant rumble"),
              ("bass-rumble-long", d_rumble(True), .052, "long deep rumble")]),
    ("riser", [("riser-2s-strong", d_riser(True, 2.2), 1.978, "2s strong rise"),
               ("riser-1s-strong", d_riser(True, 1.2), .984, "1s strong rise"),
               ("riser-2s-soft", d_riser(False, 2.2), 1.994, "2s soft rise"),
               ("riser-4s-strong", d_riser(True, 4.2), 3.977, "4s strong rise")]),
    ("faller", [("faller-2s-strong", d_faller(True, 2.0), .034, "2s strong fall"),
                ("faller-1s-strong", d_faller(True, 1.0), .015, "1s bright fall"),
                ("faller-2s-soft", d_faller(False, 2.0), .011, "2s soft airy fall")]),
    ("whoosh", [("whoosh-fast-hard", d_whoosh(True, True), .092, "fast crisp whip"),
                ("whoosh-fast-soft", d_whoosh(True, False), .099, "quick gentle puff"),
                ("whoosh-medium-hard", d_whoosh(False, True), .201, "strong rush, bright crack"),
                ("whoosh-medium-medium", d_whoosh(False, False), .209, "balanced swish"),
                ("whoosh-slow-hard", d_whoosh(False, True), .403, "big slow rush"),
                ("whoosh-slow-soft", d_whoosh(False, False), .452, "long soft breath")]),
    ("reverse", [("reverse-whoosh-long-strong", d_reverse(True), 1.165, "air drawn in to a stop"),
                 ("reverse-whoosh-medium-strong", d_reverse(False), .682, "medium reverse whoosh"),
                 ("reverse-whoosh-short-strong", d_reverse(False), .340, "short reverse whoosh")]),
    ("swish", [("swish-hard", d_swish(True), .054, "fast sharp swish"),
               ("swish-soft", d_swish(False), .085, "soft thin swish")]),
    ("zip", [("zip-in-hard", d_zip(True), .188, "bright zip that lands"),
             ("zip-in-soft", d_zip(False), .294, "small thing zipping in")]),
    ("pop", [("pop-large-in", d_pop(True), .011, "full round pop"),
             ("pop-medium-in", d_pop(False), .011, "round friendly pop"),
             ("pop-small-in", d_pop(False), .010, "tiny bright pop"),
             ("pop-large-bubble", d_pop(big=True, bubble=True), .011, "deep bubble bloop"),
             ("pop-medium-bubble", d_pop(big=False, bubble=True), .011, "clean bubble plip"),
             ("appear-burst", d_pop(big=True, bubble=True), .010, "bursting apart")]),
    ("click", [("click-button-firm", d_click("button"), .009, "firm bright button click"),
               ("click-button-medium", d_click("button"), .009, "clean crisp click"),
               ("click-latch-firm", d_click("latch"), .021, "firm latch, metal tick"),
               ("click-snap-firm", d_click("snap"), .015, "sharp bright finger snap"),
               ("click-snap-medium", d_click("snap"), .015, "clean finger snap"),
               ("click-tap-firm", d_click("button"), .009, "firm touchscreen tap"),
               ("click-clap-firm", d_click("snap"), .009, "sharp hand clap")]),
    ("shimmer", [("shimmer-short-bright", d_shimmer(True), .0, "short bright shimmer"),
                 ("shimmer-medium-bright", d_shimmer(True), .0, "medium bright shimmer"),
                 ("shimmer-long-sparkle", d_shimmer(False, sparkle=True), .0, "long sparkle"),
                 ("shimmer-short-sparkle", d_shimmer(True, sparkle=True), .0, "short sparkle")]),
    ("tonal", [("tone-ding-high", d_tonal("high"), .0, "high ding"),
               ("tone-ding-mid", d_tonal("mid"), .0, "mid ding"),
               ("tone-ding-low", d_tonal("low"), .0, "low ding"),
               ("tone-step-1", d_tonal("step1"), .0, "step 1"),
               ("tone-step-2", d_tonal("step2"), .0, "step 2"),
               ("tone-step-3", d_tonal("step3"), .0, "step 3"),
               ("tone-step-4", d_tonal("step4"), .0, "step 4"),
               ("tone-step-5", d_tonal("step5"), .0, "step 5")]),
    ("stinger", [("sting-bold-short", d_stinger(True), .0, "bold sting"),
                 ("sting-bright-short", d_stinger(False), .0, "bright sting"),
                 ("sting-airy-short", d_stinger(False), .0, "airy sting")]),
    ("move", [("move-spring", d_move("spring"), 0.0, "coiled spring flicked"),
              ("move-zoom-in", d_move("zoom-in"), .489, "zooming in"),
              ("move-zoom-out", d_move("zoom-out"), 0.0, "zooming out"),
              ("move-spin", d_move("spin"), .007, "something spinning")]),
    ("transform", [("transform-grow", d_transform("grow"), .003, "swell rising"),
                   ("transform-shrink", d_transform("shrink"), 0.0, "air falling away"),
                   ("transform-morph", d_transform("morph"), .002, "soft liquid morph"),
                   ("transform-fill", d_transform("fill"), .003, "container filling")]),
    ("appear", [("appear-poof", d_poof(), .026, "vanishing in a puff of air"),
                ("appear-burst", d_pop(big=True, bubble=True), .010, "bursting apart")]),
    ("celebrate", [("celebration-applause-big", d_celebrate(True), .0, "big applause"),
                   ("celebration-confetti", d_celebrate(False), .0, "confetti burst")]),
]


def main():
    idx = []
    for kind, items in CUR:
        for name, y, sync, note in items:
            y = np.asarray(y, np.float32).reshape(-1)
            if kind in ("slam", "impact", "boom", "bass", "rumble"):
                y = phone_tilt(y, .9)
            y = norm(y, .70)
            y = stereo(y, .30, rng.uniform(-.25, .25))
            y = fade(y, 6)
            p = os.path.join(OUT, kind + "__" + name + ".wav")
            sf.write(p, y, SR, subtype="FLOAT")
            idx.append(dict(name=kind + "__" + name, kind=kind, file=name,
                            dur=round(len(y) / SR, 3), sync=sync, note=note))
            print(f"{kind:10s} {name:26s} {len(y)/SR:5.2f}s sync {sync:.3f}")
    json.dump(idx, open(os.path.join(OUT, "index.json"), "w"), indent=1)
    print(f"\n{len(idx)} sounds -> {OUT}")


if __name__ == "__main__":
    main()
