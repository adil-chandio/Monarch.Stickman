# Law 1 — "Never Outshine the Master" · v3 (cinematic, no-brand build)

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
  de-esser → compressor.
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
python extract_sfx.py     # optional – regenerates the SFX library from assets_src/
python audio_v3.py        # -> v3out/mix_v3.wav (+ stems)
python render_v3.py full  # -> v3out/Law1_v3_CINEMATIC_9x16.mp4
```

`render_v3.py stills 0.8 30 66` renders single frames; `render_v3.py timeline` prints the beat map.
