#!/usr/bin/env python3
"""
music_v10.py — the background score, rebuilt.

v9's bed measured −33…−49 dBFS RMS: effectively inaudible next to a −20 dB voice,
so the space behind the narration was filled by UI pops and crackle beds. That is
what read as "irritating". v10 puts the *music* back in charge of the mood and
keeps the SFX layer almost empty.

Eight layers, all synthesized (see audio_v3 for the instrument primitives):

  sub      sustained root an octave down, 0.35 s attack
  pad      slow string triad with reverb send
  piano    the felt-piano motif (the thing people remember)
  cello    counter-line fifth, only where there is energy
  pulse    soft heartbeat thump, only in the busy sections
  air      band-passed noise husk for width/hush, −36 dB
  bell     one in-key bell every other bar at high energy
  swell    reverse swell + filter opening into the three big sections

The arrangement follows the video's own beat map, so the score breathes with the
picture. Everything is quantised to A minor (Am–F–C–G) for cohesion.
"""
from __future__ import annotations

import os

import numpy as np

import audio_v3 as A
from audio_v3 import (SR, T, NOTE, CHORDS, ROOT, piano, strings, sub808, kick,
                      drone, place, nr, widen, rng)
from timeline_v4 import BEATS, TOTAL

# A tight, dark room instead of a 1.6 s hall. This is the single biggest reason
# the bed sounded like an echo: the old chain sent every element into a long
# convolution AND added the same reverb again on the whole bus.
ROOM = A.Reverb(0.42, 11.0, 0.010, 3800, 7)      # 0.42 s, fast decay, dark
SEND_SCALE = float(os.environ.get("MV_REVERB", "1.0"))   # 0 = fully dry (for QA)
BUS_WET = 0.15


def _send(buf, at, sig, gain=1.0, width=0.0, rev_gain=0.0, pan=0.0):
    if SEND_SCALE > 0:
        A.place(buf, sig, at, gain=gain, pan=pan, width=width, rev=None)
    return None


def verb(x):
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    wet = ROOM(x)
    wet = A.hp(wet, 260)          # keep the wash out of the low end
    wet = A.lp(wet, 5200)         # and out of the sibilance band
    return wet.astype(np.float32)


BPM = 84.0
BEAT = 60.0 / BPM
BAR = BEAT * 4
PROG = ["Am", "F", "C", "G"]

# energy per scene kind, and how much of it each section gets over time
ENERGY = {"hook": .34, "title": .52, "story": .58, "danger": .74,
          "shock": .16, "teach": .72, "bright": .88, "quote": .26, "end": .84}


def section_at(t: float) -> dict:
    cur = BEATS[0]
    for b in BEATS:
        if t >= b["start"]:
            cur = b
    return cur


def energy(t: float) -> float:
    b = section_at(t)
    base = ENERGY.get(b["kind"], .5)
    local = t - b["start"]
    return base * (0.78 + 0.22 * min(1.0, local / 1.5))


