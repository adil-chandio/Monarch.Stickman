# Law 1 — v10: score-driven mix + cinema-layer picture

> **Current build:** `v3out/MonarchVoice_Law1_v13_CINEMATIC_9x16.mp4` (v10 echo, v11 doubled voice, v12 synthetic-instrument builds retired)
> 63.33 s · 1080×1920 · 30 fps · H.264 High 5.1 Mb/s + AAC 260 k · **41 MB**
> **−13.9 LUFS / −1.0 dBTP / LRA 1.6** (ideal for YouTube/IG/Reels at −14)

### Verified on the exported file

| check | result |
|---|---|
| clipping | none — peak −0.99 dBFS, zero samples at/over 0 dBFS |
| typewriter sync | median **2.7 ms**, 100 % within 40 ms |
| accents on screen | 12 distinct hits above −32 dBFS in 63 s (the quiet ones are staged below by design) |
| music continuity | music under the voice in **every** second (median −27.8 dBFS, one 1 s dip to −46) |
| SFX density | 22 accents, 0.35 /s (v9: 2.4 /s) |
| render time | 0.45 s/frame after caching masks → ~15 min full render |

## Why v9 still felt noisy — and what the numbers said

v9 fired **152** sound events and quietly made the *pops* the loudest thing behind
the voice:

| v9 measurement | value | consequence |
|---|---|---|
| SFX layer audible (peak > −40 dBFS) | **83 % of the runtime** | a near-constant tick behind every line |
| music RMS under voice | −5.1 dB *after* ducking, −15 dB before | the bed never carried the mood |
| events | 40 panel pops + 89 keys + 16 pill pops + 7 flashes + 10 punches … | no silence, no contrast |

Irritation was not one bad sound — it was **density without dynamics**.

## The v10 audio policy (enforced in code, not by taste)

1. **Music carries the mood.** `music_v10.py` is a real score: sub, pad, felt piano
   motif, cello, heartbeat pulse, bell, air bed, and section swells. Its RMS sits
   **5 dB under the voice** and it is ducked by the voice's own envelope
   (−42 % at full speech). Arrangement dynamics across the 10 scenes: **8.8 dB**
   (−22.9 dBFS in the bright section → −31.7 dBFS in the shock).
2. **The caption bar gets nothing.** 40 cue changes, zero sounds. Its word
   animations are visual only — the narration *is* the event.
3. **SFX only on focal points, with a hard 0.55 s minimum gap.** Total: **22
   accents in 63 s = 0.35 /s** (v9: 2.4 /s). The list is printed on every build:
   the 5 scene cuts, the 3 big display words, the crown glint, the throne, the
   flame ignition, the scales, the arrest latch, 5 camera punches, the end card.
4. **Typing survives only where it is diegetic**: the real typewriter run
   (16 characters on screen) + the 3 strongest lower-text reveals, at −15 dBFS
   peak, and never within 0.25 s of an accent.
5. **SFX occupancy: 83 % → 40 %** of the runtime, and those 40 % are the moments
   the eye is already locked on something.

### Tone

The music is EQ-carved at **1.2–3.4 kHz (−42 %)**, which is exactly where speech
intelligibility lives, then given back weight at 55–120 Hz, warmth at 400–1000 Hz,
sheen at 1.8–7 kHz and air above 5 kHz. Band balance of the score:
`0–120 Hz 9 % · 120–500 Hz 52 % · 500–1.5 k 36 % · 1.5–4 k 2.4 % · 8 k+ 0.1 %` —
warm and wide where the voice is not.

Master chain: low tilt → high shelf → slow 1.8:1 glue → tape → soft ceiling,
landing at −1.0 dBFS with zero over-0 samples.

## The v10 picture layer

New passes, all inside the frame's post chain (`render_v3.py`):

| effect | when | why |
|---|---|---|
| **whip-pan smear** | `slide` / `whoosh` transitions | the cut now has direction and speed |
| **radial zoom blur** | `slam` transitions and every camera punch | weight on the hits without shaking the text |
| **chromatic split on the picture only** | punches, ≤3 px | film-lens tell; applied *before* the caption is drawn so text stays razor sharp |
| **vignette kick** | punches | darkens the frame edges on impact |
| **light leak** | first 0.85 s of every scene | warm entrance — the frame feels like it is being projected |
| **anamorphic streak** | always (stronger on the end card) | horizontal blue flare over highlights |
| **exposure breathe** | always, ±0.7 % at 1.7 Hz / 4.3 Hz | the frame stops looking like a static PNG |
| bloom (v3, kept) | end card | glow |

