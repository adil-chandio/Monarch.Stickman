# Law 1 — v9: the picture drives the sound

> **Current build:** `v3out/MonarchVoice_Law1_v9_CINEMATIC_9x16.mp4`
> 63.33 s · 1080×1920 · 30 fps · H.264 High + AAC 256 k · **−12.2 LUFS / −1.0 dBTP / LRA 2.3**

## The idea

v8 placed sounds by hand on a beaten timeline. v9 does not guess: the renderer
is **instrumented**, and every element it draws is recorded. The sound design is
then generated from that event map, so every hit lands on the frame where
something actually happens.

```
render_v3.py events      ->  v3out/anim_events.json
                             135 element events (images, pills, text, hosts, particles, halos,
                             flashes, glitches, transitions)
                             + 10 camera punches + 40 caption cues
audio_v9.py              ->  v3out/mix_v9.wav            (keys / accents / textures / panels / transitions)
```

The camera punches are not guessed either — they are read from the renderer's own
`IMPACTS` table, so a zoom-punch and its sub hit are the same frame.

## What gets a sound, and which sound

| what happens on screen | sound |
|---|---|
| caption bar changes (40×) | soft **panel pop** — *deliberately not typing*: the bar is on screen the whole video, and typing there was the thing that felt busy |
| real typewriter run at 13.44 s (`N │ Ni │ Nic │ … Nicolas Fouquet`) | one **keystroke per character**, 16 of them, spacebar and Return included |
| small lower caption appears (8×) | a 3–6 key **typed burst that lands exactly on the word** |
| medium word appears (6×) | 3 keys + space, landing on the word |
| big display word `LAW ONE`, `MASTER`, `INSECURE`, `BEIZZATI` … (9×) | **stamp** + air — a 100 px word is struck, not typed |
| icon / art arriving (7×) | `icon_warning` → metal tick · `icon_crown` → glint · `icon_flame` → fire ignition · `icon_scale` → swaying metal · `king_throne` → big materialise |
| pills / badges (16×) | UI pop (bigger pill → deeper pop, pitched per hit) |
| particles in the scene | spark → shimmer · dust → air · embers → crackling bed · confetti → flutter |
| strong halos | a single soft breath |
| host character appears (8×) | cloth |
| flashes (7 groups) | air burst, strength-scaled |
| glitch on the end card (2 groups) | 3-slice digital stutter |
| scene cuts (5×) | whoosh family chosen by transition type (`punch` → huge whoosh) |
| camera punches (10×) | sub hit — `impact_hard` / `impact` / soft, by punch strength |
| three biggest moments | risers into them (5.55 s, 28.65 s, 54.55 s) |

## Variety, so nothing repeats

* 37 families × 2–5 rendered variants = **104 one-shots**, all synthesized in
  `sfx_v9.py` (no samples).
* the same variant is never played twice in a row;
* every hit gets ±3 % pitch, ±1.5 dB level and pan taken from its x position on
  screen (left/right of frame 540);
* pitched elements are quantised to A-minor pentatonic (A C D E G), so unrelated
  hits still feel like one palette.

## Measured on the export

| check | result |
|---|---|
| accent sync vs event map | **median 0.4 ms**, 94 % inside 25 ms (a frame is 33 ms) |
| typewriter sync | **median 3.7 ms**, 100 % inside 40 ms |
| typing level vs voice | ~12 dB under the voice during a burst (was −24 dB in the first v9 pass) |
| phone-speaker retention (400 Hz HP) | keys −2.7 dB, textures −0.8, panels −5.2, accents −4.6, voice −4.9 |
| clipping | none — stereo peak −1.02 dBFS, zero over-0 samples |
| dead air | none — every one-second window above −22.5 dB RMS |
| master | −12.2 LUFS, −1.0 dBTP, LRA 2.3 |

## Knobs

`audio_v9.CONFIG`: `KEYS_PEAK`, `ACCENT_PEAK`, `TEXTURE_PEAK`, `PANEL_PEAK`,
`TRANS_PEAK`, `DUCK_*`, `KEYS_ON`, `TEXTURES_ON`, `REVERB`, `KEYS_REVERB`.
The mapping tables are plain dicts (`IMAGE_MAP`, `TRANS_MAP`) and the per-event
logic is one `design()` function, so re-placing or removing a single sound is a
one-line edit.

## Rebuild

```bash
python render_v3.py events   # ~6 min, writes v3out/anim_events.json (committed)
python sfx_v9.py             # 104 one-shots -> audio_v9/sfx/   (~2 s)
python audio_v9.py           # -> v3out/mix_v9.wav + stems      (~55 s)
python render_v3.py full     # -> full render with v9 audio
```

To swap only the audio on an existing render (fast, what was done here):

```bash
ffmpeg -i old.mp4 -i v3out/mix_v9.wav -map 0:v:0 -map 1:a:0 \
       -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart out.mp4
```
