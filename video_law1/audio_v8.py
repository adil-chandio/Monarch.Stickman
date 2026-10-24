#!/usr/bin/env python3
"""
audio_v8.py — the new MonarchVoice mix (v8).

What changed vs v7
------------------
* **The old SFX layer is gone.** `build_sfx()` from `audio_v3.py` (which leaned
  on the sampled library + `sfx_synth2.py`) is not called. Everything you hear
  under the voice now comes from `sfx_v8.py`, synthesized from scratch.
* **Typing.** Every caption word on screen is *typed*: a keystroke lands exactly
  when the word appears (the renderer reveals word `i` at `cue_t + i*0.095 s`,
  see `render_v3.draw_caption`). Keys vary in weight, pitch, pan and brightness,
  keywords land harder, cue endings get the spacebar / return key, and each new
  caption panel opens with a soft UI pop.
* **Fewer, better accents.** Roughly half the old hit count: whooshes only on
  scene changes, cinematic sub hits only on the three moments that deserve one,
  one metal latch for the arrest, one bell for the title and one for the end.
* Music bed and the voice chain are unchanged — they were the parts that worked.

Tuning: everything is in `CONFIG`. Set `TYPING_GAIN=0` to mute typing only,
`ACCENT_GAIN=0` to hear the video with music + voice only, etc.

Run:  python audio_v8.py            -> v3out/mix_v8.wav (+ stems)
"""
from __future__ import annotations

import json
import os
import wave

import numpy as np
import soundfile as sf

import audio_v3 as A            # voice chain, music bed, mix helpers (reused)
from timeline_v4 import BEATS, TOTAL
from sfx_v8 import SR, build_kit, KIT_DIR

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "v3out")
os.makedirs(OUT, exist_ok=True)

CONFIG = dict(
    TYPING_GAIN=0.34,      # base keystroke level (relative, before bus staging)
    TYPING_KEY_GAIN=1.18,  # extra weight on highlighted keywords
    TYPING_ON=True,
    PANEL_POP_GAIN=0.16,   # the soft "panel lands" pop at every caption change
    ACCENT_GAIN=0.62,      # whooshes / impacts / bells / latches
    TRANSITION_GAIN=0.22,  # whooshes between scenes
    SFX_REVERB=0.03,       # accents only, never on the typing
    TYPING_PEAK_DBFS=-13.5,  # absolute peak target for the keystrokes
    ACCENT_PEAK_DBFS=-8.0,   # absolute peak target for the accents
    DUCK_SFX=0.18,         # how much the voice pushes the SFX down (0 = no duck)
    DUCK_MUSIC=0.60,
    MUSIC_UNDER_VOICE_DB=12.0,
)

# Caption cadence used by the renderer (render_v3.draw_caption: `word_i * .095`).
TYPE_STEP = 0.095
rng = np.random.default_rng(808)


# --------------------------------------------------------------------- kit I/O
def load_kit() -> dict:
    index_path = os.path.join(KIT_DIR, "index.json")
    if not os.path.exists(index_path):
        build_kit(write=True)
    with open(index_path) as f:
        index = json.load(f)
    kit = {}
    for name, items in index.items():
        variants = []
        for it in items:
            p = os.path.join(KIT_DIR, it["wav"])
            with wave.open(p) as w:
                raw = w.readframes(w.getnframes())
            x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            variants.append((x, it["sync"]))
        kit[name] = variants
    return kit


KIT = load_kit()


def sound(name: str, variant: int | None = None) -> tuple[np.ndarray, float]:
    vs = KIT[name]
    x, sync = vs[rng.integers(len(vs))] if variant is None else vs[variant % len(vs)]
    return x.copy(), sync


# ------------------------------------------------------------------- placement
def place(buf, sig, at, gain=1.0, pan=0.0, rev=None, rev_gain=0.0):
    """Frame-accurate placement; `at` is where the sound's sync point lands."""
    A.place(buf, sig, at, gain=gain, pan=pan, width=0.10, rev=rev, rev_gain=rev_gain)


def hit(buf, name, sync_at, gain, pan=0.0, rev=None, rev_gain=0.0):
    sig, sync = sound(name)
    place(buf, sig, sync_at - sync, gain=gain, pan=pan, rev=rev, rev_gain=rev_gain)


# ---------------------------------------------------------------------- typing
KEY_BY_WEIGHT = {
    "light": ["key_soft", "key_tick", "key_soft", "key_mid"],
    "normal": ["key_mid", "key_mid", "key_soft", "key_hard"],
    "heavy": ["key_hard", "key_mid", "key_hard"],
}