The frame at 29.6 s (the arrest punch) now shows real lens behaviour instead of a
flat blur: the motion is on the picture, the caption stays crisp.

## Rebuild

```bash
python render_v3.py events   # animation map (needed by the design pass)
python sfx_v9.py             # sound kit (unchanged from v9)
python music_v10.py          # the score           -> v3out/music_v10.wav
python audio_v10.py          # the mix             -> v3out/mix_v10.wav + stems
python render_v3.py full     # -> picture + mix (then remux, see the v11 section)
```

Every layer is written as a stem (`stem_voice / stem_music / stem_music_ducked /
stem_keys / stem_accents`) so any single element can be soloed and judged.
Tuning lives in `audio_v10.CONFIG` and `music_v10.ENERGY`.

## v11 — the "echo" fix (dry room)

The v10 score was rejected by ear: *"peeche bilawaja ka echo type irritating music
sound"*. It was not the notes — it was the space around them:

| | v10 (rejected) | v11 (dry room) |
|---|---|---|
| reverb IR | 1.6 s hall **+** 1.5 s plate | one 0.42 s room, decay 11.0, damp 3800 Hz |
| wet path | per-element send **and** a second bus pass | **one** pass, bus wet 0.30 → 0.15 |
| send gains | 0.18 – 0.85 | 0.02 – 0.13 |
| wet band | full range | HP 260 / LP 5200 (dark, sits behind) |
| constant noise | white-noise "air bed" ×0.055 + per-bar BP "husk" ×0.020 | **deleted** |
| tape hiss | 0.004 | 0.0 |
| piano tail | 1.9 s (notes pile up) | 1.35 s |
| stereo width | 0.26 (reads as echo on headphones) | 0.12 |
| **measured reverb** | ≈100 % of dry | **19 % of dry (−14.6 dB)** |

Music now sits **5 dB** under the voice (score target `MUSIC_UNDER_VOICE_DB=3.0`,
duck depth 0.34) instead of 7.5 dB, so the mood is audible without wash.

### v11 QC (`MonarchVoice_Law1_v11_CINEMATIC_9x16.mp4`, 42 MB, 63.32 s)

- −14.0 LUFS · −1.0 dBTP (stereo decode) · **0 clipped samples**
- mix RMS: voice −21.0 · music −26.0 · accents −38.1 · keys −49.5 dBFS
- spectrum: **8–16 kHz = 0.03 %** (no hiss bed), 0–120 Hz 17.5 %, 120–500 Hz 63.3 %
- picture untouched — v11 is a **remux** of the v10 video (`-c:v copy`), no re-render

```bash
python music_v10.py                      # dry-room score
python audio_v10.py                      # mix_v10.wav
ffmpeg -i <silent_picture>.mp4 -i v3out/mix_v10.wav \
       -map 0:v -c:v copy -map 1:a -c:a aac -b:a 256k -movflags +faststart -shortest \
       v3out/MonarchVoice_Law1_v11_CINEMATIC_9x16.mp4
```

## v12 — the mix that was actually broken (voice double + holes) and the bed cut to 3 layers

Two separate faults were reported after v11; both were real, and the first one
had nothing to do with music.

### 1. "voice over ke upper voice over" + "bilawaja gap" = a rebuild accident

`audio_v4/` is gitignored. After a sandbox reset it was recreated by converting
`audio/beat*.mp3` with ffmpeg — but those mp3s are the **untrimmed** TTS, and
every clip is longer than its scene slot:

| beat | raw clip | scene slot |
|---|---|---|
| 2 | **8.52 s** | 4.50 s → ran 4 s into beat 3 |
| 4 | 5.00 | 3.90 |
| 5 | 5.60 | 5.00 |
| 7 | 7.80 | 7.30 |
| 8 | 6.52 | 5.88 |
| 9 | 5.12 | 4.68 |

Placed at `b["start"]`, a clip that long **overlaps the next scene's narration**
(two voices at once) and the slots it does not reach stay empty (holes).
`tighten.py` is the only correct producer — it trims to speech, squeezes pauses
>0.34 s to 0.18 s, writes `audio_v4/` **and** regenerates `timeline_v4.py`.

Re-running it reproduced the committed `timeline_v4.py` **byte for byte**, so
the picture needed no re-render — every clip now fits its slot exactly:

