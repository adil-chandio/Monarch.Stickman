# Monarch.Stickman — Audio Upgrade Research (v13 sound kit)

Research date: 2026-10-25 · scope: background music + sound effects for the
Law-series videos and everything after them · every claim below was **run in this
sandbox**, not copied from a README.

---

## 0. TL;DR — what actually gets us to the next level

| # | Upgrade | What it replaces | Status |
|---|---|---|---|
| 1 | **Real recorded instruments** via a SoundFont (`tinysoundfont` + GeneralUser GS) | `audio_v3.piano()` (additive tones) and `strings()` (detuned saws) | ✅ working, **605× realtime** |
| 2 | **VST-grade DSP** via `pedalboard` (Spotify, JUCE) — Convolution, Reverb, Compressor, BrickwallLimiter, LadderFilter, PitchShift | hand-rolled one-pole filters, `np.tanh` mastering | ✅ working |
| 3 | **Reference mastering** via `matchering` + true BS.1770 metering via `pyloudnorm` | peak normalisation | ✅ working, 10 s in 3.5 s |
| 4 | **Sound design by layering** (transient + body + knock + air + convolution tail) | one-shot synthesized blips | ✅ working, 0.02 s per hit |
| 5 | **CC0 orchestral sample library** (VCSL, 3.9 GB) | — | ⏸ ready to fetch when disk/time allows |
| 6 | **AI music / SFX generation** (ACE-Step 1.5, Stable Audio Open, AudioGen) | — | ❌ not on this box (no GPU) — see §8 |

The single biggest finding: **the current bed is 92 % of its energy below 120 Hz.**
That is why it read as "rumble / echo type irritating" no matter how the reverb
was set. A premium bed needs 20–40 % of its energy in 120 Hz–1.5 kHz, where phone
speakers actually live. Numbers in §9.

---

## 1. The constraint that decides everything

```
2 vCPU · 3 GB RAM · no GPU · 19 GB free disk · Python 3.11
```

This is the whole reason the answer is "samples + DSP", not "AI music model".
Diffusion/transformer audio models need 8–16 GB **VRAM**; on 2 CPU cores a single
11-second Stable Audio clip is minutes per step, and MusicGen-small would swap.
Any plan that depends on them is a plan that depends on a rented GPU.

Everything recommended in Tier 1 runs in milliseconds here.

---

## 2. What was tested, and the verdict

| Tool | Source | ★ | License | Install here | Verdict |
|---|---|---|---|---|---|
| `pedalboard` | spotify/pedalboard | 6.4k | GPL-3.0 | 12 s, no deps problem | ✅ **adopt** — 26 JUCE-grade plugins |
| `tinysoundfont` | nwhitehead/tinysoundfont | ~ | MIT | wheel ok (`--no-deps`; it only wants `pyaudio` for realtime) | ✅ **adopt** for instruments |
| GeneralUser GS (31 MB SF2) | ad-si/GeneralUser fork | 14 | free for music use | download+load 0.09 s | ✅ **adopt** |
| `pyloudnorm` | csteinmetz1/pyloudnorm | 784 | MIT | ok | ✅ adopt (BS.1770-4 meter) |
| `matchering` | sergree/matchering | 2.7k | GPL-3.0 | ok | ✅ adopt **when a reference track is given** |
| VCSL (CC0 orchestral, 3.9 GB) | sgossner/VCSL | 356 | **CC0** | not fetched (size) | ⏸ best legal source, fetch on demand |
| OpenGM24 (per-note MP3, 200 MB) | designerzen/Open-GeneralMIDI-SoundFont | 3 | CC-BY / CC-BY-SA (FluidR3, Musyng, FatBoy) | downloaded, unpacked | ⏸ useful for full-bandwidth single notes |
| `sfizz` / `FluidSynth` | sfztools, FluidSynth | 2522 | BSD-2 / LGPL | ❌ no system lib, no root, no apt | ✗ skip — needs a C++ build |
| `py-meltysynth` | sinshu/py-meltysynth | 29 | — | ❌ not on PyPI | ✗ skip (pure-python, slow anyway) |
| `dawdreamer` | DBraun/DawDreamer | 1.3k | GPL-3.0 | PyPI wheel exists | ⏸ only if we ever host **VST3 plugins**; no plugins here |
| ACE-Step 1.5 | ace-step/ACE-Step-1.5 | 14k | MIT | — | ❌ needs GPU (§8) |
| Stable Audio Open / tools | Stability-AI/stable-audio-tools | 3.9k | MIT | — | ❌ needs GPU |
| AudioCraft (MusicGen/AudioGen) | facebookresearch/audiocraft | 23.8k | MIT | — | ❌ needs GPU |
| `freesound-python` | API client | — | — | ok | ⏸ needs an API key (free) — good for real foley later |

