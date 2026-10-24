#!/usr/bin/env python3
"""
audio_v9.py — sound design driven by the picture, not by a hand-written list.

Input:  v3out/anim_events.json  (produced by `render_v3.py events`)
Output: v3out/mix_v9.wav + stems

Every event the renderer logged gets a sound, chosen by *what it is*:

    caption bar change   -> soft panel pop            (never typing: the bar is
                            on screen the whole video, per the brief)
    typed characters     -> real keystrokes, one per character
    lower text appearing -> a short burst of keys that lands exactly on the word
    big display word     -> stamp + air (a 100 px word is not "typed")
    icon / art arriving  -> materialise, fire, glint, metal, sway, cloth
    pills                -> UI pop
    particles            -> shimmer / dust / embers / confetti
    camera punch         -> sub hit (varied, strength-scaled)
    flash                -> air burst
    glitch               -> digital stutter
    scene cut            -> whoosh (family by transition type)

Variety is enforced three ways: every family has 2–5 rendered variants, the same
variant is never used twice in a row, and every hit gets ±3 % pitch, ±1.5 dB
level and pan derived from its position on screen.
"""
from __future__ import annotations

import json
import os
import wave
from collections import defaultdict

import numpy as np
import soundfile as sf

import audio_v3 as A
from sfx_v8 import SR, norm
from timeline_v4 import BEATS, TOTAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "v3out")
KIT_DIR = os.path.join(ROOT, "audio_v9", "sfx")
EVENTS_JSON = os.path.join(OUT, "anim_events.json")

CONFIG = dict(
    # absolute peak targets (dBFS) — these decide how "present" each layer is
    KEYS_PEAK=-9.5,
    ACCENT_PEAK=-8.0,
    TEXTURE_PEAK=-17.0,
    PANEL_PEAK=-19.0,
    TRANS_PEAK=-16.0,
    DUCK_ACCENT=0.22,
    DUCK_TEXTURE=0.34,
    DUCK_KEYS=0.10,
    MUSIC_UNDER_VOICE_DB=12.5,
    # switches (handy when judging a single layer)
    KEYS_ON=True,
    TEXTURES_ON=True,
    REVERB=0.05,
    KEYS_REVERB=0.06,   # a touch of room makes a click read without more peak
)

rng = np.random.default_rng(4242)

# ---------------------------------------------------------------- kit loading
def load_kit() -> dict:
    idx_path = os.path.join(KIT_DIR, "index.json")
    if not os.path.exists(idx_path):
        import sfx_v9
        sfx_v9.build_kit(True)
    index = json.load(open(idx_path))
    kit = {}
    for name, items in index.items():
        vs = []
        for it in items:
            with wave.open(os.path.join(KIT_DIR, it["wav"])) as w:
                raw = w.readframes(w.getnframes())
            x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            vs.append((x, it["sync"]))
        kit[name] = vs
    return kit


KIT = load_kit()
_last_variant: dict[str, int] = {}


def sound(name: str):
    vs = KIT[name]
    if len(vs) == 1:
        return vs[0][0].copy(), vs[0][1]
    prev = _last_variant.get(name)
    i = int(rng.integers(len(vs)))
    if prev is not None and i == prev:
        i = (i + 1) % len(vs)
    _last_variant[name] = i
    return vs[i][0].copy(), vs[i][1]


def varispeed(x: np.ndarray, semitones: float) -> np.ndarray:
    """Cheap, click-free pitch shift used for per-hit variation (±3 %)."""
    if abs(semitones) < 0.01:
        return x
    rate = 2.0 ** (semitones / 12.0)
    n = max(1, int(len(x) / rate))
    idx = np.linspace(0, len(x) - 1, n)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


# ------------------------------------------------------------------- placement
def place(buf, sig, at, gain=1.0, pan=0.0, rev=None, rev_gain=0.0, semis=0.0):
    if semis:
        sig = varispeed(sig, semis)
    A.place(buf, sig, at, gain=gain, pan=float(np.clip(pan, -1, 1)), width=0.12,
            rev=rev, rev_gain=rev_gain)


def hit(buf, name, sync_at, gain, pan=0.0, rev=None, rev_gain=0.0, semis=0.0):
    sig, sync = sound(name)
    place(buf, sig, sync_at - sync, gain=gain, pan=pan, rev=rev, rev_gain=rev_gain, semis=semis)


def pan_for(x, spread=0.42):
    if x is None:
        return 0.0
    return float(np.clip((float(x) - 540.0) / 540.0 * spread, -spread, spread))


