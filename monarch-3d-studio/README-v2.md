# MONARCHVOICE // NEO PROTOCOL

**20 second, Full HD (1920×1080), 30 fps 3D stickman short film with an original score — rendered entirely inside the sandbox (no GPU, no Blender).**

## Deliverable
| | |
|---|---|
| File | `MonarchVoice-NEO-PROTOCOL-1080p.mp4` |
| Resolution | 1920 × 1080 (16:9) |
| Frame rate | 30 fps / 600 frames |
| Audio | AAC-LC 192 kb/s stereo, 44.1 kHz (original score) |
| Video | H.264 High @ 4.3 Mb/s, yuv420p, faststart |
| Runtime | 00:20.00 |
| Size | ~11 MB |

## Watch
* `film.html` — premium film landing page (player + chapter timeline + downloads)
* `MonarchVoice-NEO-PROTOCOL-1080p.mp4` — the film
* `index.html` — interactive real-time WebGL studio (Three.js, MediaRecorder export)

## Chapters
| Time | Act |
|---|---|
| 0.0 – 3.4 s | Cold open · MONARCHVOICE STUDIOS → NEO PROTOCOL title |
| 3.4 – 6.0 s | 01 The City · neon skyline, rain, hero entry + energy charge |
| 6.0 – 9.5 s | 02 Arrival · villain drops in, taiko standoff |
| 9.5 – 11.2 s | 03 Clash · first exchange, shockwaves |
| 11.2 – 13.6 s | 04 Pressure · combo, kick, counter |
| 13.6 – 15.4 s | 05 Fall · hero knocked down |
| 15.4 – 17.2 s | 06 Finish · charged dash + the finishing blow |
| 17.2 – 19.0 s | 07 Monarch · victory pose |
| 19.0 – 20.0 s | End card · logo reveal |

## Engine (v2)
`generate_video_v2.py` — CPU raster renderer, ~0.5 s/frame.
* foot-snapped FK skeleton rig (18 joints, 16 hand-authored poses, eased interpolation)
* tapered cape cloth with rim light + wet-floor reflection
* 3-layer parallax skyline with lit windows, neon signs, haze, moon
* wet street with perspective grid, puddle smears, contact shadows
* keyframed camera rig (zoom + screen-space ground solve), handheld drift, impact shake
* FX: afterimages, radial speed streaks, impact rings, shockwaves, sparks, debris, embers, rain
* post: bloom, chromatic aberration, teal/amber grade, vignette, film grain, per-hit glow flashes
* HUD: REC, timecode, chapter titles, progress bar, cinematic titles, end-card logo

`generate_audio_v2.py` — pure-numpy score: pads, sub drones, taiko kicks, snares, hats,
risers, whooshes, impacts, FFT convolution reverb, sidechain ducking, master limiter.

## Re-render
```bash
python3 generate_audio_v2.py     # -> soundtrack_v2.wav (20.0 s)
python3 generate_video_v2.py     # -> MonarchVoice-NEO-PROTOCOL-1080p.mp4
```
Requires: numpy, opencv-python-headless, imageio-ffmpeg.
