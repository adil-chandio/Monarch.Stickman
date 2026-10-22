#!/usr/bin/env python3
"""Compose an ORIGINAL 30-second stereo score, foley and narrated mix.

Every sound here is synthesised from scratch with NumPy: no stock music, no
sample libraries. The arrangement is cut to the reel, shot by shot:

    0.0 -  5.0   night watch      cold wind, night insects, a lone footstep
    5.0 - 10.0   fire lit         ignition whoosh, roar, crackles, voices
   10.0 - 14.0   knapping         seven stone strikes on the on-screen beat
   14.0 - 18.0   trek             grass footsteps, cloth, wind, birds
   18.0 - 23.0   campfire again   fire swell, embers, laughter-free warmth
   23.0 - 30.0   reveal           build, taiko hits, final impact + resolve

Mix chain: synthetic room reverb on music + foley, sidechain duck under the
narrator, soft-knee bus compression and a peak-safe master.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RATE = 48000
LENGTH = 30.0
SAMPLES = round(RATE * LENGTH)
RNG = np.random.default_rng(20261022)

# The knapping loop in scenes3d.py: one impact every STRIKE_PERIOD seconds.
STRIKE_PERIOD = 0.62
STRIKE_START = 10.0
SHOT_CUTS = (5.0, 10.0, 14.0, 18.0, 23.0)
CAPTION_CUTS = (6.40, 11.50, 14.92, 18.48, 22.67, 25.50, 27.65)


# --------------------------------------------------------------------- utils
def add(sound: np.ndarray, track: np.ndarray, when: float, pan: float = 0.0,
        gain: float = 1.0) -> None:
    """Mix a mono (or stereo) clip into a stereo track at `when` seconds."""
    begin = round(when * RATE)
    if begin < 0:
        cut = -begin
        sound = sound[cut:]
        begin = 0
    if begin >= SAMPLES or len(sound) == 0:
        return
    sound = sound[: SAMPLES - begin]
    left = math.cos((pan + 1) * math.pi / 4) * gain
    right = math.sin((pan + 1) * math.pi / 4) * gain
    if sound.ndim == 1:
        track[begin:begin + len(sound), 0] += sound * left
        track[begin:begin + len(sound), 1] += sound * right
    else:
        track[begin:begin + len(sound), 0] += sound[:, 0] * left
        track[begin:begin + len(sound), 1] += sound[:, 1] * right


def tline(duration: float) -> np.ndarray:
    return np.arange(round(duration * RATE), dtype=np.float32) / RATE


def shaped_noise(count: int, smooth: int, seed: int | None = None) -> np.ndarray:
    """Boxcar-smooth white noise: cheap low-pass, O(n) in NumPy."""
    gen = np.random.default_rng(seed) if seed is not None else RNG
    noise = gen.normal(0, 1, count + smooth).astype(np.float32)
    sums = np.cumsum(noise, dtype=np.float64)
    return ((sums[smooth:] - sums[:-smooth]) / smooth).astype(np.float32)


def bandpass(count: int, low: int, high: int, seed: int | None = None) -> np.ndarray:
    """Difference of two boxcars: a soft band-pass that stays NumPy-only."""
    return shaped_noise(count, low, seed) - shaped_noise(count, high, seed)


def sweep_sine(t: np.ndarray, f0: float, f1: float) -> np.ndarray:
    k = t / max(t[-1], 1e-6)
    return np.sin(2 * np.pi * (f0 * t + (f1 - f0) * t * k * 0.5)).astype(np.float32)


def adsr(n: int, attack: float, decay: float, power: float = 1.0) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / RATE
    env = np.minimum(1.0, t / max(attack, 1e-4)) * np.exp(-np.maximum(0.0, t - attack)
                                                            / max(decay, 1e-4))
    return (env ** power).astype(np.float32)


def fade_edges(sound: np.ndarray, ms: float = 3.0) -> np.ndarray:
    n = max(2, int(RATE * ms / 1000))
    if len(sound) < 2 * n:
        return sound
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    sound = sound.copy()
    sound[:n] *= ramp
    sound[-n:] *= ramp[::-1]
    return sound


# ------------------------------------------------------------------ reverbs
def make_ir(seconds: float = 1.5, bright: float = 0.55, seed: int = 7) -> np.ndarray:
    """Synthetic stereo room impulse response: early taps + decaying noise tail."""
    n = round(seconds * RATE)
    gen = np.random.default_rng(seed)
    tail = gen.normal(0, 1, n).astype(np.float32)
    tail *= np.exp(-np.arange(n, dtype=np.float32) / (0.30 * n)) ** 1.4
    # Darken with a short moving average so it reads as a room, not a hiss.
    k = max(4, int(60 * bright))
    tail = np.convolve(tail, np.ones(k, dtype=np.float32) / k, mode="same").astype(np.float32)
    ir = np.zeros((n, 2), dtype=np.float32)
    ir[:, 0] = tail
    ir[:, 1] = np.roll(tail, 37) * 0.92
    for tap_ms, g in ((11, 0.55), (23, 0.40), (37, 0.30), (53, 0.22), (79, 0.15)):
        idx = int(tap_ms * RATE / 1000)
        if idx < n:
            ir[idx, 0] += g
            ir[idx + 5 if idx + 5 < n else idx, 1] += g * 0.9
    # normalise the transfer function, not just the energy: the tail is very
    # low-frequency heavy, so an energy norm would boost bass by ~5x
    spec = np.fft.rfft(ir, axis=0)
    scale = float(np.max(np.abs(spec))) + 1e-9
    return (ir / scale).astype(np.float32)


def convolve_stereo(track: np.ndarray, ir: np.ndarray) -> np.ndarray:
    n = len(track) + len(ir) - 1
    size = 1 << (n - 1).bit_length()
    out = np.zeros_like(track)
    for ch in (0, 1):
        spec = np.fft.rfft(track[:, ch], size) * np.fft.rfft(ir[:, ch], size)
        wet = np.fft.irfft(spec, size)[:len(track)]
        out[:, ch] = wet.astype(np.float32)
    return out


# ------------------------------------------------------------------- voices
def note(freq: float, duration: float, amp: float, attack: float, release: float,
         kind: str = "pad") -> np.ndarray:
    t = tline(duration)
    if len(t) == 0:
        return np.empty(0, dtype=np.float32)
    if kind == "wood":
        signal = (np.sin(2 * np.pi * freq * t)
                  + 0.32 * np.sin(2 * np.pi * freq * 2.01 * t)
                  + 0.12 * np.sin(2 * np.pi * freq * 3.97 * t))
        env = (1 - np.exp(-t / max(attack, 0.002))) * np.exp(-t / 0.31)
    elif kind == "bell":
        signal = (np.sin(2 * np.pi * freq * t)
                  + 0.42 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t * 3.2)
                  + 0.21 * np.sin(2 * np.pi * freq * 5.40 * t) * np.exp(-t * 6.0))
        env = (1 - np.exp(-t / max(attack, 0.002))) * np.exp(-t * 2.1)
    elif kind == "string":
        drift = 0.004 * np.sin(2 * np.pi * 0.31 * t)
        signal = (np.sin(2 * np.pi * freq * t + drift)
                  + 0.30 * np.sin(2 * np.pi * 2.002 * freq * t)
                  + 0.14 * np.sin(2 * np.pi * 3.01 * freq * t)
                  + 0.07 * np.sin(2 * np.pi * 4.02 * freq * t))
        env = (np.minimum(1, t / max(attack, 0.002))
               * np.minimum(1, np.maximum(0, duration - t) / max(release, 0.002)))
    else:
        drift = 0.006 * np.sin(2 * np.pi * 0.28 * t)
        signal = (np.sin(2 * np.pi * freq * t + drift)
                  + 0.16 * np.sin(2 * np.pi * (2 * freq + 0.6) * t))
        env = (np.minimum(1, t / max(attack, 0.002))
               * np.minimum(1, np.maximum(0, duration - t) / max(release, 0.002)))
    return (signal * env * amp).astype(np.float32)


def kick(amp: float = 1.0) -> np.ndarray:
    t = tline(0.62)
    phase = 2 * np.pi * (46 * t + 5.2 * (1 - np.exp(-14 * t)))
    body = np.sin(phase) * np.exp(-t * 9.0)
    click = RNG.normal(0, 1, len(t)) * np.exp(-t * 150) * 0.06
    return fade_edges(((body + click) * 0.105 * amp).astype(np.float32))


def frame_drum(amp: float = 1.0) -> np.ndarray:
    t = tline(0.55)
    tone = np.sin(2 * np.pi * (94 - 22 * t) * t) * np.exp(-t * 12)
    skin = bandpass(len(t), 3, 26) * np.exp(-t * 26) * 0.55
    return fade_edges(((tone * 0.11 + skin * 0.05) * amp).astype(np.float32))


def taiko(amp: float = 1.0) -> np.ndarray:
    t = tline(1.1)
    tone = np.sin(2 * np.pi * (68 - 14 * t) * t) * np.exp(-t * 4.2)
    slap = bandpass(len(t), 2, 18) * np.exp(-t * 30) * 0.42
    return fade_edges(((tone * 0.16 + slap * 0.07) * amp).astype(np.float32))


def wood_tap(amp: float = 1.0) -> np.ndarray:
    t = tline(0.17)
    body = np.sin(2 * np.pi * (196 - 52 * t) * t) * np.exp(-t * 34)
    splinter = RNG.normal(0, 1, len(t)) * np.exp(-t * 96)
    return fade_edges(((body * 0.040 + splinter * 0.014) * amp).astype(np.float32))


def whoosh(duration: float = 0.5, amp: float = 1.0) -> np.ndarray:
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    raw = bandpass(n, 9, 42)
    env = np.sin(np.pi * np.minimum(1, t / duration)) ** 1.7
    shimmer = np.sin(2 * np.pi * (410 * t + 1400 * t * t)) * 0.16
    return fade_edges(((raw + shimmer) * env * 0.085 * amp).astype(np.float32))


def riser(duration: float = 1.1, gain: float = 1.0, f0: float = 180,
          f1: float = 900) -> np.ndarray:
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    env = (t / duration) ** 2.2
    sweep = sweep_sine(t, f0, f1)
    air = bandpass(n, 5, 30) * 0.7
    return fade_edges(((sweep * 0.020 + air * 0.045) * env * gain).astype(np.float32))


def impact(gain: float = 1.0) -> np.ndarray:
    n = round(1.05 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    sub = np.sin(2 * np.pi * (52 - 9 * t) * t) * np.exp(-t * 4.0)
    snap = RNG.normal(0, 1, n) * np.exp(-t * 34) * 0.18
    body = bandpass(n, 2, 14) * np.exp(-t * 7.0) * 0.5
    return fade_edges(((sub * 0.13 + snap * 0.05 + body * 0.05) * gain).astype(np.float32))


def stone_strike(amp: float = 1.0, bright: float = 1.0) -> np.ndarray:
    """Flint on flint: a hard transient, a metallic ring and a shower of grit."""
    n = round(0.30 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    crack = RNG.normal(0, 1, n) * np.exp(-t * 240) * 0.30 * bright
    ping = (np.sin(2 * np.pi * 3150 * t) * 0.5
            + np.sin(2 * np.pi * 4720 * t) * 0.3
            + np.sin(2 * np.pi * 6890 * t) * 0.16) * np.exp(-t * 42) * 0.13
    thud = np.sin(2 * np.pi * (150 - 40 * t) * t) * np.exp(-t * 46) * 0.18
    grit = bandpass(n, 2, 9) * np.exp(-t * 14) * 0.10
    return fade_edges(((crack + ping + thud + grit) * amp).astype(np.float32))


def stone_chip() -> np.ndarray:
    n = round(0.14 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    bright = np.sin(2 * np.pi * (2100 * t - 1300 * t * t)) * np.exp(-t * 62)
    grit = RNG.normal(0, 1, n) * np.exp(-t * 112)
    return fade_edges(((bright * 0.045 + grit * 0.026)).astype(np.float32))


def cloth(duration: float = 0.30, amp: float = 1.0) -> np.ndarray:
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    env = np.sin(np.pi * t / duration) ** 1.6
    raw = bandpass(n, 2, 12)
    return fade_edges((raw * env * 0.055 * amp).astype(np.float32))


def rustle(duration: float = 0.36) -> np.ndarray:
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    env = np.sin(np.pi * t / duration) ** 2
    return fade_edges((shaped_noise(n, 5) * env * 0.055).astype(np.float32))


def footstep(weight: float = 1.0, grass: float = 1.0) -> np.ndarray:
    n = round(0.30 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    thud = np.sin(2 * np.pi * (78 - 30 * t) * t) * np.exp(-t * 24)
    crunch = bandpass(n, 2, 7) * np.exp(-t * 30) * 0.55 * grass
    grit = shaped_noise(n, 3) * np.exp(-t * 48) * 0.30
    return fade_edges(((thud * 0.062 + crunch * 0.045 + grit * 0.022) * weight).astype(np.float32))


def fire_pop() -> np.ndarray:
    n = round(0.075 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    return fade_edges((RNG.normal(0, 1, n) * np.exp(-t * 150) * 0.055).astype(np.float32))


def fire_roar(duration: float, amp: float = 1.0, seed: int = 11) -> np.ndarray:
    """Continuous fire bed: low rumble whose body breathes with the flames."""
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    body = shaped_noise(n, 90, seed)
    hiss = shaped_noise(n, 6, seed + 1) * 0.22
    breath = 0.62 + 0.38 * np.sin(2 * np.pi * 0.31 * t + 1.1) ** 2
    gust = 0.80 + 0.20 * np.sin(2 * np.pi * 0.13 * t)
    return ((body * 0.115 + hiss * 0.045) * breath * gust * amp).astype(np.float32)


def wind_bed(duration: float, amp: float = 1.0, seed: int = 5) -> np.ndarray:
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    body = shaped_noise(n, 200, seed)
    air = shaped_noise(n, 24, seed + 3) * 0.28
    gust = 0.45 + 0.55 * np.sin(2 * np.pi * 0.09 * t + 0.7) ** 2
    return ((body * 0.105 + air * 0.055) * gust * amp).astype(np.float32)


def crickets(duration: float, amp: float = 1.0) -> np.ndarray:
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    out = np.zeros(n, dtype=np.float32)
    for base, rate, phase in ((4300, 17.0, 0.3), (5100, 13.0, 1.9), (3700, 21.0, 3.1)):
        gate = (np.sin(2 * np.pi * rate * t + phase) > 0.72).astype(np.float32)
        gate *= (0.5 + 0.5 * np.sin(2 * np.pi * 0.37 * t + phase))
        out += np.sin(2 * np.pi * base * t) * gate
    return (out * 0.011 * amp).astype(np.float32)


def owl_call(amp: float = 1.0) -> np.ndarray:
    n = round(1.4 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    f = 392 - 34 * t
    tone = np.sin(2 * np.pi * f * t) + 0.18 * np.sin(4 * np.pi * f * t)
    env = np.minimum(1, t / 0.05) * np.exp(-t * 2.6)
    return fade_edges((tone * env * 0.028 * amp).astype(np.float32))


def breath(amp: float = 1.0) -> np.ndarray:
    n = round(0.62 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    env = np.sin(np.pi * np.minimum(1, t / 0.62)) ** 1.5
    return fade_edges((bandpass(n, 12, 60) * env * 0.030 * amp).astype(np.float32))


def crackle_burst(duration: float = 1.0, density: float = 26.0) -> np.ndarray:
    n = round(duration * RATE)
    out = np.zeros(n, dtype=np.float32)
    gen = np.random.default_rng(int(duration * 1000) + 5)
    for _ in range(int(duration * density)):
        at = int(gen.random() * (n - 400))
        length = int(gen.integers(40, 260))
        t = np.arange(length, dtype=np.float32) / RATE
        out[at:at + length] += (gen.normal(0, 1, length)
                                * np.exp(-t * gen.uniform(90, 260))).astype(np.float32)
    return fade_edges(out * 0.05)


# -------------------------------------------------------------------- score
def score_and_foley() -> tuple[np.ndarray, np.ndarray]:
    music = np.zeros((SAMPLES, 2), dtype=np.float32)
    foley = np.zeros((SAMPLES, 2), dtype=np.float32)

    # ---- harmony: D minor drifting to B-flat, G minor, A and home again ----
    chords = [
        (0.00, 5.00, (73.42, 110.00, 174.61, 220.00)),
        (5.00, 10.00, (116.54, 146.83, 174.61, 233.08)),
        (10.00, 14.00, (98.00, 116.54, 146.83, 196.00)),
        (14.00, 18.00, (110.00, 138.59, 164.81, 220.00)),
        (18.00, 23.00, (87.31, 130.81, 174.61, 220.00)),
        (23.00, 27.65, (110.00, 146.83, 174.61, 220.00)),
        (27.65, 30.00, (146.83, 220.00, 293.66, 349.23)),
    ]
    for start, end, freqs in chords:
        span = end - start
        for j, freq in enumerate(freqs):
            add(note(freq, span, 0.0135 - 0.0014 * j, 0.55, 0.7, kind="string"),
                music, start, pan=(-0.52, -0.18, 0.18, 0.52)[j])
            add(note(freq * 0.5, span, 0.008, 0.9, 0.9, kind="pad"), music, start,
                pan=(-0.2, 0.2)[j % 2])
        # a single low drone tying the whole reel together
        add(note(freqs[0] * 0.5, span, 0.010, 1.2, 1.2), music, start, pan=0.0)

    # ---- pulse: frame drum from the fire onwards, taiko in the reveal ------
    beat = 60 / 96
    t = 5.0
    idx = 0
    while t < 29.4:
        strong = idx % 4 == 0
        add(frame_drum(0.85 if strong else 0.55), music, t, pan=0.0 if strong else 0.16)
        if t >= 14.0:
            add(wood_tap(0.5), music, t + beat * 0.5, pan=-0.35)
        t += beat
        idx += 1
    for at, amp in ((23.0, 0.9), (25.5, 0.95), (27.65, 1.15), (29.1, 0.7)):
        add(taiko(amp), music, at, pan=0.0)

    # ---- motif: a five-note figure that resolves on the end card ----------
    motif = (587.33, 440.00, 349.23, 440.00, 523.25, 349.23, 293.66, 587.33)
    step = 0.0
    i = 0
    while 6.0 + step < 27.4:
        moment = 6.0 + step
        amp = 0.012 if moment < 18 else 0.016
        if moment >= 23.0:
            amp = 0.020
        add(note(motif[i % len(motif)], 0.85, amp, 0.004, 0.12, kind="bell"),
            music, moment, pan=-0.42 if i % 2 else 0.42)
        step += 0.6
        i += 1

    # ---- ambience per shot ------------------------------------------------
    add(wind_bed(5.4, 0.85, seed=5), foley, 0.0, pan=-0.45)
    add(wind_bed(4.2, 0.55, seed=9), foley, 5.0, pan=0.5)
    add(wind_bed(4.1, 0.80, seed=13), foley, 13.9, pan=-0.3)
    add(wind_bed(5.0, 0.50, seed=17), foley, 18.0, pan=0.42)
    add(wind_bed(7.1, 0.42, seed=21), foley, 22.9, pan=-0.35)
    add(crickets(9.6, 1.0), foley, 0.1, pan=-0.6)
    add(crickets(4.6, 0.8), foley, 5.2, pan=0.55)
    add(crickets(7.0, 0.5), foley, 18.0, pan=-0.5)
    add(owl_call(1.0), foley, 3.05, pan=-0.35)
    add(owl_call(0.6), foley, 21.1, pan=0.5)
    for at in (1.9, 8.7, 9.45, 15.4, 16.35, 24.4, 26.2):
        add(note(1050 + (at * 37) % 480, 0.20, 0.010, 0.01, 0.09, kind="bell"),
            foley, at, pan=0.6 if int(at) % 2 else -0.6)

    # ---- shot 1: night watch ---------------------------------------------
    add(footstep(1.0, 0.7), foley, 0.55, pan=-0.10)
    add(footstep(0.8, 0.7), foley, 1.35, pan=0.08)
    add(cloth(0.45, 0.9), foley, 2.4, pan=0.2)
    add(footstep(0.75, 0.8), foley, 3.7, pan=-0.15)
    add(breath(0.8), foley, 4.35, pan=0.05)
    add(whoosh(0.6, 0.9), foley, 4.72, pan=-0.5)
    add(impact(0.55), foley, 5.0, pan=0.0)

    # ---- shot 2: the fire is lit -----------------------------------------
    add(riser(0.75, 0.9, 220, 1200), foley, 4.35, pan=0.1)
    add(whoosh(0.5, 1.1), foley, 4.95, pan=0.35)
    roar_a = fire_roar(5.2, 1.0, seed=31)
    swell = np.minimum(1.0, np.arange(len(roar_a), dtype=np.float32) / (0.35 * RATE))
    add((roar_a * swell).astype(np.float32), foley, 5.0, pan=0.0)
    for at in np.arange(5.35, 9.85, 0.37):
        add(fire_pop(), foley, float(at + RNG.uniform(-0.08, 0.08)),
            pan=float(RNG.uniform(-0.45, 0.45)), gain=float(RNG.uniform(0.55, 1.0)))
    add(crackle_burst(1.4, 22.0), foley, 5.6, pan=-0.2)
    add(crackle_burst(1.6, 18.0), foley, 7.4, pan=0.25)
    for at in (6.2, 8.15):
        add(wood_tap(0.8) * 1.0, foley, at, pan=0.1)
    add(breath(0.9), foley, 7.9, pan=-0.25)
    add(cloth(0.35, 0.8), foley, 8.9, pan=0.3)

    # ---- shot 3: knapping (locked to the on-screen strikes) --------------
    strikes = [STRIKE_START + k * STRIKE_PERIOD for k in range(7)]
    for k, at in enumerate(strikes):
        if at > 13.9:
            break
        amp = 1.0 if k % 2 == 0 else 0.86
        add(stone_strike(amp, bright=1.0 if k % 2 == 0 else 0.9), foley, at, pan=-0.12)
        add(cloth(0.16, 0.7), foley, at - 0.24, pan=-0.18)      # arm lift
        for j in range(3):                                       # chips landing
            add(stone_chip(), foley, at + 0.10 + j * 0.055 + RNG.uniform(0, 0.03),
                pan=float(RNG.uniform(-0.5, 0.5)), gain=float(RNG.uniform(0.45, 0.9)))
        add(fire_pop() * 0.5, foley, at + 0.05, pan=0.3, gain=0.4)
    add(breath(0.8), foley, 12.7, pan=0.1)
    add(whoosh(0.55, 1.0), foley, 13.6, pan=0.45)
    add(impact(0.6), foley, 14.0, pan=0.0)

    # ---- shot 4: the trek --------------------------------------------------
    for k, pan in enumerate((-0.28, 0.0, 0.3)):
        phase = 0.31 * k
        at = 14.15 + phase
        while at < 17.85:
            add(footstep(0.9 if k == 0 else 0.7, 1.15), foley, float(at), pan=pan)
            at += 0.58
    add(cloth(0.5, 1.0), foley, 15.1, pan=-0.2)
    add(cloth(0.5, 0.8), foley, 16.6, pan=0.25)
    add(breath(0.7), foley, 17.6, pan=0.0)
    add(whoosh(0.55, 1.0), foley, 17.6, pan=-0.45)
    add(impact(0.65), foley, 18.0, pan=0.0)

    # ---- shot 5: camp, embers, the reveal ---------------------------------
    add(riser(0.9, 0.85, 160, 780), foley, 17.3, pan=0.15)
    roar_b = fire_roar(5.6, 0.9, seed=41)
    add(roar_b, foley, 18.0, pan=0.05)
    for at in np.arange(18.2, 22.9, 0.34):
        add(fire_pop(), foley, float(at + RNG.uniform(-0.07, 0.07)),
            pan=float(RNG.uniform(-0.45, 0.45)), gain=float(RNG.uniform(0.5, 1.0)))
    add(crackle_burst(2.2, 16.0), foley, 19.0, pan=0.3)
    add(cloth(0.45, 0.9), foley, 20.2, pan=-0.3)
    add(whoosh(0.7, 1.2), foley, 22.2, pan=0.5)
    add(impact(0.85), foley, 23.0, pan=0.0)
    add(riser(1.1, 1.15, 200, 1400), foley, 22.0, pan=-0.1)
    add(riser(1.6, 1.25, 120, 1800), foley, 26.05, pan=0.2)
    # final reveal: a wide hit, a low tail and a bright bell
    add(impact(1.25), foley, 27.65, pan=0.0)
    add(taiko(1.2), foley, 27.65, pan=0.0)
    add(note(587.33, 2.3, 0.016, 0.004, 1.4, kind="bell"), foley, 27.68, pan=-0.3)
    add(note(880.00, 2.1, 0.012, 0.004, 1.5, kind="bell"), foley, 27.70, pan=0.32)
    add(whoosh(0.9, 1.1), foley, 27.2, pan=0.0)

    # soft tick for every caption change so the text feels designed in
    for at in CAPTION_CUTS:
        add(whoosh(0.30, 0.35), foley, at - 0.05, pan=0.0)
    return music, foley


# --------------------------------------------------------------------- mix
def narration_at_48k() -> np.ndarray:
    with wave.open(str(HERE / "narration.wav"), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("Expected the selected narrator's 16-bit mono WAV")
        rate = source.getframerate()
        voice = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
    voice = voice.astype(np.float32) / 32768
    indices = np.arange(SAMPLES, dtype=np.float32) * (rate / RATE)
    resampled = np.interp(indices, np.arange(len(voice)), voice,
                          left=0, right=0).astype(np.float32)
    # Presence lift: subtract a smoothed copy so consonants cut through the mix.
    smooth = np.convolve(resampled, np.ones(24, dtype=np.float32) / 24, mode="same")
    resampled = resampled + 0.55 * (resampled - smooth)
    # 2.4:1 crest control then makeup gain.
    magnitude = np.abs(resampled)
    compressed = np.where(magnitude <= 0.16, magnitude,
                          0.16 + (magnitude - 0.16) / 2.4)
    return (np.sign(resampled) * compressed * 1.22).astype(np.float32)


def create_mix(path: Path | None = None) -> Path:
    path = path or HERE / "_build" / "final_mix.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    music, foley = score_and_foley()
    voice = narration_at_48k()

    # A shared room so score and effects sit in the same world.
    ir = make_ir(1.6, 0.6)
    music = music * 0.82 + convolve_stereo(music, ir) * 0.26
    foley = foley * 0.88 + convolve_stereo(foley, ir) * 0.20

    # Sidechain: dip the music under every spoken word.
    activity = np.abs(voice).astype(np.float64)
    window = round(0.100 * RATE)
    cumulative = np.concatenate(([0.0], np.cumsum(activity)))
    smoothed = (cumulative[window:] - cumulative[:-window]) / window
    pad = window // 2
    smoothed = np.pad(smoothed, (pad, SAMPLES - len(smoothed) - pad), mode="edge")
    duck = np.clip(smoothed / 0.030, 0, 1)
    response = round(0.110 * RATE)
    padded = np.pad(duck, (response, 0), mode="edge")
    running = np.concatenate(([0.0], np.cumsum(padded)))
    curve = (running[response:] - running[:-response])[:SAMPLES] / response
    music_gain = (1.70 - 0.58 * curve.astype(np.float32))
    # Let the score breathe at the open, the cuts and the end card.
    for at, width, lift in ((0.0, 1.2, 0.30), (5.0, 0.8, 0.18), (10.0, 0.6, 0.12),
                            (14.0, 0.6, 0.12), (18.0, 0.8, 0.20), (23.0, 0.9, 0.24),
                            (27.6, 2.4, 0.55)):
        t = np.arange(SAMPLES, dtype=np.float32) / RATE
        music_gain += lift * np.exp(-((t - at) / width) ** 2)

    mix = music * music_gain[:, None] + foley * 1.15 + voice[:, None] * 1.0
    # Soft-knee bus compression: gentle glue, no pumping.
    peak_env = np.maximum(np.abs(mix[:, 0]), np.abs(mix[:, 1]))
    smooth_env = np.convolve(peak_env, np.ones(1200, dtype=np.float32) / 1200,
                             mode="same")
    gain = np.where(smooth_env > 0.30, 0.30 / np.maximum(smooth_env, 1e-6), 1.0)
    mix *= (0.55 + 0.45 * gain)[:, None]
    mix = np.tanh(mix * 1.6) / 1.6
    # Fade the very top and tail so the reel opens and closes cleanly.
    ramp = int(0.25 * RATE)
    mix[:ramp] *= np.linspace(0, 1, ramp, dtype=np.float32)[:, None]
    mix[-int(1.1 * RATE):] *= np.linspace(1, 0, int(1.1 * RATE),
                                          dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(mix)))
    if peak > 0:
        mix *= 0.89 / peak
    pcm = (np.clip(mix, -0.999, 0.999) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm.tobytes())
    print(f"Mixed {LENGTH:.0f}s stereo audio: {path}, peak {np.max(np.abs(mix)):.3f}, "
          f"RMS {np.sqrt(np.mean(mix ** 2)):.3f}")
    return path


if __name__ == "__main__":
    create_mix()
