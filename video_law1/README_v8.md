# Law 1 — v8: new sound design, all synthesized, typing-locked

> **Current build:** `v3out/MonarchVoice_Law1_v8_CINEMATIC_9x16.mp4`
> 63.33 s · 1080×1920 · 30 fps · H.264 High + AAC 256 k · **−12.4 LUFS / −1.0 dBTP / LRA 2.3** · 38 MB

## What this version is

v7's sound design is **gone**. The sampled library (`sfx_pack.py`, `extract_sfx.py`,
`audio_v4/sfx_gh`, `audio_v4/sfx_py`) and the numpy re-creation of it
(`sfx_synth2.py`, `audio_v3.build_sfx`) have been deleted. Everything under the
voice now comes from **`sfx_v8.py`**, written from scratch for this video.

What was kept: the narration, the cinematic music bed, and the voice chain
(HPF 88 Hz → presence → de-esser → compressor, 100 % dry). Those were the parts
that already worked.

## The typing

The renderer reveals caption word *i* at `cue_t + i × 0.095 s`
(`render_v3.draw_caption`). `audio_v8.typing_layer()` walks the very same cue
list and drops a keystroke on **every single word reveal** — 144 of them.

That is what makes it feel typed rather than "SFX added afterwards":

| detail | how it is done |
|---|---|
| a key is not one click | four layers: 2–7 kHz noise click (2–5 ms), 2–3 resonant case modes (150–400 Hz), a 450–900 Hz knock, and a *quieter upstroke* 55–85 ms later |
| it never repeats | 6 key profiles × 3–5 rendered variants × per-hit random gain (±10 %), pan (σ 0.16) and brightness |
| keywords land harder | words flagged in the timeline get the heavy keys and +18 % level |
| sentence ends | spacebar / return key on the last word of a cue |
| panel changes | soft UI pop as the blue bar lands |
| **verified** | keystrokes land **median 1.3 ms** from the frame they belong to (a frame is 33.3 ms) |
| **audible, not annoying** | a keystroke reads **+12.8 dB** above the bed in the 2.5–7 kHz band, and sits ~14 dB under the concurrent voice |

## Kit (61 one-shots, 21 families)

| family | design | used for |
|---|---|---|
| `key_soft/mid/hard/space/return/tick` | physical keystroke model (see above) | every caption word |
| `pop`, `pop_big` | pitch-glided sine + click, 85/130 ms — no cartoon boing | caption panel in, card in |
| `whoosh_soft/mid/hard` | decorrelated noise through a sliding band-pass | scene transitions |

| `riser`, `riser_short` | sliding noise band + rising detuned saw, crest at the cut | into the title / arrest / end card |
| `impact`, `impact_hard` | pitch-dropping sub + knock + **mid knock 200–1600 Hz** + crack + air | hook stop, jealousy, quote, arrest |
| `slam` | heavy knock + mid knock + paper + crack | RUK JAO, arrest, end card |
| `clank` | six inharmonic modes (512 Hz → 4.2 kHz) + hard strike | the iron latch, once |
| `bell`, `bell_low` | FM bell with decaying index | title, credit, end card |
| `sparkle` | six inharmonic partials, high-passed | "aha" moments |
| `swish` | band-passed noise, short | palace card, underline draw |

Phone-first mixing: each family is measured through a 400 Hz high-pass (a phone
speaker). Keystrokes lose 1.6–4.7 dB, pop/whoosh/clank/bell ≈ 0 dB, slam 9.7 dB,
and the sub impacts 20 dB — which is why they carry an extra mid knock.

## Accents are half of v7's

Transitions whoosh only on scene cuts; sub hits only on the hook, the jealousy,
the arrest and the quote; one metal latch; two bells. Nothing during the lines
that need the voice alone.

## Adjusting it

Everything lives in `audio_v8.CONFIG`:

```python
TYPING_GAIN=0.34        # base keystroke level
TYPING_KEY_GAIN=1.18    # extra weight on highlighted keywords
TYPING_PEAK_DBFS=-13.5  # absolute keystroke peak
TYPING_ON=True          # False = no typing at all
PANEL_POP_GAIN=0.16
ACCENT_GAIN=0.62
TRANSITION_GAIN=0.22
ACCENT_PEAK_DBFS=-8.0
SFX_REVERB=0.03         # accents only, typing stays dry
DUCK_SFX=0.18           # voice pushes SFX down by at most ~1.6 dB
MUSIC_UNDER_VOICE_DB=12.0
```

The per-beat accent editorial map is the `accent_layer()` function — one block
per beat, easy to re-place or delete a single hit.

## Rebuild

```bash
python sfx_v8.py       # 61 synthesized one-shots -> audio_v8/sfx/ (+ index.json)
python tighten.py      # narration prep -> audio_v4/beatNN.wav + timeline_v4.py
python audio_v8.py     # -> v3out/mix_v8.wav + stems (voice/music/typing/accents)
python render_v3.py full   # -> v3out/MonarchVoice_Law1_v8_CINEMATIC_9x16.mp4
```

`render_v3.py stills 12 31 58` renders single frames; `mix_v8.wav` and the four
stems are written to `v3out/` (git-ignored) for inspection — listening to
`stem_typing.wav` alone is the fastest way to judge the typing.
