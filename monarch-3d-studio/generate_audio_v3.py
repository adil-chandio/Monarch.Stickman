#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONARCHVOICE // MOTION LAB — 30 s score
Reuses the v2 synth kit (pads, taiko, risers, impacts, reverb) with a new
arrangement synced to the 6 explainer chapters.
"""

import math
import wave
import numpy as np

import generate_audio_v2 as A

SR = A.SR
DUR = 30.0
N = int(SR * DUR)

A.N = N
A.SR = SR
A.L = np.zeros(N, np.float64)
A.R = np.zeros(N, np.float64)
A.SEND = np.zeros(N, np.float64)

L, R = A.L, A.R
place = A.place
pad, sub_drone = A.pad, A.sub_drone
kick, snare, hat, tom, boom = A.kick, A.snare, A.hat, A.tom, A.boom
impact_hit, whoosh, riser = A.impact_hit, A.whoosh, A.riser
filt, decay, noise, midi = A.filt, A.decay, A.noise, A.midi

CH = {
    "Am": [45, 57, 60, 64, 69],
    "F":  [41, 53, 57, 60, 65],
    "C":  [48, 55, 60, 64, 67],
    "G":  [43, 55, 59, 62, 67],
    "Em": [40, 52, 55, 59, 64],
    "Dm": [50, 57, 62, 65, 69],
}


def build():
    # ---------------- INTRO 0 - 3.2 ----------------
    place((L, R), pad(CH["Am"], 3.6, attack=1.1, release=0.8, bright=0.35),
          0.05, gain=0.24, send=0.6)
    place((L, R), sub_drone([33], 3.4), 0.0, gain=0.20)
    place((L, R), riser(1.4, 90, 460), 0.15, gain=0.10, send=0.5)
    place((L, R), boom(2.0, 42), 0.30, gain=0.26, send=0.3)
    for i, tt in enumerate([1.1, 1.55, 2.0, 2.45, 2.85]):
        place((L, R), hat(0.07), tt, gain=0.09,
              pan=0.3 if i % 2 else -0.3)

    # ---------------- LAW 1 · GRAVITY 3.2 - 10.2 ----------------
    place((L, R), pad(CH["F"], 3.6, attack=0.4, release=0.6, bright=0.55),
          3.15, gain=0.26, send=0.5)
    place((L, R), sub_drone([29, 41], 3.4), 3.2, gain=0.20)
    # gentle pulse while the hero walks in
    for i in range(5):
        place((L, R), kick(0.4, 120, 48, 0.5), 3.35 + i * 0.55, gain=0.22)
    place((L, R), whoosh(0.55, up=True), 3.85, gain=0.26, send=0.55)
    place((L, R), tom(78, 0.35), 3.85, gain=0.20, send=0.4)
    place((L, R), whoosh(0.45, up=False), 5.30, gain=0.22, send=0.5)
    place((L, R), impact_hit(0.9, 0.8), 5.35, gain=0.30, send=0.4)
    # second, bigger jump
    place((L, R), riser(0.9, 180, 900), 6.35, gain=0.20, send=0.55)
    place((L, R), whoosh(0.7, up=True), 6.55, gain=0.32, send=0.6)
    place((L, R), tom(66, 0.5), 6.55, gain=0.24, send=0.5)
    place((L, R), whoosh(0.55, up=False), 8.25, gain=0.26, send=0.5)
    place((L, R), impact_hit(1.1, 0.9), 8.30, gain=0.34, send=0.45)
    place((L, R), boom(1.6, 40), 8.30, gain=0.24, send=0.3)
    place((L, R), pad(CH["C"], 2.0, attack=0.3, release=0.6, bright=0.5),
          8.4, gain=0.20, send=0.55)

    # ---------------- LAW 2 · MOMENTUM 10.2 - 15.8 ----------------
    place((L, R), pad(CH["Dm"], 3.0, attack=0.25, release=0.6, bright=0.6),
          10.2, gain=0.26, send=0.45)
    place((L, R), sub_drone([38], 2.6), 10.2, gain=0.24)
    place((L, R), pad(CH["G"], 2.8, attack=0.25, release=0.7, bright=0.65),
          13.0, gain=0.26, send=0.45)
    # groove under the two pushes
    bpm = 118.0
    beat = 60.0 / bpm
    tt = 10.2
    k = 0
    while tt < 15.6:
        if k % 2 == 0:
            place((L, R), kick(0.45, 130, 48, 0.8), tt, gain=0.34, send=0.12)
        if k % 4 == 3:
            place((L, R), snare(0.24, 0.7), tt, gain=0.20, send=0.25)
        for j in range(2):
            place((L, R), hat(0.05, open_=(j == 1)),
                  tt + j * beat / 2, gain=0.06,
                  pan=0.3 if j else -0.3)
        tt += beat
        k += 1
    # heavy crate grind
    n = int(1.6 * SR)
    grind = filt(noise(n), lo=60, hi=420) * decay(n, 0.8) * 0.5
    place((L, R), grind, 11.1, gain=0.28, send=0.3)
    place((L, R), tom(58, 0.6), 11.05, gain=0.26, send=0.35)
    # light crate zip
    place((L, R), whoosh(0.4, up=True), 13.35, gain=0.26, send=0.5)
    place((L, R), snare(0.16, 0.9), 13.40, gain=0.22, send=0.3)
    place((L, R), whoosh(0.35, up=True), 13.9, gain=0.14, send=0.4)

    # ---------------- LAW 3 · ACTION = REACTION 15.8 - 21.4 --------------
    place((L, R), pad(CH["Em"], 2.7, attack=0.2, release=0.6, bright=0.7),
          15.75, gain=0.26, send=0.45)
    place((L, R), sub_drone([40], 2.4), 15.75, gain=0.24)
    place((L, R), pad(CH["Am"], 2.7, attack=0.2, release=0.6, bright=0.75),
          18.4, gain=0.26, send=0.45)
    place((L, R), sub_drone([33, 45], 2.4), 18.4, gain=0.24)
    # first clash (t = 16.85) and second (19.25)
    for (tt, pw) in [(16.85, 1.0), (19.25, 1.15)]:
        place((L, R), whoosh(0.42, up=True), tt - 0.30, gain=0.30, send=0.5)
        place((L, R), impact_hit(1.0, 1.0), tt, gain=0.52 * pw, send=0.4)
        place((L, R), boom(1.4, 40), tt, gain=0.34 * pw, send=0.3)
        place((L, R), tom(72, 0.5), tt + 0.02, gain=0.22, send=0.35)
    bpm = 126.0
    beat = 60.0 / bpm
    tt = 16.1
    k = 0
    while tt < 21.0:
        place((L, R), kick(0.42, 128, 46, 0.75), tt, gain=0.26, send=0.1)
        if k % 4 == 2:
            place((L, R), snare(0.22, 0.8), tt, gain=0.18, send=0.25)
        tt += beat
        k += 1

    # ---------------- LAW 4 · ENERGY 21.4 - 27.2 ----------------
    place((L, R), pad(CH["Am"], 3.2, attack=0.25, release=0.5, bright=0.55),
          21.35, gain=0.26, send=0.5)
    place((L, R), sub_drone([33], 2.2), 21.35, gain=0.26)
    # the weight falls: descending wah + slam
    n = int(1.05 * SR)
    fall = A.sweep_sine(420, 70, 1.05, 0.8) * decay(n, 0.5) * 0.6
    place((L, R), fall, 22.30, gain=0.30, send=0.4)
    place((L, R), impact_hit(1.0, 0.9), 23.35, gain=0.40, send=0.45)
    place((L, R), tom(70, 0.55), 23.35, gain=0.24, send=0.4)
    # lever spring -> launch
    place((L, R), riser(0.75, 220, 1600), 23.45, gain=0.24, send=0.55)
    place((L, R), whoosh(0.6, up=True), 23.85, gain=0.32, send=0.6)
    place((L, R), pad(CH["F"], 2.4, attack=0.3, release=0.8, bright=0.8),
          23.9, gain=0.26, send=0.55)
    place((L, R), whoosh(0.45, up=False), 25.55, gain=0.22, send=0.5)
    place((L, R), impact_hit(1.0, 0.85), 25.62, gain=0.34, send=0.45)
    place((L, R), pad(CH["G"], 2.0, attack=0.35, release=0.7, bright=0.6),
          25.7, gain=0.22, send=0.55)

    # ---------------- OUTRO 27.2 - 30.0 ----------------
    place((L, R), whoosh(0.6, up=False), 27.05, gain=0.22, send=0.6)
    place((L, R), boom(2.0, 42), 27.25, gain=0.42, send=0.5)
    place((L, R), pad([57, 69, 72, 76], 2.6, attack=0.10, release=1.1,
                      bright=0.6), 27.28, gain=0.32, send=0.75)
    place((L, R), sub_drone([33], 2.4), 27.28, gain=0.22)
    n = int(2.0 * SR)
    tt2 = np.arange(n) / SR
    shimmer = (np.sin(2 * np.pi * midi(81) * tt2) * decay(n, 1.0) * 0.5 +
               np.sin(2 * np.pi * midi(88) * tt2) * decay(n, 1.4) * 0.3)
    place((L, R), shimmer, 27.35, gain=0.12, send=0.9)
    place((L, R), hat(0.6, open_=True), 27.4, gain=0.09, send=0.6)


def main():
    build()
    print("  mixing...", flush=True)
    n = N
    # sidechain pad bus under the groove sections
    kicks = []
    for (t0, t1, bpm) in [(10.2, 15.6, 118.0), (16.1, 21.0, 126.0)]:
        beat = 60.0 / bpm
        tt = t0
        while tt < t1:
            kicks.append(tt)
            tt += beat
    duck = A.sidechain(n, kicks)
    for (a, b) in [(10.1, 15.7), (16.0, 21.1)]:
        seg = slice(int(a * SR), int(b * SR))
        L[seg] *= duck[seg]
        R[seg] *= duck[seg]

    revL = A.reverb(A.SEND, 0.6)
    revR = A.reverb(A.SEND, 0.6)
    outL = L + revL * 0.35
    outR = R + revR * 0.35
    outL = filt(outL, lo=28)
    outR = filt(outR, lo=28)
    st = np.stack([outL, outR], 1)
    st = np.tanh(st * 0.75) / np.tanh(0.75)
    peak = np.percentile(np.abs(st), 99.99)
    st = st / peak * 0.85
    fi = int(0.15 * SR)
    fo = int(0.5 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]

    pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    with wave.open("soundtrack_v3.wav", "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"  wrote soundtrack_v3.wav {pcm.shape} dur={len(st)/SR:.2f}s "
          f"peak={np.abs(st).max():.3f}", flush=True)


if __name__ == "__main__":
    main()
