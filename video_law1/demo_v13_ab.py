#!/usr/bin/env python3
"""
demo_v13_ab.py — the proof, not the pitch.

Renders the *same* four-chord idea (Am–F–C–G, 3 s each, 12 s total) two ways and
writes them side by side so the difference can be judged by ear, then measured:

  A  current stack   music_v12: additive/FM `piano()`, detuned-saw `strings()`,
                     hand-rolled filters, peak normalisation
  B  v13 stack       GeneralUser GS grand piano + string ensemble (real
                     recordings) via TinySoundFont, humanised velocity/timing,
                     Spotify `pedalboard` master chain, BS.1770 loudness target

Run: python demo_v13_ab.py   ->  v3out/ab_A_current.wav, v3out/ab_B_v13.wav
"""
from __future__ import annotations

import os

import numpy as np
import soundfile as sf

import audio_v3 as A
import premium_audio as P
from audio_v3 import CHORDS, NOTE, SR, T

CH = ["Am", "F", "C", "G"]
BAR = 3.0
TOTAL = BAR * len(CH)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v3out")
rng = np.random.default_rng(2026)


def midi(freq: float) -> int:
    return int(round(69 + 12 * np.log2(freq / 440.0)))


# ------------------------------------------------------------------ A: current
def build_a() -> np.ndarray:
    import music_v12
    x = music_v12.build(TOTAL + 0.5)[: T(TOTAL)]
    return P.master(x, target_lufs=-14.0)


# --------------------------------------------------------------------- B: v13
def build_b() -> np.ndarray:
    ins = P.Instruments(gain_db=0.0)
    ins.program(0, "piano")
    ins.program(1, "strings_slow")

    for i, ch in enumerate(CH):
        tones = [NOTE[t] for t in CHORDS[ch][:3]]
        t0 = i * BAR
        # piano: rolled chord, real velocity spread, note lengths vary per note
        for j, f in enumerate(tones):
            ins.note(0, midi(f) - 12,
                     vel=int(92 + rng.integers(-6, 8)),
                     at=t0 + 0.02 + j * 0.04 + rng.uniform(-.008, .008),
                     dur=BAR * float(rng.uniform(.80, .98)))
        # strings: pad an octave above, one chord per bar, no rhythm
        ins.chord(1, [midi(f) + 12 for f in tones], vel=84,
                  at=t0, dur=BAR * 1.06, spread=0.02, humanise=0.010, rng=rng)

    body = ins.render(TOTAL)

    # weight: the SoundFont has no sub, so an 808 goes underneath — but levels
    # are set by RMS (-18 body / -24 sub), because peak-matching made the old
    # beds 90 % sub-bass and 0 % midrange.
    low = np.zeros_like(body)
    for i, ch in enumerate(CH):
        sub = A.sub808(NOTE[[*CHORDS[ch]][0]] / 2, BAR * .95, drive=1.2)
        A.place(low, sub, i * BAR, gain=1.0)

    # Levelled by PEAK, not RMS. Two traps, both measured here:
    #  * a sparse piano at "-18 dBFS RMS" peaks at +8 dBFS -> the limiter takes
    #    20 dB off it and only the sustained sub survives (96 % of the spectrum);
    #  * a 40 Hz sine has a crest factor of ~1, so "-24 dBFS RMS" is a roar.
    body = P.fit_peak(body, -6.0)
    low = P.fit_peak(low, -30.0)      # sub carries weight, never the spectrum
    mix = body + low
    return P.master(mix, target_lufs=-14.0, ceiling_db=-1.0)


def main():
    os.makedirs(OUT, exist_ok=True)
    a, b = build_a(), build_b()
    for name, x in (("ab_A_current", a), ("ab_B_v13", b)):
        p = os.path.join(OUT, name + ".wav")
        sf.write(p, x, SR, subtype="FLOAT")
        print(f"{name:14s} {P.lufs(x):6.1f} LUFS  peak {20*np.log10(np.abs(x).max()):5.2f} dBFS")
        bal = P.spectral_balance(x)
        print("   " + "  ".join(f"{k}:{v:4.1f}%" for k, v in bal.items()))

    # 0.4 s of silence between them so the ear can reset
    gap = np.zeros((int(.4 * SR), 2), dtype=np.float32)
    sf.write(os.path.join(OUT, "ab_reel.wav"), np.vstack([a, gap, b]),
             SR, subtype="FLOAT")
    print("wrote v3out/ab_A_current.wav, ab_B_v13.wav, ab_reel.wav")


if __name__ == "__main__":
    main()