---

## 3. Pillar 1 — real instruments (`premium_audio.Instruments`)

`audio_v3.piano()` is an additive model: it can be in tune, but it cannot sound
like a recording, because there is no rosin, no hammer noise, no body resonance.
A SoundFont is a recording.

**Measured here**

```
soundfont load          0.09 s          (31 MB GeneralUser.sf2, kept out of git)
render 12 s of chords   0.02 s          = 605× realtime
master chain            0.43 s
one impact designed     0.02 s
```

**What makes it sound played instead of sequenced** (all in `Instruments.chord`):
velocity spread ±7, micro-timing ±9 ms, per-note length variation ±0.15 s, and
one instrument group per pan position (groups are panned, not individual notes).

### Traps found the hard way (each one cost a debugging round)

1. **`tinysoundfont.Synth(gain=..., samplerate=...)` — the first positional
   argument is `gain`, not the sample rate.** `Synth(48000)` sets gain = 48000 and
   every render comes out `inf`/`NaN`. This single line made the whole SoundFont
   path look broken.
2. **`generate()` returns interleaved `float32`, not `int16`.** Reading it as
   int16 turns music into full-scale noise. (`nbytes_simple / (samples*2) == 4`.)
3. A GM font is **band-limited**: GeneralUser GS has almost nothing above 4 kHz,
   so a shelf at 6 kHz does nothing. Brightness must come from a brighter preset
   (`piano_bright`, `strings`), a second octave, or a fuller library (VCSL /
   OpenGM24), never from EQ.

### License note

GeneralUser GS: *"You may use GeneralUser GS without restriction for your own
music creation, private or commercial"* — fine for our videos; the author cannot
guarantee the provenance of every embedded sample, so do **not** redistribute the
.sf2 itself (hence `/tmp` cache, git-ignored).
VCSL is **CC0** — that is the clean one if we ever need to ship assets.

---

## 4. Pillar 2 — effects (`pedalboard`)

Available without any external plugin: `Convolution`, `Reverb`, `Chorus`,
`Phaser`, `Delay`, `Compressor`, `BrickwallLimiter`, `Clipping`, `Distortion`,
`LadderFilter`, `HighpassFilter`, `LowpassFilter`, `PeakFilter`, `LowShelfFilter`,
`HighShelfFilter`, `NoiseGate`, `PitchShift`, `Gain`, `Bitcrush`, `IIRFilter`.

That is a full mixing desk in one import. It replaces every one-pole filter in
`audio_v3.py` with a proper biquad, and gives us **convolution with a real IR** —
the one thing the whole project was missing for SFX tails.

### Traps

- **`pedalboard.Limiter` is a maximiser, not a limiter.** It applies automatic
  makeup gain (a 0.5-peak sine comes out at 0.86). On a sub-heavy bed it pushed
  0–60 Hz from **64 % → 95 %** of the spectrum. Use
  `BrickwallLimiter(ceiling_db=..., release_ms=80, lookahead_ms=4, true_peak=True)`
  — transparent, verified sample-exact on a tone.
- The call signature is `board(input, sample_rate)`. Passing only the array raises
  a confusing "incompatible function arguments" error naming all the plugins.
- Input must be **C-contiguous float32**; `y * gain` and `.T` views are rejected.
  `run()` in `premium_audio.py` re-wraps every call.
- `Convolution(np_array_ir, ...)` also requires `sample_rate=` when the IR is an
  array.
- `Reverb(dry_level=.94, wet_level=.06)` still raised the bed by **+5.5 dB** RMS —
  always re-measure the level after a reverb, never trust the knobs.

---

## 5. Pillar 3 — mastering that is measured, not guessed

