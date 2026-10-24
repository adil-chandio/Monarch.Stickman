#!/usr/bin/env python3
"""
audio_v10.py — the v10 mix: score in charge, SFX only where the eye is.

Why v9 sounded busy
-------------------
v9 fired **152** sound events (40 caption pops, 89 keystrokes, 16 pill pops, 7
images, 7 flash bursts, 10 punches, textures…) and its music sat 15 dB under the
voice. Measured: the panel layer was audible in 100 % of the timeline and the
music never rose above −33 dBFS. So the thing filling the space behind the
narration was a metronome of pops, not music. That is the irritation.

The v10 policy, enforced in code
--------------------------------
1. **Music carries the mood.** `music_v10` is a full score (8 layers, arrangement
   follows the beat map). It is 5–7 dB under the voice, ducked by the voice's own
   envelope, and EQ-carved at 1.2–3.4 kHz so words stay untouched.
2. **No sound on the caption bar.** The blue bar changes 40 times; it gets
   nothing. Its own word animations are silent — the voice is the event.
3. **SFX only on focal points**, and no two within 0.55 s:
   scene cuts, the 3 biggest display words, the arrest/quote/hook hits, the
   crown glint, the flame ignition, the scales, the iron latch, the end card.
4. **Typing survives exactly where it is diegetic**: the real typewriter run
   (16 characters on screen) plus the three strongest lower-text reveals, played
   at −22 dB and only when nothing else is sounding.
5. **Loudness, not level.** Everything is placed by peak, then the master chain
   (gentle bus compression + tape + 3-band tilt + limiter) is tuned to
   −13 LUFS with a −1 dBTP ceiling.

Run: python audio_v10.py  ->  v3out/mix_v10.wav (+ stems)
"""
from __future__ import annotations

import json
import os
import wave
from collections import defaultdict

import numpy as np
import soundfile as sf

import audio_v3 as A
import audio_v9 as V9           # keystroke kit + event parsing + helpers
import music_v10
from sfx_v8 import SR
from timeline_v4 import BEATS, TOTAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "v3out")

CONFIG = dict(
    MUSIC_UNDER_VOICE_DB=3.0,   # music RMS under voice RMS (ducked on top)
    ACCENT_PEAK=-9.0,
    KEY_PEAK=-15.0,             # typing is an accent, not a layer
    DUCK_MUSIC=0.34,            # how far the voice pushes the score down
    DUCK_ACCENT=0.30,
    MIN_GAP=0.55,               # no two accents closer than this
    REVERB=0.06,
    KEYS_ON=True,
    # master
    TARGET_LUFS=-13.0,
    CEILING=0.89,               # -1.0 dBFS
)

rng = np.random.default_rng(1010)


def peak_db(x):
    return 20 * np.log10(max(float(np.abs(x).max()), 1e-9))


def stage(x, target_dbfs):
    p = float(np.abs(x).max())
    return x * (10 ** (target_dbfs / 20) / p) if p > 0 else x


# ---------------------------------------------------------------- event filter
class Placer:
    """Places accents with a hard minimum gap, priority wins."""

    def __init__(self, buf, send, gap):
        self.buf, self.send, self.gap = buf, send, gap
        self.times: list[float] = []
        self.log = []

    def free(self, t, priority=False):
        if priority:
            return True
        return all(abs(t - u) >= self.gap for u in self.times)

    def hit(self, name, at, gain, pan=0.0, rev=0.0, semis=0.0, priority=False, tag=""):
        if not self.free(at, priority):
            return False
        sig, sync = V9.sound(name)
        V9.place(self.buf, sig, at - sync, gain=gain, pan=pan,
                 rev=self.send if rev else None, rev_gain=rev, semis=semis)
        self.times.append(at)
        self.log.append((round(at, 2), name, tag))
        return True