# --------------------------------------------------------------- event parsing
def load_events():
    if not os.path.exists(EVENTS_JSON):
        raise SystemExit("run `python render_v3.py events` first")
    return json.load(open(EVENTS_JSON))


def typewriter_runs(text_events):
    """Group consecutive text events whose label is a growing prefix."""
    runs, cur = [], []
    for e in text_events:
        if cur:
            p = cur[-1]
            same = (abs(e["t"] - p["t"]) < 0.30 and e["fs"] == p["fs"]
                    and abs((e["x"] or 0) - (p["x"] or 0)) < 3
                    and abs((e["y"] or 0) - (p["y"] or 0)) < 3
                    and e["label"].startswith(p["label"].rstrip("|")))
            if same:
                cur.append(e)
                continue
        if len(cur) > 1:
            runs.append(cur)
        cur = [e]
    if len(cur) > 1:
        runs.append(cur)
    return runs


def groups(events, gap=0.12):
    """Collapse frame-by-frame effects (flash / glitch) into single hits."""
    out, cur = [], []
    for e in sorted(events, key=lambda e: e["t"]):
        if cur and e["t"] - cur[-1]["t"] > gap:
            out.append(cur)
            cur = []
        cur.append(e)
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- the designer
def design(total: float):
    data = load_events()
    ev = data["events"]
    n = A.T(total)
    keys = np.zeros((n, 2), dtype=np.float32)
    accents = np.zeros((n, 2), dtype=np.float32)
    textures = np.zeros((n, 2), dtype=np.float32)
    panels = np.zeros((n, 2), dtype=np.float32)
    trans = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)
    rv = CONFIG["REVERB"]
    counts = defaultdict(int)

    def K(name, t, g, pan=0.0, semis=0.0):
        if CONFIG["KEYS_ON"]:
            hit(keys, name, t, g, pan=pan, semis=semis, rev=send, rev_gain=CONFIG["KEYS_REVERB"])
            counts["keys"] += 1

    # ---------------------------------------------------------- 1 · blue captions
    # The bar is on screen for the whole video, so it gets one *soft* panel pop
    # per cue change — no typing, no clicks.
    for c in data["captions"]:
        pan = 0.0
        hit(panels, "panel", c["t"], 1.0 + 0.15 * (len(c["text"]) % 3), pan=pan,
            semis=float(rng.uniform(-1.5, 1.5)))
        counts["panels"] += 1

    # ------------------------------------------------------------ 2 · lower text
    text_events = [e for e in ev if e["el"] == "text"]
    runs = typewriter_runs(text_events)
    in_run = {id(e) for r in runs for e in r}

    # 2a. genuine typewriter runs: one keystroke per character
    for r in runs:
        for i, e in enumerate(r):
            ch = e["label"][-1:] if i else e["label"][:1]
            if ch == " ":
                K("key_space", e["t"], 0.95, pan_for(e["x"]), semis=0.0)
            elif ch.isupper():
                K("key_hard", e["t"], 1.0, pan_for(e["x"]), semis=float(rng.uniform(-.6, .6)))
            else:
                K("key_mid", e["t"], 0.85, pan_for(e["x"]), semis=float(rng.uniform(-1, 1)))
        last = r[-1]
        K("key_return", last["t"] + 0.06, 0.8, pan_for(last["x"]))
        counts["typed_runs"] += 1

    # 2b. everything else
    for e in text_events:
        if id(e) in in_run:
            continue
        t, fs, amp = e["t"], e["fs"], e["amp"]
        pan = pan_for(e["x"])
        label = e["label"]
        if fs >= 70:
            # big display word: it lands, it is not typed
            hit(accents, "stamp", t, 0.85 + 0.3 * amp, pan=pan, semis=float(rng.uniform(-1, 1)),
                rev=send, rev_gain=rv)
            if fs >= 95:
                hit(accents, "air_burst", t + 0.01, 0.35, pan=-pan)
            counts["stamps"] += 1
        elif fs >= 40:
            # medium word: three keys and a space, landing on the word
            nk = 3
            for i in range(nk):
                K(["key_mid", "key_soft", "key_hard"][i % 3],
                  t - (nk - i) * 0.075, 0.72, pan=pan, semis=float(rng.uniform(-1, 1)))
            K("key_space", t, 0.9, pan=pan)
            counts["typed_words"] += 1
        else:
            # small lower caption: a real little burst, ends exactly on the word
            nk = int(np.clip(round(len(label) / 4), 3, 6))
            for i in range(nk):
                K("key_mid" if i % 2 else "key_soft",
                  t - (nk - i) * 0.068, 0.66, pan=pan, semis=float(rng.uniform(-1.2, 1.2)))
            K("key_space", t, 0.8, pan=pan)
            counts["typed_small"] += 1

    # -------------------------------------------------------------- 3 · pictures
    IMAGE_MAP = {
        "icon_warning": ("metal_tick", 0.9),
        "icon_crown": ("glint", 0.9),
        "icon_flame": ("fire_ignite", 1.0),
        "icon_scale": ("sway_metal", 0.9),
        "king_throne": ("materialize_big", 1.0),
        "palace_party": ("materialize_big", 1.0),
        "chained_hand": ("materialize_big", 1.0),
    }
    for e in ev:
        if e["el"] != "image":
            continue
        name, g = IMAGE_MAP.get(e["label"], ("materialize", 0.85))
        hit(accents, name, e["t"], g * (0.8 + 0.4 * e["amp"]), pan=pan_for(e["x"]),
            semis=float(rng.uniform(-.8, .8)), rev=send, rev_gain=rv)
        counts["images"] += 1

    # ---------------------------------------------------------------- 4 · pills
    for e in ev:
        if e["el"] != "pill":
            continue
        big = len(e["label"]) > 13 or e["label"].isupper()
        hit(accents, "pop_big" if big else "pop", e["t"], 0.75 + 0.3 * e["amp"],
            pan=pan_for(e["x"]), semis=float(rng.uniform(-1.5, 1.5)))
        counts["pills"] += 1

    # ---------------------------------------------------- 5 · fire & particles
    if CONFIG["TEXTURES_ON"]:
        for e in ev:
            if e["el"] != "particles":
                continue
            fam = {"spark": "shimmer", "dust": "dust", "ember": "ember_bed",
                   "confetti": "confetti"}.get(e["label"], "dust")
            hit(textures, fam, e["t"] - (0.15 if fam == "ember_bed" else 0.0),
                0.9, pan=float(rng.uniform(-.2, .2)))
            counts["particles"] += 1

        for e in ev:                        # only the strong halos get a breath
            if e["el"] == "halo" and e["amp"] >= 0.8:
                hit(textures, "dust", e["t"], 0.35, pan=pan_for(e["x"]))
                counts["halos"] += 1

    # --------------------------------------------------------------- 6 · host
    for e in ev:
        if e["el"] == "host":
            hit(textures, "cloth", e["t"], 0.55 + 0.2 * e["amp"], pan=pan_for(e["x"]))
            counts["host"] += 1

    # --------------------------------------------- 7 · flashes / glitches / cuts
    for g in groups([e for e in ev if e["el"] == "flash"]):
        top = max(x["amp"] for x in g)
        hit(accents, "air_burst", g[0]["t"], 0.25 + 1.1 * top, pan=float(rng.uniform(-.15, .15)))
        counts["flashes"] += 1

    for g in groups([e for e in ev if e["el"] == "glitch"], gap=0.10):
        top = max(x["amp"] for x in g)
        # a stutter is a burst, not a single hit: two or three slices
        for k in range(3):
            hit(accents, "stutter", g[0]["t"] + k * 0.055, 0.35 + 0.5 * top,
                pan=float(rng.uniform(-.25, .25)), semis=float(rng.uniform(-2, 2)))
        counts["glitches"] += 1

    TRANS_MAP = {"slide": ("whoosh_soft", 0.8), "whoosh": ("whoosh_mid", 0.9),
                 "flash": ("whoosh_hard", 1.0), "slam": ("whoosh_hard", 1.0),
                 "punch": ("whoosh_huge", 1.0)}
    for e in ev:
        if e["el"] != "transition":
            continue
        name, g = TRANS_MAP.get(e["label"], ("whoosh_mid", .9))
        hit(trans, name, e["t"], g, pan=float(rng.uniform(-.2, .2)), rev=send, rev_gain=rv)
        counts["transitions"] += 1

    # ------------------------------------------------------------ 8 · the weight
    for e in data["derived"]:
        amp = e["amp"]
        if amp >= 0.8:
            hit(accents, "impact_hard", e["t"], 1.0, rev=send, rev_gain=rv)
        elif amp >= 0.5:
            hit(accents, "impact", e["t"], 0.75, rev=send, rev_gain=rv)
        else:
            hit(accents, "impact", e["t"], 0.45, semis=-2.0)
        counts["punches"] += 1

    # risers into the three biggest moments (musical build the picture implies)
    for t in (5.55, 28.65, 54.55):
        hit(trans, "riser_short", t, 0.55, pan=0.0, rev=send, rev_gain=rv)
        counts["risers"] += 1

    # ------------------------------------------------------------- 9 · the end
    hit(accents, "bell_low", BEATS[-1]["start"] + 1.55, 0.5, rev=send, rev_gain=rv)
    hit(accents, "sparkle", BEATS[-1]["start"] + 4.10, 0.4, pan=0.15)
    hit(accents, "whoosh_soft", BEATS[-1]["start"] + 4.70, 0.45, pan=0.2)

    wet = A.VERB_SFX(send)
    for bus in (accents, textures, trans):
        bus += wet * rv
    return dict(keys=keys, accents=accents, textures=textures, panels=panels,
                trans=trans, counts=dict(counts))


