#!/usr/bin/env python3
"""
music_v13.py — the v12 arrangement, played on real instruments.

v12 fixed the *arrangement* (3 layers, no melody, 8 dB under the voice) but the
sources were still synthetic: `audio_v3.piano()` is additive tones and
`strings()` is detuned saws. Measured, a v12 bed puts 92 % of its energy below
120 Hz — the band a phone speaker cannot reproduce. That is the "rumble" that
reads as echo even with the reverb off.

This score keeps the v12 rules and swaps the source for GeneralUser GS samples
rendered by TinySoundFont (605× realtime):

    pad    strings_slow, one chord per scene, low, no rhythm
    sub    808 root underneath, only where the edit gets heavy
    mark   ONE piano note at each scene change (10 in the whole video)
    sheen  celesta octave on the three biggest beats only

Levels are set by PEAK per layer and by LUFS at the master — never by feel.
"""
from __future__ import annotations

import os

import numpy as np

import audio_v3 as A
import premium_audio as P
from audio_v3 import CHORDS, NOTE, SR
from timeline_v4 import BEATS, TOTAL

SCENE_CHORD = ["Am", "F", "C", "G", "Dm", "Am", "F", "C", "G", "Am"]
WEIGHT = {"hook": .55, "title": .45, "story": .30, "danger": .70,
          "shock": .80, "teach": .35, "bright": .40, "quote": .30, "end": .75}

# the three beats that carry a word big enough to deserve a sparkle
SHEEN_AT = [0.37, 25.77, 55.81]

# per-layer peaks (dBFS) before the master stage. Each layer is rendered
# separately: a dense pad and a sparse piano cannot be levelled against each
# other by peak inside one buffer.
PAD_DB, SUB_DB, MARK_DB, SHEEN_DB = -17.0, -46.0, -15.0, -20.0


def midi(freq: float) -> int:
    return int(round(69 + 12 * np.log2(freq / 440.0)))


def build(total: float, rng_seed: int = 13) -> np.ndarray:
    rng = np.random.default_rng(rng_seed)
    n = A.T(total)

    def player(program: str, gain_db: float = -6.0):
        ins = P.Instruments(gain_db=gain_db)
        ins.program(0, program)
        return ins

    pad_i, mark_i, sheen_i = player("strings"), player("piano"), player("celesta")
    sub = np.zeros((n, 2), dtype=np.float32)

    for i, b in enumerate(BEATS):
        t0, dur = float(b["start"]), float(b["dur"])
        if t0 >= total:
            break
        ch = SCENE_CHORD[i % len(SCENE_CHORD)]
        tones = CHORDS[ch]
        w = WEIGHT.get(b.get("kind", "story"), .35)

        # pad: one chord for the scene, low, overlapping the cut by 0.9 s
        # open voicing: root an octave down, third at pitch, fifth an octave up.
        # A pad voiced only in the low octave is why an earlier pass measured
        # 37 % of its energy at 60-120 Hz and 6 % at 500-1500 Hz.
        for j, t in enumerate(tones[:3]):
            pad_i.note(0, midi(NOTE[t]) + (-12, 0, 12)[j],
                       vel=int(80 + 8 * w + rng.integers(-4, 5)),
                       at=t0 + rng.uniform(-.01, .01), dur=dur + 0.9)

        # one note at the scene change — a marker, never a tune
        if i > 0:
            mark_i.note(0, midi(NOTE[tones[0]]) + 12,
                        vel=int(72 + rng.integers(-5, 6)),
                        at=t0 - .02 + rng.uniform(-.006, .006),
                        dur=float(rng.uniform(1.4, 1.8)))

        # sheen: the chord's fifth, an octave up, very quiet — gives the bed a
        # top end the GM strings do not have (they stop dead at ~4 kHz)
        if i % 2 == 0 or w >= .6:
            sheen_i.note(0, midi(NOTE[tones[2]]) + 24,
                         vel=int(56 + rng.integers(-4, 5)),
                         at=t0 + .04, dur=float(rng.uniform(1.1, 1.6)))

        if w >= .45:
            s = A.sub808(NOTE[tones[0]] / 2, min(dur, 3.2), drive=1.2)
            A.place(sub, s, t0, gain=1.0)

    # the three biggest beats get a second sheen note (sparkle, still no melody)
    for t in SHEEN_AT:
        sheen_i.note(0, midi(NOTE["A5"]), vel=58, at=t + .02, dur=1.2)

    pad = P.fit_peak(pad_i.render(total), PAD_DB)
    mark = P.fit_peak(mark_i.render(total), MARK_DB)
    sheen = P.fit_peak(sheen_i.render(total), SHEEN_DB)
    mix = (pad + mark + sheen + P.fit_peak(sub, SUB_DB)).astype(np.float32)

    # dark short room, glue only — then re-measure (a Reverb at 6 % wet can add
    # +5 dB RMS, so the knob means nothing)
    from pedalboard import Pedalboard, Reverb
    room = Pedalboard([Reverb(room_size=0.28, damping=0.8, wet_level=0.05,
                              dry_level=0.95, width=0.50)])
    mix = np.ascontiguousarray(room(np.array(mix.T, dtype=np.float32, order="C"), SR).T)

    fo, fi = A.T(1.2), A.T(.6)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None].astype(np.float32)
    mix[:fi] *= np.linspace(0, 1, fi)[:, None].astype(np.float32)
    return P.master(mix.astype(np.float32), target_lufs=-14.0)


def build_bed(total: float):
    m = build(total)
    return m, A.smooth(np.abs(m).max(axis=1), 220)


if __name__ == "__main__":
    import soundfile as sf
    total = TOTAL + 0.25
    m = build(total)
    out = os.path.join("v3out", "music_v13.wav")
    sf.write(out, m, SR, subtype="FLOAT")
    print(f"wrote {out} {len(m)/SR:.2f}s lufs {P.lufs(m):.1f} "
          f"peak {20*np.log10(np.abs(m).max()):.1f}")
    print("  " + " ".join(f"{k}:{v:4.1f}%" for k, v in P.spectral_balance(m).items()))