def design(total: float):
    data = V9.load_events()
    ev = data["events"]
    n = A.T(total)
    keys = np.zeros((n, 2), dtype=np.float32)
    accents = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)
    P = Placer(accents, send, CONFIG["MIN_GAP"])
    counts = defaultdict(int)

    # ---------------------------------------------------------------- 1 · cuts
    TR = {"slide": ("whoosh_soft", .75), "whoosh": ("whoosh_mid", .85),
          "flash": ("whoosh_hard", .95), "slam": ("whoosh_hard", 1.0),
          "punch": ("whoosh_huge", 1.0)}
    for e in ev:
        if e["el"] == "transition":
            name, g = TR.get(e["label"], ("whoosh_mid", .85))
            P.hit(name, e["t"], g, pan=float(rng.uniform(-.2, .2)),
                  rev=CONFIG["REVERB"], priority=True, tag="cut")
            counts["cuts"] += 1

    # ------------------------------------------------- 2 · the big display words
    for e in ev:
        if e["el"] == "big" and e["fs"] >= 90:
            P.hit("stamp", e["t"], 0.95, pan=V9.pan_for(e["x"]),
                  rev=CONFIG["REVERB"], priority=True, tag="bigword")
            counts["bigwords"] += 1

    # ------------------------------------------------------------- 3 · pictures
    PIC = {"icon_crown": ("glint", .8), "icon_flame": ("fire_ignite", .85),
           "icon_scale": ("sway_metal", .75), "icon_warning": ("metal_tick", .6),
           "king_throne": ("materialize_big", .7), "palace_party": ("materialize_big", .7),
           "chained_hand": ("materialize_big", .75)}
    for e in ev:
        if e["el"] == "image":
            name, g = PIC.get(e["label"], ("materialize", .6))
            if P.hit(name, e["t"], g, pan=V9.pan_for(e["x"]), rev=CONFIG["REVERB"],
                     priority=name in ("fire_ignite", "materialize_big", "glint"),
                     tag="picture"):
                counts["pictures"] += 1

    # --------------------------------------------------- 4 · punches (weight)
    for e in data["derived"]:
        amp = e["amp"]
        if amp >= 0.6:
            P.hit("impact_hard" if amp >= 0.85 else "impact", e["t"],
                  1.0 if amp >= 0.85 else 0.7, rev=CONFIG["REVERB"],
                  priority=True, tag="punch")
            counts["punches"] += 1

    # ---- the arrest: iron latch under the camera punch (the story's turning point)
    arrest = [e for e in data["derived"] if abs(e["t"] - 29.52) < 0.05]
    if arrest:
        P.hit("clank", arrest[0]["t"] + 0.06, 0.55, pan=0.25,
              rev=CONFIG["REVERB"], priority=True, tag="arrest")
        counts["arrest"] += 1

    # ------------------------------------------- 5 · the end-card punctuation
    end = BEATS[-1]["start"]
    P.hit("bell_low", end + 1.55, 0.55, rev=CONFIG["REVERB"], priority=True, tag="end")
    P.hit("sparkle", end + 4.10, 0.42, pan=0.15, tag="end")
    counts["end"] += 2

    # ------------------------------------------------------------ 6 · typing
    if CONFIG["KEYS_ON"]:
        text_events = [e for e in ev if e["el"] == "text"]
        runs = V9.typewriter_runs(text_events)
        in_run = {id(e) for r in runs for e in r}

        def K(t, weight, gain, pan):
            if not P.free(t, False) and P.times and min(abs(t - u) for u in P.times) < 0.25:
                return
            name = {"hard": "key_hard", "mid": "key_mid", "soft": "key_soft",
                    "space": "key_space", "ret": "key_return"}[weight]
            sig, sync = V9.sound(name)
            V9.place(keys, sig, t - sync, gain=gain, pan=pan, rev=None,
                     semis=float(rng.uniform(-.8, .8)))
            counts["keys"] += 1

        # 6a. the genuine typewriter run — one key per character
        for r in runs:
            for i, e in enumerate(r):
                ch = e["label"][-1:]
                w = "space" if ch == " " else ("hard" if (ch.isupper() and i) else "mid")
                K(e["t"], w, 1.0 if w == "space" else 0.85, V9.pan_for(e["x"]))
            K(r[-1]["t"] + 0.06, "ret", 0.8, V9.pan_for(r[-1]["x"]))
            counts["typed_runs"] += 1

        # 6b. the three strongest lower-text reveals (not all of them)
        solo = [e for e in text_events if id(e) not in in_run and e["fs"] >= 44]
        solo.sort(key=lambda e: -e["fs"])
        for e in solo[:3]:
            for i in range(2):
                K(e["t"] - (2 - i) * 0.075, "mid" if i else "soft", 0.55, V9.pan_for(e["x"]))
            K(e["t"], "space", 0.7, V9.pan_for(e["x"]))
            counts["typed_reveals"] += 1

    wet = A.VERB_SFX(send)
    accents = (accents + wet * CONFIG["REVERB"]).astype(np.float32)
    return keys, accents, dict(counts), P.log