def build(total: float) -> np.ndarray:
    n = T(total)
    music = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)

    bars = int(total / BAR) + 2
    for bi in range(bars):
        t0 = bi * BAR
        if t0 >= total:
            break
        ch = PROG[bi % 4]
        tones = CHORDS[ch]
        en = energy(t0)
        root = NOTE[ROOT[ch]]

        # ---------------------------------------------------------------- sub
        sub = sub808(root / 2, BAR * 1.02, glide=None, drive=1.6)
        # gains are relative to each other; the whole bed is normalised once at
        # the end, so what matters here is the *balance* (sub / pad / piano).
        sub_g = (0.30 + 0.16 * en) * (0.55 if en < .2 else 1.0)
        place(music, sub / max(np.abs(sub).max(), 1e-9) * sub_g,
              t0, gain=1.0, width=.10, rev=send, rev_gain=.02)

        # ---------------------------------------------------------------- air
        a_n = T(BAR * 1.1)
        if en < .2:
            continue        # the hush of the quote/shock: voice owns it

        # ---------------------------------------------------------------- pad
        pad = strings([NOTE[x] for x in tones[1:4]], BAR * 1.16,
                      bright=.30 + .36 * en, attack=.80, release=1.5)
        padn = pad / max(np.abs(pad).max(), 1e-9)
        place(music, A.hp(padn, 180) * (0.118 + 0.075 * en), t0, gain=1.0, width=.60,
              rev=send, rev_gain=.10)

        # -------------------------------------------------------------- piano
        if en < .6:
            pat = [(0, 0.0), (2, 1.0), (3, 2.0), (4, 3.0)]
        else:
            pat = [(0, 0.0), (2, .5), (4, 1.0), (3, 1.5), (2, 2.0), (3, 2.5), (4, 3.0), (3, 3.5)]
        for k, pos in pat:
            f = NOTE[tones[min(k, len(tones) - 1)]] * 2
            p = piano(f, 1.35, bright=.90 + .25 * en, vel=1.0)
            pn = p / max(np.abs(p).max(), 1e-9)
            place(music, pn * (0.105 + 0.070 * en), t0 + pos * BEAT, gain=1.0,
                  pan=float(rng.uniform(-.20, .20)), rev=send, rev_gain=.11)

        # ------------------------------------------------------------ celesta
        # sparse high bells: this is where the score gets its sheen, without
        # putting sustained energy where the voice needs to be understood.
        if en >= .45:
            import sfx_v9
            for k, pos in ((3, 1.0), (4, 2.75)):
                if k >= len(tones):
                    break
                tone, _ = sfx_v9.bell(NOTE[tones[k]] * 4)
                tn = tone / max(np.abs(tone).max(), 1e-9)
                place(music, tn * (0.080 * en), t0 + pos * BEAT,
                      pan=float(rng.uniform(-.35, .35)), rev=send, rev_gain=.13)

        # -------------------------------------------------------------- cello
        if en >= .55:
            cel = strings([root * 1.5, root * 3.0], BAR * .9, bright=.22 + .2 * en,
                          attack=.55, release=1.1, detune=5.0)
            cel = cel / max(np.abs(cel).max(), 1e-9)
            place(music, cel * (0.075 * en), t0 + BEAT * .5, gain=1.0, width=.3,
                  rev=send, rev_gain=.06)

        # -------------------------------------------------------------- pulse
        if en >= .65:
            for pos in (0.0, 2.0):
                k = kick(.42, 96, 44, .28)
                k = k / max(np.abs(k).max(), 1e-9)
                place(music, k * (0.20 * en), t0 + pos * BEAT, gain=1.0,
                      rev=send, rev_gain=.02)

        # --------------------------------------------------------------- bell
        if en >= .70 and bi % 2 == 0:
            import sfx_v9
            tone, _ = sfx_v9.bell(NOTE[tones[3]] * 4)
            tone = tone / max(np.abs(tone).max(), 1e-9)
            place(music, tone * (0.085 * en), t0 + BEAT * 3.5,
                  pan=float(rng.uniform(-.3, .3)), rev=send, rev_gain=.10)

    # ------------------------------------------------------- section swells
    for b, strength in ((BEATS[1], 1.0), (BEATS[5], 0.8), (BEATS[9], 1.0)):
        t = b["start"]
        # reverse swell out of the bed itself (no sample, no SFX library)
        sw = T(1.3)
        x = A.nz(sw) * np.linspace(0, 1, sw) ** 2.2
        x = A.bp(x, 300, 5200) * .06 * strength
        place(music, np.stack([x, np.roll(x, 300)], axis=1), t - 1.3, gain=1.0,
              rev=send, rev_gain=.06)
        # a low taiko-ish hit exactly on the cut
        hit = A.kick(.9, 110, 38, .5)
        hit = hit / max(np.abs(hit).max(), 1e-9)
        place(music, hit * (0.26 * strength), t, gain=1.0, rev=send, rev_gain=.04)

    # exactly one reverb pass, at 30 % — the sends above are the only wet
    music = (music + verb(send) * BUS_WET * SEND_SCALE).astype(np.float32)
    music = A.hp(music, 30)

    # ---- tone: a score with weight, sheen and a hole where the voice lives.
    # 1.2–3.4 kHz is carved (that is where words need room), 1.8–7 kHz is added
    # back as instrument "sheen", and 140–420 Hz is trimmed so the bed is not wool.
    carve = A.bp(music, 1200, 3400, order=2)
    music = (music - carve * 0.42).astype(np.float32)
    music = (music - A.bp(music, 140, 420, order=2) * 0.42).astype(np.float32)
    music = music + A.bp(music, 55, 120, order=2) * 0.70        # sub weight
    music = music + A.bp(music, 400, 1000, order=2) * 0.22      # phone-speaker warmth
    music = music + A.bp(music, 1800, 7000, order=2) * 0.50     # sheen / bow noise
    music = music + A.hp(music, 5200) * 0.30                    # air

    # (the old white-noise "air bed" is gone: a constant 7 kHz hiss reads as
    #  tape noise, not as air. The top end now comes from the instruments.)
    music = A.tape(music, 1.10, 0.0)
    music = A.widen(music, .12)
    pk = float(np.abs(music).max())
    return (music / max(pk, 1e-9) * 0.88).astype(np.float32)


def build_bed(total: float) -> tuple[np.ndarray, np.ndarray]:
    """Returns (music, music_sidechain_key). The key is the music's own envelope,
    used so the voice ducks the bed smoothly instead of pumping."""
    m = build(total)
    env = np.abs(m).max(axis=1)
    k = max(3, T(.02))
    env = np.convolve(env, np.ones(k, dtype=np.float32) / k, mode="same")
    return m, env.astype(np.float32)


if __name__ == "__main__":
    import soundfile as sf
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v3out", "music_v10.wav")
    m = build(TOTAL + .25)
    sf.write(out, m, SR, subtype="FLOAT")
    print(f"wrote {out} {len(m) / SR:.2f}s rms {20*np.log10(np.sqrt((m**2).mean())):.1f} dBFS "
          f"peak {20*np.log10(np.abs(m).max()):.1f}")
