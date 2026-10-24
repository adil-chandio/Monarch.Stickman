# Law 1 — v10: score-driven mix + cinema-layer picture

> **Current build:** `v3out/MonarchVoice_Law1_v10_CINEMATIC_9x16.mp4`
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
python render_v3.py full     # -> v3out/MonarchVoice_Law1_v10_CINEMATIC_9x16.mp4
```

Every layer is written as a stem (`stem_voice / stem_music / stem_music_ducked /
stem_keys / stem_accents`) so any single element can be soloed and judged.
Tuning lives in `audio_v10.CONFIG` and `music_v10.ENERGY`.
