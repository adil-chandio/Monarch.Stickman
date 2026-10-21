#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONARCHVOICE // NEO PROTOCOL  -  procedural soundtrack (20.0 s, 44.1 kHz stereo)
Pure numpy DSP: pads, sub drones, taiko/EDM drums, risers, whooshes, impacts,
FFT band-pass filtering, convolution reverb, sidechain ducking, soft limiter.
"""

import math
import wave
import numpy as np

SR = 44100
DUR = 20.0
N = int(SR * DUR)
rng = np.random.default_rng(2024)

L = np.zeros(N, np.float64)
R = np.zeros(N, np.float64)
SEND = np.zeros(N, np.float64)          # reverb send bus


# ---------------------------------------------------------------- helpers
def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12.0)


def at(sec):
    return int(round(sec * SR))


def place(buf, sig, start, gain=1.0, pan=0.0, send=0.0):
    """mix mono sig into stereo pair at time offset `start` (sec)."""
    i0 = at(start)
    if i0 >= N:
        return
    n = min(len(sig), N - i0)
    s = sig[:n] * gain
    gl = math.sqrt(0.5 * (1.0 - pan))
    gr = math.sqrt(0.5 * (1.0 + pan))
    buf[0][i0:i0 + n] += s * gl
    buf[1][i0:i0 + n] += s * gr
    if send > 0:
        SEND[i0:i0 + n] += s * send


def filt(x, lo=None, hi=None, order=2):
    """zero-phase FFT band filter (2-pole-ish Butterworth magnitude)."""
    n = len(x)
    if n == 0:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    f = np.maximum(f, 1e-6)
    m = np.ones_like(f)
    if lo:
        m *= 1.0 / (1.0 + (lo / f) ** (2 * order))
    if hi:
        m *= 1.0 / (1.0 + (f / hi) ** (2 * order))
    return np.fft.irfft(X * m, n)


def decay(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def noise(n):
    return rng.standard_normal(n)


def saw(freq, n, bright=1.0):
    """band-limited-ish saw via additive harmonics"""
    tt = np.arange(n) / SR
    out = np.zeros(n)
    kmax = max(1, int(min(18, (SR * 0.45) / max(20.0, freq))))
    for k in range(1, kmax + 1):
        out += (1.0 / k ** (1.25 - 0.25 * bright)) * np.sin(
            2 * np.pi * freq * k * tt + rng.uniform(0, 6.28))
    return out / (np.abs(out).max() + 1e-9)


def sweep_sine(f0, f1, dur, curve=2.0):
    n = int(dur * SR)
    tt = np.linspace(0, 1, n)
    f = f0 + (f1 - f0) * (tt ** curve)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph)


# ---------------------------------------------------------------- drums
def kick(dur=0.55, f0=130, f1=44, punch=1.0):
    n = int(dur * SR)
    body = sweep_sine(f0, f1, dur, 0.55) * decay(n, dur * 0.32)
    click = noise(int(0.006 * SR)) * decay(int(0.006 * SR), 0.002)
    click = filt(click, lo=1200)
    out = body
    out[:len(click)] += click * 0.55 * punch
    out = np.tanh(out * 1.6) * 0.95
    return out / (np.abs(out).max() + 1e-9) * punch


def snare(dur=0.35, bright=1.0):
    n = int(dur * SR)
    nz = filt(noise(n), lo=1400, hi=9000) * decay(n, dur * 0.30)
    tone = np.sin(2 * np.pi * 190 * np.arange(n) / SR) * decay(n, 0.045) * 0.5
    out = nz * 0.9 + tone
    out = np.tanh(out * 1.4)
    return out / (np.abs(out).max() + 1e-9) * bright


def hat(dur=0.09, open_=False):
    n = int(dur * SR)
    x = filt(noise(n), lo=6500, hi=15000) * decay(n, dur * (0.55 if open_ else 0.22))
    return x / (np.abs(x).max() + 1e-9)


def tom(freq=110, dur=0.5):
    n = int(dur * SR)
    x = sweep_sine(freq * 1.8, freq, dur, 0.4) * decay(n, dur * 0.35)
    x += filt(noise(n), lo=200, hi=2500) * decay(n, 0.03) * 0.3
    return x / (np.abs(x).max() + 1e-9)


def boom(dur=2.2, f=42):
    n = int(dur * SR)
    sw = sweep_sine(f * 3.2, f, dur, 0.5)
    x = sw * decay(n, dur * 0.28)
    x += filt(noise(n), lo=24, hi=180) * decay(n, 0.30) * 0.7
    x = np.tanh(x * 1.8)
    return x / (np.abs(x).max() + 1e-9)


def impact_hit(dur=0.9, bright=1.0):
    n = int(dur * SR)
    crack = filt(noise(n), lo=900, hi=11000) * decay(n, 0.028)
    body = sweep_sine(220, 60, dur, 0.6) * decay(n, 0.10)
    sub = sweep_sine(90, 38, dur, 0.7) * decay(n, dur * 0.30)
    x = crack * 1.0 + body * 0.75 + sub * 0.9
    x = np.tanh(x * 1.7)
    return x / (np.abs(x).max() + 1e-9) * bright


def whoosh(dur=0.5, up=True):
    n = int(dur * SR)
    nz = noise(n)
    # sweeping band via time-varying mix of three static bands
    b1 = filt(nz, lo=300, hi=1200)
    b2 = filt(nz, lo=900, hi=3500)
    b3 = filt(nz, lo=2500, hi=9000)
    tt = np.linspace(0, 1, n)
    w = tt if up else 1 - tt
    env = np.sin(np.pi * np.clip(tt * 1.05, 0, 1)) ** 1.5
    x = (b1 * (1 - w) ** 2 + b2 * 2 * w * (1 - w) + b3 * w ** 2) * env
    return x / (np.abs(x).max() + 1e-9)


def riser(dur=1.6, f0=120, f1=900):
    n = int(dur * SR)
    tt = np.linspace(0, 1, n)
    tone = sweep_sine(f0, f1, dur, 1.4) * (tt ** 2.0) * 0.35
    air = filt(noise(n), lo=600, hi=11000) * (tt ** 2.4) * 0.8
    x = tone + air
    return x / (np.abs(x).max() + 1e-9)


# ---------------------------------------------------------------- pad / chords
def pad(notes, dur, attack=0.8, release=1.2, bright=0.5, detune=0.16):
    n = int(dur * SR)
    out = np.zeros(n)
    tt = np.arange(n) / SR
    for m in notes:
        f = midi(m)
        for d in (-detune, 0.0, detune):
            ff = f * (1 + d / 100.0)
            vib = 1 + 0.0022 * np.sin(2 * np.pi * (0.13 + rng.uniform(0, 0.2)) * tt
                                      + rng.uniform(0, 6.28))
            ph = 2 * np.pi * np.cumsum(ff * vib) / SR
            sig = np.sin(ph) * 0.6
            # a bit of harmonic sparkle
            sig += np.sin(ph * 2) * 0.28 * bright
            sig += np.sin(ph * 3) * 0.14 * bright
            sig += np.sin(ph * 5) * 0.06 * bright
            out += sig * (1.0 / (1 + abs(d) * 3))
    out /= (len(notes) * 3.0)
    a = max(1, int(attack * SR))
    r = max(1, int(release * SR))
    env = np.ones(n)
    env[:a] = np.linspace(0, 1, a) ** 0.7
    env[-r:] *= np.linspace(1, 0, r) ** 1.4
    return out * env


def sub_drone(notes, dur, gain=1.0):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    out = np.zeros(n)
    for m in notes:
        out += np.sin(2 * np.pi * midi(m) * tt)
    out /= len(notes)
    env = np.ones(n)
    a = int(0.5 * SR)
    env[:a] = np.linspace(0, 1, a)
    env[-int(0.8 * SR):] *= np.linspace(1, 0, int(0.8 * SR))
    return out * env * gain


# ---------------------------------------------------------------- arrangement
def build():
    # ---- chord map (cinematic dark minor) ----
    # A minor  |  F major | C major | G#/E tension | A minor resolve
    CH = {
        "Am": [45, 57, 60, 64, 69],      # A2 A3 C4 E4 A4
        "F":  [41, 53, 57, 60, 65],
        "C":  [48, 55, 60, 64, 67],
        "G#": [44, 56, 59, 63, 68],
        "Em": [40, 52, 55, 59, 64],
    }

    # ---------- INTRO 0.0 - 3.4 ----------
    s = pad(CH["Am"], 3.6, attack=1.2, release=0.9, bright=0.35)
    place((L, R), s, 0.05, gain=0.20, send=0.55)
    place((L, R), sub_drone([33], 3.5), 0.0, gain=0.20)
    # logo swell
    place((L, R), riser(1.5, 80, 420), 0.15, gain=0.10, send=0.5)
    place((L, R), boom(2.4, 40), 0.25, gain=0.26, send=0.25)
    for i, tt in enumerate([0.9, 1.35, 1.8, 2.25]):
        place((L, R), hat(0.07), tt, gain=0.10, pan=0.25 if i % 2 else -0.25)

    # ---------- BUILD 3.4 - 6.0 (hero walk / charge) ----------
    place((L, R), pad(CH["F"], 2.7, attack=0.5, release=0.5, bright=0.5),
          3.35, gain=0.26, send=0.45)
    place((L, R), sub_drone([29, 41], 2.7), 3.35, gain=0.18)
    # heartbeat-ish pulse
    for i in range(6):
        tt = 3.5 + i * 0.42
        place((L, R), kick(0.42, 120, 46, 0.55), tt, gain=0.30)
    # footsteps
    for i in range(10):
        tt = 2.55 + i * 0.30
        place((L, R), tom(70, 0.18), tt, gain=0.10, pan=-0.4)
    # charge whine
    n = int(2.0 * SR)
    tt = np.arange(n) / SR
    whine = np.sin(2 * np.pi * np.cumsum(180 + 520 * (tt / 2.0) ** 2) / SR)
    whine *= (tt / 2.0) ** 2 * decay(n, 3.0)
    place((L, R), whine, 4.0, gain=0.12, send=0.6)
    place((L, R), riser(0.8, 300, 1400), 5.15, gain=0.16, send=0.5)
    place((L, R), boom(1.6, 48), 5.55, gain=0.35, send=0.4)

    # ---------- ARRIVAL 6.0 - 9.5 ----------
    place((L, R), pad(CH["C"], 3.6, attack=0.35, release=1.0, bright=0.6),
          6.0, gain=0.36, send=0.5)
    place((L, R), pad([36, 55, 60, 63], 1.8, attack=0.2, release=0.8,
                      bright=0.75), 6.15, gain=0.22, send=0.4)
    place((L, R), sub_drone([36], 3.5), 6.0, gain=0.30)
    place((L, R), whoosh(0.9, up=False), 5.55, gain=0.28, send=0.6)
    place((L, R), impact_hit(1.4, 1.0), 7.42, gain=0.75, send=0.55)
    place((L, R), boom(2.2, 38), 7.42, gain=0.55, send=0.3)
    place((L, R), whoosh(0.5, up=False), 7.30, gain=0.22, send=0.5)
    # menacing taiko pulse
    for i in range(7):
        tt = 7.9 + i * 0.25
        place((L, R), tom(88, 0.35), tt, gain=0.20, pan=0.35 if i % 2 else -0.35,
              send=0.35)
    place((L, R), riser(1.2, 200, 1800), 8.35, gain=0.20, send=0.6)

    # ---------- CLASH 9.5 - 13.5 (fight) ----------
    place((L, R), pad(CH["Am"], 4.2, attack=0.15, release=0.9, bright=0.8),
          9.5, gain=0.34, send=0.4)
    place((L, R), sub_drone([33, 45], 4.2), 9.5, gain=0.28)
    # driving 16th hats + kick pattern
    bpm = 132.0
    beat = 60.0 / bpm
    tt = 9.5
    k = 0
    while tt < 13.5:
        place((L, R), kick(0.5, 135, 46, 0.9), tt, gain=0.42, send=0.15)
        if k % 2 == 1:
            place((L, R), snare(0.3, 0.85), tt, gain=0.30, send=0.30)
        for j in range(4):
            place((L, R), hat(0.06, open_=(j == 3)), tt + j * beat / 4,
                  gain=0.085 if j % 2 else 0.055,
                  pan=0.35 if j % 2 else -0.35)
        tt += beat
        k += 1
    # fight impacts synced to the visuals
    for (t0, pw) in [(9.80, 1.0), (10.42, 0.9), (11.50, 0.8), (12.10, 0.85),
                     (12.90, 1.0)]:
        place((L, R), impact_hit(0.7, 1.0), t0, gain=0.45 * pw, send=0.35)
        place((L, R), whoosh(0.35, up=True), t0 - 0.16, gain=0.18, send=0.4)
    place((L, R), whoosh(0.45, up=True), 9.55, gain=0.24, send=0.4)
    place((L, R), whoosh(0.45, up=True), 10.2, gain=0.20, send=0.4)

    # ---------- PRESSURE 13.5 - 15.4 ----------
    place((L, R), pad(CH["G#"], 2.2, attack=0.5, release=0.8, bright=0.4),
          13.4, gain=0.38, send=0.55)
    place((L, R), sub_drone([32], 2.2), 13.4, gain=0.30)
    place((L, R), whoosh(0.4, up=False), 13.85, gain=0.22, send=0.5)
    place((L, R), impact_hit(1.1, 1.1), 14.08, gain=0.55, send=0.5)
    # muffled "underwater" fall
    place((L, R), boom(2.0, 34), 15.02, gain=0.40, send=0.25)
    place((L, R), tom(60, 0.7), 15.02, gain=0.28, send=0.5)

    # ---------- FINISH build 15.4 - 16.45 ----------
    place((L, R), pad(CH["Em"], 1.4, attack=0.3, release=0.2, bright=0.7),
          15.3, gain=0.30, send=0.5)
    place((L, R), riser(1.15, 140, 2400), 15.30, gain=0.30, send=0.55)
    # accelerating snare roll
    tt = 15.55
    gap = 0.16
    while tt < 16.42:
        place((L, R), snare(0.16, 0.6), tt, gain=0.10 + 0.16 * ((tt - 15.55) / 0.87),
              send=0.3)
        tt += gap
        gap = max(0.055, gap * 0.90)
    place((L, R), whoosh(0.5, up=True), 16.05, gain=0.30, send=0.5)

    # ---------- THE FINISH HIT 16.45 ----------
    place((L, R), impact_hit(2.4, 1.0), 16.45, gain=1.00, send=0.75)
    place((L, R), boom(3.0, 33), 16.45, gain=0.85, send=0.4)
    place((L, R), kick(0.9, 170, 36, 1.0), 16.45, gain=0.55)
    place((L, R), pad(CH["Am"], 3.3, attack=0.05, release=1.6, bright=1.0),
          16.47, gain=0.42, send=0.7)
    place((L, R), pad(CH["F"], 2.6, attack=0.4, release=1.4, bright=0.6),
          17.5, gain=0.22, send=0.7)
    place((L, R), sub_drone([33], 3.2), 16.47, gain=0.26)
    # slow tom heartbeat after the hit
    for i, tt in enumerate([17.1, 17.7, 18.3]):
        place((L, R), tom(52, 0.9), tt, gain=0.22 - i * 0.04, send=0.5)

    # ---------- VICTORY 17.5 - 19.0 ----------
    n = int(1.6 * SR)
    tt2 = np.arange(n) / SR
    shimmer = np.sin(2 * np.pi * midi(81) * tt2) * decay(n, 0.9) * 0.5
    shimmer += np.sin(2 * np.pi * midi(88) * tt2) * decay(n, 1.2) * 0.3
    place((L, R), shimmer, 17.5, gain=0.12, send=0.9)

    # ---------- END CARD 19.0 - 20.0 ----------
    place((L, R), whoosh(0.55, up=False), 18.85, gain=0.20, send=0.6)
    place((L, R), boom(1.5, 44), 19.02, gain=0.50, send=0.5)
    place((L, R), pad([57, 69, 72, 76], 1.3, attack=0.08, release=0.6,
                      bright=0.6), 19.03, gain=0.30, send=0.8)
    place((L, R), hat(0.5, open_=True), 19.06, gain=0.10, send=0.6)


# ---------------------------------------------------------------- mixdown
def reverb(x, wet=0.55):
    ir_len = int(1.5 * SR)
    ir = noise(ir_len) * np.exp(-np.arange(ir_len) / (0.42 * SR))
    ir = filt(ir, hi=5200)
    ir[:int(0.008 * SR)] *= np.linspace(0, 1, int(0.008 * SR))
    ir /= np.abs(ir).max()
    n = len(x) + len(ir)
    nfft = 1 << (n - 1).bit_length()
    wet_sig = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:len(x)]
    return x + wet_sig * wet


def sidechain(n, kicks):
    duck = np.ones(n)
    env_n = int(0.16 * SR)
    shape = 1 - 0.55 * np.exp(-np.arange(env_n) / (0.055 * SR))
    for kt in kicks:
        i = at(kt)
        m = min(env_n, n - i)
        if m > 0:
            duck[i:i + m] = np.minimum(duck[i:i + m], shape[:m])
    return duck


def main():
    global L, R, SEND
    build()
    n = N
    print("  mixing...", flush=True)

    # sidechain the pad bus against the four-on-the-floor section
    kicks = [9.5 + i * (60 / 132.0) for i in range(int(4.0 / (60 / 132.0)) + 1)]
    duck = sidechain(n, kicks)
    seg = slice(at(9.4), at(13.6))
    L[seg] *= duck[seg]
    R[seg] *= duck[seg]

    revL = reverb(SEND, 0.6)
    revR = reverb(SEND, 0.6)
    L = L + revL * 0.35
    R = R + revR * 0.35

    # gentle bus glue: highpass rumble cleanup + soft limit
    L = filt(L, lo=28)
    R = filt(R, lo=28)
    st = np.stack([L, R], 1)
    st = np.tanh(st * 0.75) / np.tanh(0.75)
    peak = np.percentile(np.abs(st), 99.99)
    st = st / peak * 0.85
    # fade in/out
    fi = int(0.15 * SR)
    fo = int(0.35 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]

    pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    out = "soundtrack_v2.wav"
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"  wrote {out}  {pcm.shape}  peak={np.abs(st).max():.3f}", flush=True)


if __name__ == "__main__":
    main()