- voice active **66.7 % → 75.8 %** of the runtime
- gaps ≥0.35 s: **13 → 11**, and all 11 are natural 0.36–0.40 s scene seams (plus the end card)
- `audio_v10.check_voice_clips()` now hard-fails the build if any clip length
  disagrees with its slot, and tells you to run `tighten.py`

### 2. "irritating bekar music" = the arrangement, not the level

v10 ran **8 layers** at 84 BPM — felt-piano motif, celesta, bell, cello
counter-line, heartbeat pulse, reverse swells. Under a voice-over that is a
*second performance*. `music_v12.py` keeps three things and drops the rest:

| | v10 | v12 |
|---|---|---|
| layers | 8 (piano motif, celesta, bell, cello, pulse, swells, sub, pad) | **3** (pad, sub, mark) |
| melody | continuous piano motif | **none** — one low note per scene change (10 total) |
| noise layers | air bed + husk | none |
| width | 0.12 | 0.08 |
| level under voice | 5 dB | **8 dB** (`MUSIC_UNDER`) |

Music is present in **100 %** of seconds (min −37.2, median −30.6 dBFS) but never
fights a word: it is a floor, not a tune.

### v12 QC (`MonarchVoice_Law1_v12_CINEMATIC_9x16.mp4`, 42 MB, 63.3 s)

- −14.7 LUFS · −1.0 dBTP · LRA 1.8 · **0 clipped samples**
- stems: voice −19.9 · music −30.0 · accents −38.1 · keys −49.5 dBFS
- picture: `-c:v copy` from v11 — no re-render, all sync intact

```bash
python tighten.py                                   # ONLY if audio_v4/ is missing
python music_v12.py                                 # -> v3out/music_v12.wav
python audio_v10.py                                 # -> v3out/mix_v12.wav (+ stems)
ffmpeg -i <picture>.mp4 -i v3out/mix_v12.wav -map 0:v -c:v copy -map 1:a \
       -c:a aac -b:a 256k -movflags +faststart -shortest out.mp4
```

`MUSIC_MODULE` selects the score (`music_v12` default, `music_v10` the old one),
`MUSIC_UNDER` the level under the voice, `MIX_NAME` the output stem name.

## v13 — the research applied: sampled instruments, designed SFX, measured master

Full research and license notes: `SOUND_KIT_RESEARCH.md`. This is the first build
that uses it.

| | v12 | v13 |
|---|---|---|
| score source | `audio_v3.piano()` additive tones + detuned saws | **GeneralUser GS samples** via TinySoundFont (605× realtime, 0.09 s load) |
| voicing | low pad | open voicing — root −12, third at pitch, fifth +12 |
| sheen | none (bed died at 4 kHz) | celesta on the biggest beats |
| energy below 120 Hz | **92 %** | **15.5 %** |
| effects | one-shot blips | layered `impact` / `whoosh` / `marker` + **convolution tails**, per-cue root/seed/pan |
| master | hand-rolled tilt + `np.tanh` | `pedalboard` EQ + `pyloudnorm` BS.1770 target + `BrickwallLimiter` true peak |

### v13 QC (`MonarchVoice_Law1_v13_CINEMATIC_9x16.mp4`, 42 MB, 63.3 s)

- **−14.1 LUFS · −1.3 dBTP · LRA 2.1 · 0 clipped samples**
- stems: voice −19.9 · score −30.2 · accents −36.6 · keys −49.8 dBFS (pre-master)
- **13 audible accent onsets**, each on a real animation event:
  0.31 punch · 6.46 cut · 11.30 cut · 25.32 flame · 25.78 big word · 29.51 arrest ·
  31.31 punch · 37.38 glint · 44.73 scales · 55.80 big word · 56.38 punch ·
  57.09 end bell · 59.63 sparkle
- narration unchanged (tightened clips, 75.8 % voiced, no doubled voice);
  picture is `-c:v copy` from v12 — no re-render

```bash
python music_v13.py     # sampled score   -> v3out/music_v13.wav
python sfx_v13.py       # designed accents -> v3out/sfx_v13.wav
python audio_v13.py     # mix + master    -> v3out/mix_v13.wav (+ stems)
ffmpeg -i <picture>.mp4 -i v3out/mix_v13.wav -map 0:v -c:v copy -map 1:a \
       -c:a aac -b:a 256k -movflags +faststart -shortest out.mp4
```

Env: `MUSIC_UNDER` (score level under the voice, default 8 dB), `TARGET_LUFS`
(−14.0), `CEILING_DB` (−1.5 — AAC adds ~0.2 dB of true-peak overshoot, so the
WAV is cut lower than the −1.0 delivery ceiling on purpose).
