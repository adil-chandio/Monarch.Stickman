#!/usr/bin/env python3
"""
audio_v13.py — the v13 mix: real-instrument score, designed SFX, measured master.

Changes from audio_v10/v12 (the mix policy that was signed off is unchanged):

    score     music_v13 (GeneralUser GS samples) instead of synthesized voices
    effects   sfx_v13 (layered impacts / whooshes / markers with convolution
              tails) instead of one-shot blips
    master    premium_audio.master — brickwall true-peak ceiling and a BS.1770
              loudness target measured with pyloudnorm, not a guessed gain

Still true, and deliberately so:
    * the score sits UNDER the voice (default 8 dB RMS) and is ducked by the
      voice's own envelope
    * accents never exceed ACCENT_PEAK and are spaced by MIN_GAP
    * typing exists only where it is diegetic
    * voice stays 100 % dry

Run: python audio_v13.py  ->  v3out/mix_v13.wav (+ stems)
"""
from __future__ import annotations

import os

import numpy as np
import soundfile as sf

import audio_v3 as A
import music_v13
import premium_audio as P
import sfx_v13
from audio_v10 import CONFIG, OUT, check_voice_clips, peak_db, stage
from timeline_v4 import TOTAL


def build() -> str:
    total = TOTAL + 0.25
    n = A.T(total)

    check_voice_clips()
    print("voice…");  voice, venv = A.build_voice(total)
    print("score…");  music = music_v13.build(total)
    print("design…")
    keys, accents, counts, log = sfx_v13.design(total)
    print("       " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"       designed accents: {len(log)} in {total:.0f}s")

    voice, music = voice[:n], music[:n]
    keys, accents = keys[:n], accents[:n]

    voice = stage(voice, -1.5)
    vr = A.rms_db(voice)

    # score: RMS under the voice, then ducked by the voice envelope
    music = music / max(np.abs(music).max(), 1e-9)
    music = music * 10 ** ((vr - CONFIG["MUSIC_UNDER_VOICE_DB"] - A.rms_db(music)) / 20)
    keys = stage(keys, CONFIG["KEY_PEAK"])
    accents = stage(accents, CONFIG["ACCENT_PEAK"])

    d = A.smooth(venv[:n], 220)
    d = np.clip(d / max(d.max(), 1e-9) * 2.4, 0, 1)
    music_d = music * (1 - CONFIG["DUCK_MUSIC"] * d)[:, None]
    accents_d = accents * (1 - CONFIG["DUCK_ACCENT"] * d)[:, None]

    mix = (voice + music_d + accents_d + keys).astype(np.float32)
    print(f"pre-master  voice {A.rms_db(voice):5.1f}  score {A.rms_db(music_d):5.1f}  "
          f"accents {A.rms_db(accents_d):5.1f}  keys {A.rms_db(keys):5.1f} dBFS")
    mix = P.master(mix, target_lufs=float(os.environ.get("TARGET_LUFS", "-14.0")),
                   ceiling_db=float(os.environ.get("CEILING_DB", "-1.5")))
    print(f"post-master {P.lufs(mix):5.1f} LUFS  peak {peak_db(mix):5.2f} dBFS")

    for name, x in (("stem_voice", voice), ("stem_music", music),
                    ("stem_music_ducked", music_d), ("stem_keys", keys),
                    ("stem_accents", accents_d)):
        sf.write(os.path.join(OUT, name + ".wav"), x.astype(np.float32),
                 A.SR, subtype="FLOAT")
    path = os.path.join(OUT, os.environ.get("MIX_NAME", "mix_v13.wav"))
    sf.write(path, mix.astype(np.float32), A.SR, subtype="FLOAT")
    print(f"wrote {path} {n / A.SR:.2f}s")
    return path


if __name__ == "__main__":
    build()
