# Law 1 — "Never Outshine the Master" · v3+ (cinematic, no-brand build)

> **v7 (current build — `v3out/MonarchVoice_Law1_v7_CINEMATIC_9x16.mp4`, 63.33 s)** — ✅ exported & verified
> - **Measured on the exported file:** −12.2 LUFS integrated, −1.0 dBTP true peak, LRA 2.1 LU,
>   1080×1920 / 30 fps / H.264 High @ 4.7 Mb/s + AAC 256 k stereo, 38 MB.
> - Spectral QC of the final mix: 6.1 % of energy below 120 Hz (phone speakers still hear
>   the body), 38.1 % in the 300–3000 Hz speech band, 2.9 % crack at 2–6 kHz.
> - No dead air: every one of the 63 one-second windows is above −22 dB RMS.
> - **Rebuild order matters** (this was missing before): `sfx_synth2.py` → `tighten.py`
>   (regenerates `audio_v4/beatNN.wav` + `timeline_v4.py`) → `render_v3.py full`.
>   The regenerated `timeline_v4.py` is byte-identical to the committed one, so the
>   narration timing in git is authoritative. `audio_v4/` is git-ignored because it is
>   fully derived from `audio_v2/`.
> - **The GitHub SFX pack is gone.** `sfx_pack.py` and `audio_v4/sfx_gh/` are
>   deleted; nothing from that library reaches the mix any more.
> - **All sound design is synthesised in numpy** by `sfx_synth2.py` — 76
>   one-shots, each built as *layers* the way a sound designer builds a hit:
>   saturated pitch-gliding sub + body knock + filtered-noise crack + FM ring +
>   tail rumble. Risers and whooshes are spectral sweeps (noise through a
>   bandpass whose centre slides, crossfaded segment by segment), bells and
>   dings are FM, the sparkle layer is stacked partials, and applause is layered
>   claps. Every sound is rendered to `audio_v4/sfx_py/` with its sync point.
> - **Phone-speaker presence.** A pure-sub hit is inaudible on a phone, so the
>   low family (slam / impact / boom / bass / rumble) gets an extra body knock,
>   crack and air layer plus a mid-band tilt. Measured spectra went from ~99 %
>   energy below 120 Hz to ~75 % with a real 2–6 kHz crack on top.
> - Voice still 100 % dry, music reverb 6 %, SFX 3 % of a 0.7 s IR. Voice leads
>   the music by 14.8 dB and the SFX by 12.0 dB in the 300–3 kHz speech band.
> - Master targets −12 LUFS / −1.0 dBTP (v3.0 build measured −12.1 LUFS, LRA 1.8 LU;
>   the exported v7 file measures −12.2 LUFS, LRA 2.1 LU). Picture unchanged from v6
>   (the hooded narrator, no branding), audio rebuilt and remuxed.

