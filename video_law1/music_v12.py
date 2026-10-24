#!/usr/bin/env python3
"""
music_v12.py — the bed, cut down to what a narration video actually needs.

Why v10's score was rejected
----------------------------
v10 ran **eight** layers at 84 BPM: felt-piano motif, celesta, bell, cello
counter-line, heartbeat pulse, reverse swells, sub, pad. Under a voice-over that
is a second performance competing with the first one — "bilawaja music". Even
with the echo fixed the arrangement itself was the problem.

The v12 rule: *one idea at a time, and never a melody.*
  pad    one sustained chord per scene, slow attack, low register, dark
  sub    the chord root an octave down, enters only where the edit gets heavy
  mark   ONE note at a scene change (10 in the whole video) — a marker, not a tune

No arpeggios, no bells, no celesta, no counter-line, no noise layers, no
reverse swells. The bed is mixed 8 dB under the voice, single short room.
"""
from __future__ import annotations

import os

import numpy as np

import audio_v3 as A
from audio_v3 import (SR, T, NOTE, CHORDS, ROOT, strings, sub808, piano,
                      place, drone)
from timeline_v4 import BEATS, TOTAL

ROOM = A.Reverb(0.42, 11.0, 0.010, 3800, 7)
SEND_SCALE = float(os.environ.get("MV_REVERB", "1.0"))
BUS_WET = 0.12

# one chord per scene, in the order of the beat map (Am - F - C - G family)
SCENE_CHORD = ["Am", "F", "C", "G", "Dm", "Am", "F", "C", "G", "Am"]
# how heavy each scene is: 0 = pad only, 1 = pad + sub + a mark note
WEIGHT = {"hook": .55, "title": .45, "story": .30, "danger": .70,
          "shock": .80, "teach": .35, "bright": .40, "quote": .30, "end": .75}


def verb(x):
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    wet = ROOM(x)
    wet = A.hp(wet, 280)
    wet = A.lp(wet, 4800)
    return wet.astype(np.float32)


def build(total: float) -> np.ndarray:
    n = T(total)
    music = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)

    for i, b in enumerate(BEATS):
        t0 = float(b["start"])
        dur = float(b["dur"])
        if t0 >= total:
            break
        ch = SCENE_CHORD[i % len(SCENE_CHORD)]
        tones = CHORDS[ch]
        root = NOTE[ROOT[ch]]
        w = WEIGHT.get(b.get("kind", "story"), .35)

        # ------------------------------------------------------------- pad
        # one chord for the whole scene, 0.9 s attack so it never "stabs"
        freqs = [NOTE[t] for t in tones[:3]]
        pad = strings([f / 2 for f in freqs], dur + 1.1,
                      bright=.35, attack=.9, release=1.3, detune=5.0)
        pad = A.lp(pad, 1500)
        place(music, pad, t0, gain=.30 + .10 * w, width=.30,
              rev=send, rev_gain=.05)

        # ------------------------------------------------------------- sub
        if w >= .45:
            sub = sub808(root / 2, min(dur, 3.2), glide=None, drive=1.3)
            place(music, sub, t0, gain=.16 + .10 * w, rev=send, rev_gain=.02)

        # ------------------------------------------------------------ mark
        # a single low note as the scene changes; nothing during the sentence
        if i > 0:
            m = piano(NOTE[tones[0]] * 2, 1.6, bright=.45, vel=.8)
            m = A.lp(m, 2400)
            pan = (-0.12, 0.12)[i % 2]
            place(music, m, t0 - .02, gain=.16, pan=pan, rev=send, rev_gain=.07)

    # ---------------------------------------------------------------- tone
    # dark and mid-forward: carve the word band, keep the low end for weight,
    # no high "sheen" boost (that is what made the old bed hissy).
    music = (music - A.bp(music, 1200, 3400, order=2) * .45).astype(np.float32)
    music = (music - A.bp(music, 140, 420, order=2) * .35).astype(np.float32)
    music = music + A.bp(music, 50, 110, order=2) * .55
    music = A.lp(music, 5200)
    music = A.tape(music, 1.04, 0.0)

    wet = verb(send) * BUS_WET * SEND_SCALE
    music = (music + wet).astype(np.float32)
    music = A.widen(music, .08)

    # fade the head/tail so the bed never starts or stops with a click
    fi, fo = T(.6), T(1.2)
    music[:fi] *= np.linspace(0, 1, fi)[:, None].astype(np.float32)
    music[-fo:] *= np.linspace(1, 0, fo)[:, None].astype(np.float32)

    pk = float(np.abs(music).max())
    return (music / max(pk, 1e-9) * .85).astype(np.float32)


def build_bed(total: float):
    m = build(total)
    env = np.abs(m).max(axis=1)
    return m, A.smooth(env, 220)


if __name__ == "__main__":
    import soundfile as sf
    total = TOTAL + 0.25
    m = build(total)
    out = os.path.join("v3out", "music_v12.wav")
    sf.write(out, m, SR, subtype="FLOAT")
    print(f"wrote {out} {len(m)/SR:.2f}s rms {A.rms_db(m):.1f} dBFS "
          f"peak {20*np.log10(np.abs(m).max()):.1f}")