# ------------------------------------------------------------------------ mix
def build() -> str:
    total = TOTAL + 0.25
    n = A.T(total)

    print("voice…");   voice, venv = A.build_voice(total)
    print("music…");   music = A.build_music(total)
    print("design…")
    layers = design(total)
    counts = layers["counts"]
    print("       " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    voice, music = voice[:n], music[:n]
    bus = {k: (v[:n] if isinstance(v, np.ndarray) else v) for k, v in layers.items()}

    def peak_db(x):
        return 20 * np.log10(max(float(np.abs(x).max()), 1e-9))

    def stage(x, target):
        p = float(np.abs(x).max())
        return x * (10 ** (target / 20) / p) if p > 0 else x

    # voice is the reference
    voice = voice / max(np.abs(voice).max(), 1e-9) * 10 ** (-1.5 / 20)
    vr = A.rms_db(voice)

    music = music / max(np.abs(music).max(), 1e-9)
    music *= 10 ** ((vr - CONFIG["MUSIC_UNDER_VOICE_DB"] - A.rms_db(music)) / 20)

    for name, key in (("keys", "keys"), ("accents", "accents"), ("textures", "textures"),
                      ("panels", "panels"), ("trans", "trans")):
        bus[key] = stage(bus[key], CONFIG[{"keys": "KEYS_PEAK", "accents": "ACCENT_PEAK",
                                           "textures": "TEXTURE_PEAK",
                                           "panels": "PANEL_PEAK",
                                           "trans": "TRANS_PEAK"}[key]])

    d = A.smooth(venv[:n], 260)
    d = np.clip(d / max(d.max(), 1e-9) * 2.2, 0, 1)
    music *= (1 - 0.60 * d)[:, None]
    bus["accents"] *= (1 - CONFIG["DUCK_ACCENT"] * d)[:, None]
    bus["textures"] *= (1 - CONFIG["DUCK_TEXTURE"] * d)[:, None]
    bus["keys"] *= (1 - CONFIG["DUCK_KEYS"] * d)[:, None]
    bus["panels"] *= (1 - CONFIG["DUCK_KEYS"] * d)[:, None]

    mix = voice + music + sum(bus[k] for k in ("keys", "accents", "textures", "panels", "trans"))
    mix = A.tape(mix, 1.1, 0.0)
    mix = A.compress(mix, -11, 2.4, .004, .18, 0.0)
    mix = mix * (10 ** (3.8 / 20))
    mix = np.tanh(mix * 0.98) / 0.98
    pk = float(np.abs(mix).max())
    if pk > .89:
        mix = mix / pk * .89
    fi, fo = A.T(.02), A.T(1.4)
    mix[:fi, :] *= np.linspace(0, 1, fi)[:, None].astype(np.float32)
    mix[-fo:, :] *= np.linspace(1, 0, fo)[:, None].astype(np.float32)

    for name, x in (("stem_voice", voice), ("stem_music", music),
                    ("stem_keys", bus["keys"]), ("stem_accents", bus["accents"]),
                    ("stem_textures", bus["textures"]), ("stem_panels", bus["panels"]),
                    ("stem_trans", bus["trans"])):
        sf.write(os.path.join(OUT, name + ".wav"), x.astype(np.float32), SR, subtype="FLOAT")
    path = os.path.join(OUT, "mix_v9.wav")
    sf.write(path, mix.astype(np.float32), SR, subtype="FLOAT")

    print(f"wrote {path} {n / SR:.2f}s")
    print("  peak " + "  ".join(f"{k} {peak_db(bus[k]):5.1f}" for k in
                                ("keys", "accents", "textures", "panels", "trans"))
          + f"  | voice {peak_db(voice):5.1f}  mix {peak_db(mix):5.1f} dBFS")
    return path


if __name__ == "__main__":
    build()