> **v6 (current build — `Law1_v6_CINEMATIC_9x16.mp4`, 63.33 s)**
> - **The white circle-face mascots are gone.** Every `char_happy/think/worried`
>   slot now shows the hooded narrator from the reference art
>   (`assets/host_*.png`, 3 poses cut out of the reference), with a soft contact
>   shadow and a pulsing glow on the eyes and smile. The bottom-of-frame message
>   strip from v5 is removed — the character stands *in* the scene, no boxes.
> - **Sound design is now a real library, not synthesised approximations.**
>   `sfx_pack.py` curates 120 one-shots from the CC0
>   [`wyzowl/sfx-kit`](https://github.com/wyzowl/sfx-kit) (48 kHz / 24-bit WAV) into
>   `audio_v4/sfx_gh/`. Each entry keeps its catalogue **sync point**, so a hit is
>   started so that its peak lands on the exact frame it belongs to instead of
>   "somewhere near".
> - **Music transitions de-echoed.** The section swells used to come from the SFX
>   library through the reverb send at 45 % wet — that was the audible "echo on
>   the music". They are now built from the bed itself (reverse + envelope) and
>   sent at 22 %.
> - **Stereo fix.** `lp/hp/bp` were calling `signal.lfilter(b, a, x)` on a 2-D
>   array, which scipy treats as N independent 1-D signals — the left and right
>   channels were filtered against their own past, breaking the image (the music
>   bed measured **8.9 dB louder on the right**; that is the "one ear gets more
>   music" the user heard on AirPods). All three filters now pass `axis=0`.
> - Voice still 100 % dry; music reverb 6 %, SFX 3 % of a 0.7 s IR. Voice leads
>   the music by 14.8 dB and the SFX by 18.3 dB in the 300–3 kHz speech band.
> - Rebuild the pack with `python sfx_pack.py` (downloads nothing — it reads
>   `/tmp/sfxkit/sfx-kit-main/sounds`, produced by
>   `curl -L https://codeload.github.com/wyzowl/sfx-kit/tar.gz/refs/heads/main`).

> **v4 (current build — `Law1_v4_CINEMATIC_9x16_FLOW.mp4`, 63.33 s)**
> - **Voice flow fixed:** `tighten.py` trims every clip to speech, squeezes internal
>   pauses > 0.34 s down to 0.18 s and regenerates `timeline_v4.py` with real
>   durations + sentence-accurate cue times. Dead air between lines: 72.6 s → 63.3 s.
> - **Echo removed everywhere:** music reverb 26 % → 6 % (shorter IR), SFX reverb
>   20 % → 4 %, voice 100 % dry. Nothing in the mix has a tail longer than ~1.6 s.
> - **Voice sits on top:** 170–430 Hz mud cut, +46 % presence at 2.2–5.2 kHz,
>   music 10 dB under the voice before ducking (12.9 dB in the 300–3k band after),
>   SFX peaks −7.5 dB. Master −14.4 LUFS / −1.0 dBTP.

72.57 s · 1080×1920 · 30 fps · H.264 CRF 18 + AAC 256 k · −13.6 LUFS / −2.5 dBTP

## What changed from v2

**Sound (the whole reason for v3)**
- v2's trap-style bed was replaced with a *cinematic orchestral cue* at 84 BPM (Am–F–C–G):
  sustained cello, two-octave string pad, felt piano motif, glass-bell sparkle,
  low "heartbeat" pulses for tension, taiko-ish low hits at section peaks.
  No hats, no claps, no 808 growl — none of the sounds that read as cheap.
- The 34 one-shot SFX used in the edit were **extracted from the reference packs**
  the user supplied (`assets_src/VID_20261011_*.mp4`) with `extract_sfx.py`:
  gap-based event detection → −50 dB edge trim → 3.2 s cap → spectral classification
  (click / impact / riser / downlifter / whoosh / tonal) → −3 dBFS normalise,
  4 ms fades, 48 kHz float WAV + `index.json`.
- Every extracted hit is then **polished before it is placed** (`audio_v3.polish_sfx`):
  the harsh 2.8–5.2 kHz band is subtracted, the top is darkened, the pitch is dropped
  slightly for weight, edges are softened. That is what turns raw pack sounds into
  smooth, "premium" accents instead of piercing ones.
- Placement is editorial, not decorative: a boom on the hook, a riser into the title,
  a slam on the jail, sparse ticks in the quote, one big hit on the end card —
  and *nothing* during the lines that need the voice alone.
- Voice chain: HPF 88 Hz → presence 2.2–4.8 k (+34 %) → air 8 k (+18 %) →
  de-esser → compressor. **The voice is 100 % dry** — the short plate reverb that
  v3.0 put on every beat read as an echo/slapback on phone speakers, so it was removed.
- Ducking: music −52 %, SFX −30 % under the voice; voice peak −1.5 dBFS,
  music ≈ 9.5 dB under the voice before ducking, SFX peaks ≈ 4 dB under the voice.
- Master: tape saturation → glue compression → soft limiter → −13.6 LUFS, −2.5 dBTP.

**Picture**
- **All branding removed** — no crown logo, no "MONARCHVOICE", no handle pill,
  no beat tick marks, no "LAW 01 / 48" chip. Only a 3 px progress hairline remains.
- Impact punches: the camera kicks +2–4 % on every designed SFX hit, synced frame-exactly.
- Light sweep across the frame on every beat entry; bloom on the end card;
  brief chromatic aberration on impacts; sub-pixel film gate weave.
- Captions: per-word rise + fade animation, the newest word pops and tilts,
  keywords render in gold with a sweeping gold underline (no more beige stickers).
  Gold accent bar grows on the panel's left edge.
- End card: brand pill replaced with the closing line "WAQT — aur bhi nahi hai."

## Files

| file | purpose |
|---|---|
| `extract_sfx.py` | cuts one-shots out of the reference packs → `audio_v3/sfx_raw/` |
| `audio_v3.py` | instruments, score, SFX editorial layer, voice chain, mixdown → `v3out/mix_v3.wav` |
| `timeline_v3.py` | 10 beats, Urdnglish cues, keyword lists |
| `render_v3.py` | scenes, camera, captions, cinematic post, mp4 encode |
| `audio_v3/sfx_raw/index.json` | kind / duration / spectral features for all 34 hits |

## Rebuild

```bash
python sfx_synth2.py      # 76 synthesized one-shots -> audio_v4/sfx_py/ (+ index.json)
python tighten.py         # narration trim/pause-squeeze -> audio_v4/beatNN.wav + timeline_v4.py
python render_v3.py full  # frames -> v3out/video_v7_silent.mp4 + mix -> v3out/MonarchVoice_Law1_v7_CINEMATIC_9x16.mp4
```

`python audio_v3.py` on its own rebuilds only `v3out/mix_v3.wav` (+ stems) — handy for
iterating on the mix without re-rendering 1900 frames. `extract_sfx.py` is legacy (v3,
reference-pack SFX) and is no longer part of the v7 chain.

`render_v3.py stills 0.8 30 66` renders single frames; `render_v3.py timeline` prints the beat map.
