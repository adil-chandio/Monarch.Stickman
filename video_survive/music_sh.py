#!/usr/bin/env python3
"""
music_sh.py — score for "How Ancient Humans Survived" (46 s).

Same engine as v13 (GeneralUser GS samples + pedalboard + BS.1770 master), a
different palette: low strings and contrabass instead of piano-led pad, taiko
instead of a heartbeat, celesta for the two "hope" moments (fire, harvest).

There is one arc, and the picture is cut to it:

    beat 1-2   cold, sparse, low          (fear)
    beat 3-4   warm pad + crackle space   (relief)
    beat 5     stone pulse, rhythmic      (work)
    beat 6     driving taiko + low strings (peak)
    beat 7-8   settle                     (safety)
    beat 9     brighter, celesta          (hope)
    beat 10    resolve, one swell         (identity)

No melody line: the story is in the picture and the words.
"""
from __future__ import annotations

import os

import numpy as np

import audio_v3 as A
import premium_audio as P
from audio_v3 import NOTE, SR
from timeline_sh import BEATS, TOTAL

# D minor family — darker than the Law score (A minor), same "no melody" rule
CHORD = {
    1: ["D3", "A3", "D4"], 2: ["D3", "F3", "A3"], 3: ["D3", "A3", "F4"],
    4: ["A#2", "F3", "D4"], 5: ["G2", "D3", "A#3"], 6: ["D3", "A3", "D4"],
    7: ["A#2", "F3", "A#3"], 8: ["F2", "C3", "F3"], 9: ["F2", "C3", "A3"],
    10: ["D3", "F3", "A3", "D4"],
}
ROOT_NOTE = {1: "D1", 2: "D1", 3: "D1", 4: "A#1", 5: "G1", 6: "D1",
             7: "A#1", 8: "F1", 9: "F1", 10: "D1"}
WEIGHT = {1: .35, 2: .55, 3: .50, 4: .45, 5: .60, 6: .95, 7: .35, 8: .40,
          9: .55, 10: .80}

PAD_DB, SUB_DB, MARK_DB, SHEEN_DB, PERC_DB = -15.0, -52.0, -19.0, -22.0, -21.0


def midi(f: float) -> int:
    return int(round(69 + 12 * np.log2(f / 440.0)))


def build(total: float, seed: int = 46) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = A.T(total)

    def player(prog, gain=-6.0):
        ins = P.Instruments(gain_db=gain)
        ins.program(0, prog)
        return ins

    pad = player("strings")
    low = player("contrabass")
    mark = player("cello")
    sheen = player("celesta")
    perc = player("taiko")

    sub = np.zeros((n, 2), dtype=np.float32)

    for b in BEATS:
        t0, dur, k = float(b["start"]), float(b["dur"]), int(b["n"])
        w = WEIGHT[k]
        tones = CHORD[k]

        # pad: the chord, low and slow, overlapping the cut
        for j, tn in enumerate(tones[:3]):
            # voicing: the low octave only where the scene must feel heavy.
            # Voicing everything down an octave is what made an earlier pass
            # measure 58 % of its energy below 120 Hz.
            pad.note(0, midi(NOTE[tn]) + (-12 if (k in (1, 2, 6) and j == 0) else 0),
                     vel=int(64 + 26 * w + rng.integers(-4, 5)),
                     at=t0 + rng.uniform(-.01, .01), dur=dur + 1.0)

        # contrabass: the floor of the mix, enters when the edit gets heavy
        if w >= .5:
            low.note(0, midi(NOTE[ROOT_NOTE[k]]) + 12, vel=int(62 + 20 * w),
                     at=t0 + .02, dur=min(dur, 3.4))

        # one low cello note at the cut — a marker, never a tune
        if k > 1:
            mark.note(0, midi(NOTE[tones[0]]) + 12,
                      vel=int(58 + rng.integers(-4, 5)),
                      at=t0 + .04, dur=float(rng.uniform(.9, 1.4)))

        # taiko: the pulse of work and hunt (beats 5, 6), soft elsewhere
        if k in (5, 6):
            step, hits = (0.62, 6) if k == 6 else (0.80, 4)
            for i in range(hits):
                tt = t0 + .55 + i * step
                if tt > t0 + dur - .2:
                    break
                acc = 1.0 if i % 2 == 0 else .72
                perc.note(0, 40 if k == 6 else 38,
                          vel=int((58 + 40 * w) * acc),
                          at=tt + rng.uniform(-.006, .006), dur=.5)
        elif k in (4, 10):
            for i in range(2):
                perc.note(0, 36, vel=int(50 + 20 * w), at=t0 + 1.0 + i * 1.9, dur=.7)

        # sub: weight under the heaviest scenes
        if w >= .55:
            s = A.sub808(NOTE[ROOT_NOTE[k]] / 2, min(dur, 3.0), drive=1.15)
            A.place(sub, s, t0, gain=1.0)

        # celesta: only fire (3) and harvest (9) — the two "hope" beats
        if k in (3, 9):
            for j, tn in enumerate(tones[:2]):
                sheen.note(0, midi(NOTE[tn]) + 24,
                           vel=int(56 + rng.integers(-4, 5)),
                           at=t0 + .55 + j * .34, dur=1.6)
    # final resolve: one high celesta note over the last chord
    last = BEATS[-1]
    sheen.note(0, midi(NOTE["D5"]), vel=62, at=last["start"] + 2.0, dur=2.4)

    padx = P.fit_peak(pad.render(total), PAD_DB)
    lowx = P.fit_peak(low.render(total), PAD_DB - 8)
    markx = P.fit_peak(mark.render(total), MARK_DB)
    sheenx = P.fit_peak(sheen.render(total), SHEEN_DB)
    percx = P.fit_peak(perc.render(total), PERC_DB)
    mix = (padx + lowx + markx + sheenx + percx + P.fit_peak(sub, SUB_DB))

    from pedalboard import Pedalboard, Reverb
    room = Pedalboard([Reverb(room_size=0.34, damping=0.82, wet_level=0.055,
                              dry_level=0.945, width=0.55)])
    mix = np.ascontiguousarray(room(np.array(mix.astype(np.float32).T, dtype=np.float32,
                                             order="C"), SR).T)

    fo, fi = A.T(1.4), A.T(.5)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None].astype(np.float32)
    mix[:fi] *= np.linspace(0, 1, fi)[:, None].astype(np.float32)
    return P.master(mix.astype(np.float32), target_lufs=-14.0)


if __name__ == "__main__":
    import soundfile as sf
    m = build(TOTAL)
    out = os.path.join("out", "music_sh.wav")
    sf.write(out, m, SR, subtype="FLOAT")
    print(f"wrote {out} {len(m)/SR:.2f}s lufs {P.lufs(m):.1f} "
          f"peak {20*np.log10(np.abs(m).max()):.1f}")
    print("  " + " ".join(f"{k}:{v:4.1f}%" for k, v in P.spectral_balance(m).items()))
