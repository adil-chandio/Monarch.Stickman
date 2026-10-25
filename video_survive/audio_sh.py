#!/usr/bin/env python3
"""
audio_sh.py — final mix for "How Ancient Humans Survived".

Two modes:

  no narration   (default) music bed + designed effects, mastered to -14 LUFS.
                 The film is written so the on-screen text carries the story.
  narration      drop `audio_sh/beat01.wav … beat10.wav` (one per beat) and the
                 mix switches to the Law-series policy automatically: voice on
                 top, score 8 dB underneath, ducked by the voice envelope, and
                 the effects pulled back by DUCK_ACCENT.

Frame-accurate: each narration file is placed at its beat start, so a cue that
lands on the animation also lands under the right line.

Run: python audio_sh.py -> out/mix_sh.wav
"""
from __future__ import annotations

import glob
import os

import numpy as np
import soundfile as sf

import audio_v3 as A
import music_sh
import premium_audio as P
import sfx_sh
from timeline_sh import BEATS, TOTAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
VOICE_DIR = os.path.join(ROOT, "audio_sh")
SR = A.SR


def load_voice(total: float) -> tuple[np.ndarray, np.ndarray] | None:
    files = sorted(glob.glob(os.path.join(VOICE_DIR, "beat*.wav")))
    if len(files) != len(BEATS):
        return None
    n = A.T(total)
    v = np.zeros((n, 2), dtype=np.float32)
    env = np.zeros(n, dtype=np.float32)
    for b, f in zip(BEATS, files):
        x, sr = sf.read(f, dtype="float32", always_2d=True)
        if sr != SR:
            raise SystemExit(f"{f} is {sr} Hz — convert to 48 kHz first")
        dur = len(x) / SR
        if dur > b["dur"] + .05:
            print(f"  ! {os.path.basename(f)} is {dur:.2f}s but the slot is "
                  f"{b['dur']:.2f}s — it will run over the next scene")
        st = A.T(b["start"])
        en = min(n, st + len(x))
        v[st:en] += x[:en - st]
        env[st:en] = np.maximum(env[st:en], np.abs(x[:en - st]).max(axis=1))
    return v, env


def build() -> str:
    total = TOTAL
    n = A.T(total)
    music = music_sh.build(total)[:n]
    fx = sfx_sh.build(total)[:n]

    voice_env = load_voice(total)
    if voice_env is None:
        # ---- no narration: the score is the bed, the effects sit on top
        music = P.fit_rms(music, -21.0)
        fx = P.fit_rms(fx, -31.0)
        mix = (music + fx).astype(np.float32)
        print(f"music {A.rms_db(music):5.1f}  fx {A.rms_db(fx):5.1f} dBFS  (no narration)")
    else:
        v, env = voice_env
        v = v / max(float(np.abs(v).max()), 1e-9) * 10 ** (-1.5 / 20)
        vr = A.rms_db(v)
        music = music / max(float(np.abs(music).max()), 1e-9)
        music *= 10 ** ((vr - 8.0 - A.rms_db(music)) / 20)
        d = A.smooth(env, 220)
        d = np.clip(d / max(d.max(), 1e-9) * 2.4, 0, 1)
        music_d = music * (1 - .34 * d)[:, None]
        fx_d = fx * (1 - .30 * d)[:, None]
        mix = (v + music_d + fx_d).astype(np.float32)
        print(f"voice {A.rms_db(v):5.1f}  music {A.rms_db(music_d):5.1f}  "
              f"fx {A.rms_db(fx_d):5.1f} dBFS  (narrated)")

    mix = P.master(mix, target_lufs=-14.0, ceiling_db=-1.5)
    path = os.path.join(OUT, "mix_sh.wav")
    sf.write(path, mix, SR, subtype="FLOAT")
    print(f"wrote {path}  {len(mix)/SR:.2f}s  {P.lufs(mix):.1f} LUFS  "
          f"peak {20*np.log10(np.abs(mix).max()):.2f} dBFS")
    print("  " + " ".join(f"{k}:{val:4.1f}%" for k, val in P.spectral_balance(mix).items()))
    return path


if __name__ == "__main__":
    build()
