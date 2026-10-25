# How Ancient Humans Survived — 46 s · 9:16 · easy Urdnglish

A second film on the v13 sound engine, a completely new visual language.

## What it is

10 beats, 46.0 s, 1080×1920 @ 30 fps. Ancient-world palette (charcoal night,
ember, bone, cold moonlight) instead of the Law series' paper/blue. Procedural
art — cave mouth, flame, mammoth, stone, hide, sprout — plus the camera language
the Law videos earned: whip pans, punch blur (on the picture only), light leaks,
anamorphic streak, weave, exposure breathe, film grain.

Story (see `SCRIPT_ANCIENT.md` for the full table): 20,000 years ago → the daily
question → fire → warmth → stone tools → the group → hide and cave → language →
farming → *"hum wahi insaan hain, sirf tools badle"*.

## Sound

- **Score** `music_sh.py` — GeneralUser GS samples, D-minor family, one chord per
  scene, no melody. There is an arc: cold/sparse (1–2) → warm (3–4) → work pulse
  (5) → hunt peak (6) → settle (7–8) → hope (9) → resolve (10).
- **Effects** `sfx_sh.py` — 49 cues, each tied to a real animation trigger.
  New voices for this film: `roar` (mammoth), `cloth`, `crackle` (embers,
  deliberately sparse), `stone` (knapping), `crack` (lightning), `sprout`.
- **Mix** `audio_sh.py` — mastered to −14 LUFS / −1.5 dBFS WAV ceiling, so the
  AAC delivery measures −14.1 LUFS / −1.3 dBTP.

## Narration slot (one step, when you have the voice files)

The film is built so one `.wav` per beat drops straight in:

```
audio_sh/beat01.wav … beat10.wav      # 48 kHz, ≤ the beat length (see the script table)
python audio_sh.py                    # switches to voice-on-top automatically
```

The mix then applies the Law-series policy: voice on top, score 8 dB under it,
ducked by the voice envelope, effects pulled back. Cues stay frame-exact because
they are placed against the same beat map.

## QC (this build)

| | |
|---|---|
| duration | 46.00 s |
| video | 1080×1920, 30 fps, H.264 high, 1.9 Mb/s |
| audio | AAC-LC 48 kHz stereo 252 kb/s |
| loudness | **−14.1 LUFS** |
| true peak | **−1.3 dBTP** (0 samples ≥ 0 dBFS) |
| LRA | 4.7 LU |
| spectrum | 0–120 Hz 36 % · 120–500 47 % · 500–1500 12 % · 1.5–8 k 3 % |
| silence | 4 windows of 100 ms under −45 dBFS (scene seams only) |
| render | 1380 frames, 4.2 fps, 10.5 MB silent → 12.4 MB with audio |

## Rebuild

```bash
./bootstrap.sh          # links the shared engine (video_law1) into this folder
python render_sh.py stills 2 12.5 26   # quick look
python render_sh.py full               # ~6 min -> out/survive_silent.mp4
python music_sh.py && python sfx_sh.py && python audio_sh.py
```