def typing_layer(total: float):
    """A keystroke for every word that appears, plus panel pops."""
    n = A.T(total)
    buf = np.zeros((n, 2), dtype=np.float32)
    events = 0
    if not CONFIG["TYPING_ON"]:
        return buf, events

    for b in BEATS:
        cues = b["cue_times"]
        for ci, cue in enumerate(cues):
            words = cue["text"].split()
            kws = {k.upper() for k in cue["kw"]}
            cue_start = cue["t"]
            cue_end = cues[ci + 1]["t"] if ci + 1 < len(cues) else b["start"] + b["dur"]

            # panel entrance: one soft pop as the blue bar lands
            hit(buf, "pop", b["start"] + cue_start, CONFIG["PANEL_POP_GAIN"],
                pan=float(rng.uniform(-0.08, 0.08)))

            for wi, word in enumerate(words):
                t = b["start"] + cue_start + wi * TYPE_STEP
                if t >= b["start"] + cue_end:
                    break
                core = word.strip(".,!?\"“”…:;").upper()
                is_kw = core in kws
                last = wi == len(words) - 1
                long_word = len(core) >= 6

                if last:
                    name = "key_space" if (ci % 3 == 0 or len(words) > 4) else "key_return"
                    weight = "heavy"
                elif is_kw:
                    weight = "heavy"
                    name = None
                elif long_word:
                    weight = "normal"
                    name = None
                else:
                    weight = "light"
                    name = None
                if name is None:
                    pool = KEY_BY_WEIGHT[weight]
                    name = pool[int(rng.integers(len(pool)))]

                g = CONFIG["TYPING_GAIN"]
                if is_kw:
                    g *= CONFIG["TYPING_KEY_GAIN"]
                g *= float(rng.uniform(0.86, 1.06))
                # typing sits slightly left/right of centre like a real keyboard
                pan = float(np.clip(rng.normal(0, 0.16), -0.45, 0.45))
                hit(buf, name, t, g, pan=pan)
                events += 1
    return buf, events


# --------------------------------------------------------------------- accents
def accent_layer(total: float):
    n = A.T(total)
    buf = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)
    g = CONFIG["ACCENT_GAIN"]
    tr = CONFIG["TRANSITION_GAIN"]

    # ---- scene transitions: one whoosh per scene change, on the cut
    TR = {"punch": "whoosh_hard", "slide": "whoosh_soft", "whoosh": "whoosh_mid",
          "flash": "whoosh_hard", "slam": "whoosh_mid"}
    for b in BEATS[1:]:
        hit(buf, TR.get(b.get("trans", "whoosh"), "whoosh_mid"), b["start"] + 0.02,
            tr, pan=float(rng.uniform(-0.2, 0.2)), rev=send, rev_gain=CONFIG["SFX_REVERB"])

    b = {x["n"]: x for x in BEATS}
    st = lambda k: b[k]["start"] if k in b else BEATS[k - 1]["start"]

    # ---- 1 · hook: riser into "RUK JAO", then the hard stop
    s = st(1)
    hit(buf, "riser_short", s + 1.55, g * 0.55, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "impact_hard", s + 1.58, g * 0.95, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "key_return", s + 1.60, g * 0.55, pan=-0.12)

    # ---- 2 · title: build into the crown, bell on "MASTER"
    s = st(2)
    hit(buf, "riser", s + 1.10, g * 0.55, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "impact", s + 1.18, g * 0.80, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "bell", s + 1.30, g * 0.42, pan=0.10, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "sparkle", s + 3.10, g * 0.34, pan=0.18)

    # ---- 3 · France 1661: paper swish as the palace card slides in
    s = st(3)
    hit(buf, "swish", s + 0.55, g * 0.55, pan=-0.22)
    hit(buf, "pop_big", s + 1.55, g * 0.55, pan=0.16)

    # ---- 4 · the nobles murmur: one dry tick, nothing else
    s = st(4)
    hit(buf, "key_tick", s + 1.60, g * 0.30, pan=0.28)

    # ---- 5 · jealousy: low hit under the smile, sparkle as it catches
    s = st(5)
    hit(buf, "impact", s + 0.10, g * 0.70, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "sparkle", s + 2.05, g * 0.40, pan=-0.14)
    hit(buf, "riser_short", s + 3.62, g * 0.50)

    # ---- 6 · the arrest: slam + iron latch (the one metal moment)
    s = st(6)
    hit(buf, "slam", s + 1.20, g * 1.00, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "impact_hard", s + 1.30, g * 0.75, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "clank", s + 3.00, g * 0.50, pan=0.22, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "key_return", s + 3.05, g * 0.40, pan=-0.20)

    # ---- 7 · the lesson: clean, dry, one soft panel pop
    s = st(7)
    hit(buf, "pop_big", s + 1.05, g * 0.40, pan=-0.10)

    # ---- 8 · talent ⚖ credit: bright, one sparkle + one bell
    s = st(8)
    hit(buf, "sparkle", s + 2.55, g * 0.38, pan=0.14)
    hit(buf, "bell", s + 4.30, g * 0.30, pan=-0.16, rev=send, rev_gain=CONFIG["SFX_REVERB"])

    # ---- 9 · the quote: soft sub under the card, swish as the underline draws
    s = st(9)
    hit(buf, "impact", s + 0.10, g * 0.55, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "swish", s + 2.60, g * 0.42, pan=0.20)

    # ---- 10 · end card: long riser, slam, low bell, then out
    s = st(10)
    hit(buf, "riser", s - 0.55, g * 0.55, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "slam", s + 0.05, g * 0.95, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "bell_low", s + 1.55, g * 0.45, rev=send, rev_gain=CONFIG["SFX_REVERB"])
    hit(buf, "sparkle", s + 4.10, g * 0.34, pan=0.12)
    hit(buf, "whoosh_soft", s + 4.70, g * 0.35, pan=0.20)

    # a whisper of room on the accents only (the typing stays bone dry)
    wet = A.VERB_SFX(send)
    buf = (buf + wet * CONFIG["SFX_REVERB"]).astype(np.float32)
    return buf