`pyloudnorm` (ITU-R BS.1770-4) gives the real integrated loudness, gated, so
silence does not drag the number down. The master loop in `premium_audio.master()`
is: **EQ → gain to target LUFS → true-peak ceiling → repeat until it converges**
(4 passes, 0.43 s for a minute of audio).

`matchering` goes further: give it a **reference track** and it matches spectral
balance, RMS and peak of our mix to that track. Verified end-to-end here:
10 s of audio in **3.5 s**, output −14.4 LUFS / −1.99 dBFS peak.

> To use it we need 2–3 tracks whose *sound* you like. Drop the links/names and
> the next build can be matched to them instead of to a number.

**Loudness targets that actually matter for YouTube Shorts:** −14 LUFS
integrated, −1.0 dBTP true peak. Our v12 already hits −14.7 / −1.0, so the
*mastering* was never the problem — the **mix** was.

---

## 6. Pillar 4 — how a premium SFX is actually built

The current kit is one-shots: a noise burst with an envelope. A designed hit is
**five layers**, each with its own job (`premium_audio.impact`):

| layer | content | why |
|---|---|---|
| transient | 6–11 ms of saturated noise, HP 2 kHz | the "hit" the ear locks onto |
| sub | pitch-dropping sine 120→40 Hz | the weight you feel |
| knock | BP 180–900 Hz, 60 ms | wood/metal character |
| air | BP 1.2–6 kHz, 30 ms | survives a phone speaker |
| tail | **convolution** with a synthetic IR (decaying noise + 4 early taps) | space, without a reverb wash |

`whoosh()` = band-split noise with a low→high sweep, a sin² envelope, a
**stereo pan sweep**, and a short convolution tail at 22 % wet.
`marker()` = 3-partial tonal ping for scene changes (no melody).

**Measurement lesson:** band-share on a whole file is useless for transients. The
same impact measures *99 % sub-bass* over 1.4 s and *full spectrum* (4 % above
8 kHz) in its first 10 ms. Measure transients on the **first 10–100 ms**.

---

## 7. Free libraries worth having (GitHub)

| Library | Size | License | Use |
|---|---|---|---|
| **VCSL** `sgossner/VCSL` | 3.9 GB | **CC0** | real orchestral: Aerophones, Chordophones, Membranophones, Idiophones, Electrophones — the upgrade path for strings/brass/percussion |
| **GeneralUser GS** `ad-si/GeneralUser` | 31 MB | free for music | 128 GM instruments in one file, loads in 90 ms |
| **OpenGM24** `designerzen/Open-GeneralMIDI-SoundFont` | 200 MB | CC-BY / CC-BY-SA | chromatic per-note MP3s, full bandwidth — good for a handful of hero instruments |
| **Meadowlark factory library** | small | CC0 | CC0 presets/samples |
| `wle8300/uifx` | 75 KB | MIT | *not* samples — WebAudio UI synth; checked, not useful for us |

Real foley (cloth, paper, room tone) is **not** on GitHub in usable form; that is
Freesound (API, free key) or the Sonniss GDC bundles. Both are opt-in later.

---

## 8. AI generation — what it would buy, and why not yet

| Model | Repo | What it gives | Reality on 2 vCPU / 3 GB |
|---|---|---|---|
| **ACE-Step 1.5** | ace-step/ACE-Step-1.5 (14k★, MIT) | full songs from a text prompt + lyrics, local | needs a GPU; CPU offload = hours per clip |
| **Stable Audio Open** | Stability-AI/stable-audio-tools | text→SFX and text→loops, 47 s | 8 GB+ VRAM |
| **AudioGen / MusicGen** | facebookresearch/audiocraft | text→SFX, text→music | 8 GB VRAM (small: 2 GB, but RAM-tight) |
| **YuE2** | multimodal-art-projection/YuE | songs with vocals | GPU |
| **Magenta RT** | magenta/magenta | realtime style transfer | TPU/GPU |

Verdict: **not now, but it is the real endgame** for bespoke BGM and for
"this specific sound" foley. Two honest options when we want it:

1. **Rent a GPU by the minute** (Colab / RunPod / HF Inference): generate 10–15
   beds and 30 SFX in one session, commit the WAVs (few MB), keep the generator
   out of the repo. This is by far the cheapest route to "one of a kind" audio.
2. Stay 100 % procedural with tiers 1–4, which is already a large jump.

