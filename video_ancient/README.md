# How Ancient Humans Survived — **Law 1 style** (46 s · 9:16)

Same visual grammar as `video_law1` (Law 1), new subject. This is the version to
compare with the Law 1 video, not the dark "prehistoric" cut in `video_survive/`.

## The style, kept identical

| element | how it is done here |
|---|---|
| background | cream paper texture (`vlib.paper_bg`) + ink line art |
| palette | ink / blue / red / gold (`vlib` constants, no new colours) |
| top caption | **the same blue bar and word-by-word reveal** — `render_v3.draw_caption` imported as-is, gold keywords, underline, panel pop-in |
| host character | the same hooded host (`host_worried` / `host_happy`), now at 690 px in the corner |
| big typography | Playfair 900 for display words, Inter 900 for stamps |
| stamps / pills | `vlib.stamp` + `vlib.pill` (`ZINDA?`, `JHUND`, `ZUBAAN`, `JACKET`, `BEEJ`) |
| icon set | the channel's own `icon_warning` slams in on the threat beat |
| camera | per-beat push/pull, punch blur **on the picture only**, whip transitions |
| post | light sweep, leak, anamorphic streak, weave, exposure breathe, grain |
| progress | the same hairline progress line at the bottom |

New drawings only where the story needs them: rock massif + cave mouth, paper
flame, ink mammoth, wheat, sprout, stone pile, sun.

## Story (10 beats, 46.0 s)

| # | caption | visual |
|---|---|---|
| 1 | 20,000 SAAL PEHLE → na ghar, na kapde | moon, hills, cave, lone figure, red slam word |
| 2 | Har subah… ek hi sawal — zinda rahoge ya nahi? | warning icon slam + predator eyes |
| 3 | Phir bijli ne AAG di → DOST bana liya | lightning strike, fire ignites, host happy |
| 4 | Aag = GARMI / ROSHNI / darinde DOOR | fire circle, three figures |
| 5 | Pathar toda → HATHIYAR bana → shikaar aasan | stone strikes with sparks on the cue frames |
| 6 | Akela KAMZOR → JHUND mein KHATARNAAK | hunters + mammoth, `JHUND` stamp |
| 7 | Janwar ki KHAAL → jaket → gufa ghar | cloak drops on the figure, cave, sleeping pair |
| 8 | sabse bada hathiyaar? ZUBAAN | speech bubble + rings, `ZUBAAN` stamp |
| 9 | Beej boya → khana khud ugaya | sun, wheat, sprout, falling seeds |
| 10 | hum wahi insaan hain, SIRF TOOLS BADLE | night city, phone glow, follow pill |

## Sound

Reuses the mix already built for this topic, so the timings line up exactly:
`video_survive/music_sh.py` (D-minor score, sampled instruments) +
`video_survive/sfx_sh.py` (**49 designed cues**, each on a real animation
trigger) → `audio_an.py` masters to −14 LUFS.

The cue frames were re-checked against this edit: the four stone strikes land on
0.75 / 1.55 / 2.35 / 3.15 s into beat 5, which is exactly where the sparks are
drawn here.

## Narration slot

`audio_sh/beat01.wav … beat10.wav` (48 kHz) → `python audio_an.py` switches to
voice-on-top automatically (score 8 dB under, ducked). Full lines in
`video_survive/SCRIPT_ANCIENT.md`.

## QC (this build)

| | |
|---|---|
| duration | 46.00 s · 1080×1920 · 30 fps · H.264 high |
| loudness | **−14.1 LUFS** · **−1.3 dBTP** · LRA 4.7 |
| audio | AAC-LC 48 kHz stereo 252 kb/s |
| render | 1380 frames, 3.7 fps |
| file | 24.8 MB |

## Rebuild

```bash
./bootstrap.sh
python render_an.py stills 1 12 26 44    # quick look
python render_an.py full                 # ~6 min
python audio_an.py                       # needs video_survive/out/music_sh.wav + sfx_sh.wav
```