# ------------------------------------------------------------------------ mix
def build() -> str:
    total = TOTAL + 0.25
    n = A.T(total)

    print("voice…")
    voice, venv = A.build_voice(total)
    print("music…")
    music = A.build_music(total)
    print("typing…")
    typing, n_keys = typing_layer(total)
    print(f"       {n_keys} keystrokes")
    print("accents…")
    accents = accent_layer(total)

    voice, music = voice[:n], music[:n]
    typing, accents = typing[:n], accents[:n]

    # ---- staging: voice is the reference
    voice = voice / max(np.abs(voice).max(), 1e-9) * 10 ** (-1.5 / 20)
    vr = A.rms_db(voice)

    music = music / max(np.abs(music).max(), 1e-9)
    music *= 10 ** ((vr - CONFIG["MUSIC_UNDER_VOICE_DB"] - A.rms_db(music)) / 20)

    # typing: present, never in front of the voice. Peak-referenced, because a
    # keystroke is a 3 ms transient — its RMS badly understates how loud it reads.
    if np.abs(typing).max() > 0:
        typing = typing / np.abs(typing).max() * 10 ** (CONFIG["TYPING_PEAK_DBFS"] / 20)
    accents = accents / max(np.abs(accents).max(), 1e-9) * 10 ** (CONFIG["ACCENT_PEAK_DBFS"] / 20)

    sfx = typing + accents

    # ---- ducking (typing is ducked far less than music: it *is* the detail)
    d = A.smooth(venv[:n], 260)
    d = np.clip(d / max(d.max(), 1e-9) * 2.2, 0, 1)
    music *= (1 - CONFIG["DUCK_MUSIC"] * d)[:, None]
    sfx *= (1 - CONFIG["DUCK_SFX"] * d)[:, None]

    mix = voice + music + sfx
    mix = A.tape(mix, 1.1, 0.0)
    mix = A.compress(mix, -11, 2.4, .004, .18, 0.0)
    mix = mix * (10 ** (3.8 / 20))
    mix = np.tanh(mix * 0.98) / 0.98
    pk = np.abs(mix).max()
    if pk > .89:
        mix = mix / pk * .89
    fi, fo = A.T(.02), A.T(1.4)
    mix[:fi, :] *= np.linspace(0, 1, fi)[:, None].astype(np.float32)
    mix[-fo:, :] *= np.linspace(1, 0, fo)[:, None].astype(np.float32)

    for nm, bus in (("stem_voice", voice), ("stem_music", music),
                    ("stem_typing", typing), ("stem_accents", accents)):
        sf.write(os.path.join(OUT, nm + ".wav"), bus.astype(np.float32), SR, subtype="FLOAT")
    path = os.path.join(OUT, "mix_v8.wav")
    sf.write(path, mix.astype(np.float32), SR, subtype="FLOAT")

    def db(v):
        return 20 * np.log10(max(float(np.abs(v).max()), 1e-9))

    print(f"wrote {path} {n / SR:.2f}s")
    print(f"  rms  voice {A.rms_db(voice):6.1f}  music {A.rms_db(music):6.1f}  "
          f"typing {A.rms_db(typing):6.1f}  accents {A.rms_db(accents):6.1f} dBFS")
    print(f"  peak voice {db(voice):6.1f}  music {db(music):6.1f}  typing {db(typing):6.1f}  "
          f"accents {db(accents):6.1f}  mix {db(mix):6.1f} dBFS")
    return path


if __name__ == "__main__":
    build()