Recommendation: **finish the Tier-1 rebuild first**, then spend one GPU session
on a "signature" library (one 8-bar theme + 12 SFX) that every future video
reuses. That is how a channel gets a sound.

---

## 9. Measured A/B — same 12 s harmonic idea, old engine vs new

`python demo_v13_ab.py` → `v3out/ab_A_current.wav`, `v3out/ab_B_v13.wav`,
`v3out/ab_reel.wav` (A, 0.4 s gap, B).

| | A — current (`music_v12`) | B — v13 (SoundFont + pedalboard) |
|---|---|---|
| loudness | −14.0 LUFS | −14.0 LUFS |
| peak | −1.99 dBFS | −1.00 dBFS |
| 0–60 Hz | **28.4 %** | 5.9 % |
| 60–120 Hz | **63.9 %** | 11.0 % |
| 120–500 Hz | 6.6 % | 48.0 % |
| 500–1500 Hz | 1.2 % | 30.6 % |
| 1500–4000 Hz | 0.0 % | 4.4 % |
| 4–16 kHz | 0.0 % | 0.0 % |

**A is 92 % below 120 Hz.** That is the "rumble" the ear reads as echo/wash even
when the reverb is off. B moves the energy into the band where a phone speaker
and a human voice live.

---

## 10. Roadmap

**Tier 1 — v13 (next video, no new assets needed)**
1. Score on real instruments: piano + string ensemble, one chord per scene,
   no melody (§3 rules from v12 still apply — the arrangement, not the source,
   was the "irrelevant music" problem).
2. Mix by stem with peak/LUFS per stem; never by "feel".
3. Master through `premium_audio.master()`; verify with `pyloudnorm`.
4. Replace the SFX kit with `impact()` / `whoosh()` / `marker()` + convolution
   tails; one variant per event (different root, seed, wet).
5. Small brightness layer: a celesta or music-box octave only on the 3 biggest
   beats — the GM piano alone is dark.

**Tier 2 — asset upgrade**
6. Fetch VCSL (CC0) and use real string/brass/percussion samples for the
   signature theme; keep it in a git-ignored cache with a `fetch_*` script.

**Tier 3 — signature sound (one GPU session)**
7. Generate a 15–20 s theme + 12 SFX with ACE-Step 1.5 / Stable Audio Open, keep
   them as the channel's reusable library.

---

## 11. How to run it

```bash
# one-time: audio sandbox
python3 -m venv /tmp/venv
/tmp/venv/bin/pip install numpy scipy soundfile imageio-ffmpeg pedalboard pyloudnorm matchering
/tmp/venv/bin/pip install --no-deps tinysoundfont      # pyaudio is only for live playback

# A/B proof  (downloads GeneralUser.sf2 once, 31 MB, into /tmp/monarch_audio)
/tmp/venv/bin/python demo_v13_ab.py

# SFX proof
/tmp/venv/bin/python -c "import premium_audio as P, soundfile as sf, numpy as np; \
  sf.write('v3out/sfx.wav', np.vstack([P.impact(55), P.whoosh(.55), P.marker(880)]), 48000)"
```

Module map — `video_law1/premium_audio.py`:
`fetch_soundfont` · `Instruments` · `rms_db` / `fit_rms` / `fit_peak` ·
`master` · `lufs` · `spectral_balance` · `make_ir` · `convolve` · `impact` ·
`whoosh` · `marker`.

---

## Appendix — every bug that cost a round in this research

1. `Synth(48000)` → gain = 48000 → `inf`/`NaN` renders.
2. `generate()` is float32, read as int16 → noise.
3. `pedalboard.Limiter` = maximiser → sub-bass takeover.
4. `board(array)` without a sample rate → "incompatible arguments".
5. Non-contiguous / non-float32 arrays rejected by pedalboard.
6. `Convolution(array_ir)` needs `sample_rate=`.
7. Levelling a sparse piano by RMS put its peak at **+7.6 dBFS**; the limiter then
   removed 20 dB of it and the mix collapsed to its sustained component.
8. A sine's crest factor is ~1, so "−24 dBFS RMS" sub = a roar; level tonal
   elements by **peak**, beds by **LUFS**.
9. `Reverb` raised the bus +5.5 dB at 6 % wet.
10. Whole-file band-share is meaningless for transients — measure the first 10 ms.