# ------------------------------------------------------------------ master bus
def master(mix: np.ndarray) -> np.ndarray:
    """Gentle, musical chain: tilt → glue → tape → limiter."""
    mix = A.hp(mix, 26)
    # small low tilt for phone weight, small high shelf for air
    mix = mix + A.bp(mix, 55, 130, order=2) * 0.10
    mix = mix + A.hp(mix, 9000) * 0.10
    mix = A.compress(mix, -18, 1.8, .020, .30, 0.0)      # slow glue
    mix = A.tape(mix, 1.08, 0.0)
    pk = float(np.abs(mix).max())
    if pk > 0:
        mix = mix / pk * 0.985
    mix = np.tanh(mix * 1.02) / 1.02                     # soft ceiling
    pk = float(np.abs(mix).max())
    mix = mix / max(pk, 1e-9) * CONFIG["CEILING"]
    fi, fo = A.T(.02), A.T(1.6)
    mix[:fi, :] *= np.linspace(0, 1, fi)[:, None].astype(np.float32)
    mix[-fo:, :] *= np.linspace(1, 0, fo)[:, None].astype(np.float32)
    return mix.astype(np.float32)


def build() -> str:
    total = TOTAL + 0.25
    n = A.T(total)

    print("voice…");  voice, venv = A.build_voice(total)
    print("music…");  music = music_v10.build(total)
    print("design…")
    keys, accents, counts, log = design(total)
    print("       " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"       accents placed: {len(log)} in {total:.0f}s = {len(log)/total:.2f}/s")
    for t_, nm, tag in log:
        print(f"         {t_:6.2f}s  {nm:<16} {tag}")

    voice, music = voice[:n], music[:n]
    keys, accents = keys[:n], accents[:n]

    # ---- voice reference
    voice = stage(voice, -1.5)
    vr = A.rms_db(voice)

    # ---- score: RMS under the voice, then ducked by the voice envelope
    music = music / max(np.abs(music).max(), 1e-9)
    music = music * 10 ** ((vr - CONFIG["MUSIC_UNDER_VOICE_DB"] - A.rms_db(music)) / 20)

    keys = stage(keys, CONFIG["KEY_PEAK"])
    accents = stage(accents, CONFIG["ACCENT_PEAK"]) if np.abs(accents).max() > 0 else accents

    d = A.smooth(venv[:n], 220)
    d = np.clip(d / max(d.max(), 1e-9) * 2.4, 0, 1)
    music_ducked = music * (1 - CONFIG["DUCK_MUSIC"] * d)[:, None]
    accents_ducked = accents * (1 - CONFIG["DUCK_ACCENT"] * d)[:, None]

    mix = voice + music_ducked + accents_ducked + keys
    mix = master(mix)

    for name, x in (("stem_voice", voice), ("stem_music", music),
                    ("stem_music_ducked", music_ducked),
                    ("stem_keys", keys), ("stem_accents", accents)):
        sf.write(os.path.join(OUT, name + ".wav"), x.astype(np.float32), SR, subtype="FLOAT")
    path = os.path.join(OUT, "mix_v10.wav")
    sf.write(path, mix.astype(np.float32), SR, subtype="FLOAT")

    print(f"wrote {path} {n / SR:.2f}s")
    print(f"  rms  voice {A.rms_db(voice):5.1f}  music {A.rms_db(music_ducked):5.1f}  "
          f"accents {A.rms_db(accents_ducked):5.1f}  keys {A.rms_db(keys):5.1f} dBFS")
    print(f"  peak voice {peak_db(voice):5.1f}  music {peak_db(music_ducked):5.1f}  "
          f"mix {peak_db(mix):5.2f} dBFS")
    return path


if __name__ == "__main__":
    build()
