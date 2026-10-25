# How Ancient Humans Survived — **our own art** (46 s · 9:16)

A film about the first humans, built from our own character sheets — not from
the Law 1 drawings. The **style language** (cream paper, ink outlines, blue
caption bar, red stamps, gold keywords) is shared, because that is the channel;
every character, animal, tool, flame and landscape is drawn for this film.

    sheet/01…08_*.png   →  assets_an/<set>/<NN>_<slug>.png  →  out/AncientHumans_OwnArt_9x16.mp4

## 1. The character sheets (the art department)

Eight generated sheets, one per family of things the story needs, in a single
locked style: flat vector, thick clean ink outline, paper-cut/sticker look, pure
white background, no text, limited palette.

| # | sheet | items |
|---|---|---|
| 01 | `01_host_character_sheet` | the hooded narrator: idle, point, think, cheer |
| 02 | `02_ancient_human_poses` | idle, two hunters, crouch, kneel, kneel-2, triumph |
| 03 | `03_fire_elements` | candle, camp fire, bonfire, embers, sparks, torch, fire ring, smoke curl, flame core |
| 04 | `04_stone_tools_props` | stone hammer, spear, knife, clay pot, bow, flint block, hide vest, bone tool, basket, amphora |
| 05 | `05_environment` | cave mouth, cave inside, hills, forest, field, night, river, plain |
| 06 | `06_animals` | mammoth, sabertooth, wolf, deer, vulture, boar, rabbit |
| 07 | `07_effects_ui_shapes` | panel, outline, stamp frame, ribbon, curved arrow, arrow, burst ring, speed lines, dust, sparkle, streaks, spotlight |
| 08 | `08_small_props_nature` | wheat, sprout, seed handful, small rocks, boulder, moon, sun, stars, smoke, droplets, footprints, firewood |

Palette held across all eight: charcoal `#18181C`, red `#C6182C`, gold `#C99B2C`,
blue `#1385E5`, tan `#C9A27B`, stone `#B4AC9C`, green `#6E9E63`, cream `#F6F1E6`.

## 2. Sheets → sprites (`extract_sheet.py`)

Cutting a white-background sheet naively ("everything near-white is background")
deletes the *inside* of the art — tusks, flame cores, the cream of the sun — and
every sprite comes out milky. The pipeline therefore:

1. **flood-fills the background from the border** (`binary_propagation` of the
   near-white mask), so only white *reachable from outside* is removed;
2. **eats the anti-aliased rim** (2 px of near-white just inside the edge),
   which is what left a pale halo around sprites on the paper background;
3. **merges pieces of one drawing** — a multi-stroke glyph (speed lines, a
   sparkle cluster, a handful of seeds) arrives as several components, so boxes
   within 26 px are unioned (`JOIN` per sheet; 0 for sheets whose items sit
   close together, e.g. the pose sheet);
4. **labels** each group, drops anything under 1200 px, trims with 6 px padding
   and writes `assets_an/<set>/<NN>_<name>.png` in reading order (rows grouped by
   `|Δy| < 90`, then left→right), plus `manifest.json` and `_contact.png`.

Result: **69 sprites**, every one inspected on the contact sheet.

## 3. Staging (`render_an2.py`)

A small scene language instead of one-off coordinates:

| helper | job |
|---|---|
| `put_s(name, cx/bottom or cx/cy, h/w, rot, flip, opacity, silhouette, tint)` | stage one sprite, cached scaling, paper shadow |
| `host_stage(pose)` | the narrator from sheet 01, with a warm halo |
| `flame_stage(cx, ground, h, t)` | a fire built from three flame sprites at different phases, so no two frames repeat |
| `env_band(name, bottom, feather)` | environment art as a full-width band whose top and sides melt into the paper (bare, it reads as a pasted rectangle) |
| `speedlines` / `dust` / `own_bubble` / `warn_badge` | drawn effects — no borrowed art |
| `GL / HERO / MID / SMALL` | the ground line (y=1700) and the three size steps every scene obeys |

Ten beats, ten scene functions (`s1…s10`), then `CAM` (per-beat push/pull),
`SHAKE` (impact kicks), `GRADE` (warm/cool tint + contrast), `PARTS` (dust,
embers, sparks, confetti) and `compose()` which adds the transitions, caption bar,
light sweep, leak, chroma/zoom blur on impacts, weave, exposure breathe and grain.

Story beats and caption text are unchanged from the approved script, so the
existing 46.00 s mix (`out/mix_an.wav`) still fits frame-for-frame:

| # | caption (Urdnglish) | picture |
|---|---|---|
| 1 | 20,000 SAAL PEHLE → na ghar, na kapde | stars, moon, hills, cave, one human, narrator walks in |
| 2 | Har subah ek hi sawal — zinda raho ge ya nahi? | sabertooth closes in, danger badge, `ZINDA?` |
| 3 | Phir bijli ne AAG di → DOST bana liya | lightning, fire ignites, narrator cheers |
| 4 | Aag = GARMI / ROSHNI / darinde DOOR | ring of people around the fire, wolf in the dark |
| 5 | Pathar toda → HATHIYAR bana → shikaar aasan | four strikes on the boulder, each on its sound cue, spear appears |
| 6 | Akela KAMZOR → JHUND mein KHATARNAAK | hunters + mammoth, `JHUND`, `KHATARNAAK` |
| 7 | Janwar ki KHAAL → jaket → gufa ghar | vest drops onto the figure, cave, `GUFA = GHAR` |
| 8 | sabse bada hathiyaar? ZUBAAN | speech bubble, warm rings, `ZUBAAN` |
| 9 | Beej boya → bhookh kam hui | sun, falling seeds, arrow, sprout, wheat field |
| 10 | hum wahi insaan hain, SIRF TOOLS BADLE HAIN | night, silhouette with a phone glow, follow pill |

## 4. Sound

Unchanged from the approved mix: `out/mix_an.wav` (46.00 s, −14.1 LUFS, −1.3 dBTP),
built by `audio_an.py` from the self-made `music_sh.wav` + `sfx_sh.wav` kit. The
strike frames in beat 5 (`0.75 / 1.55 / 2.35 / 3.15 s`) are the same ones the SFX
were cut to, and every beat boundary is still `0.30 / 4.60 / 9.20 / 14.30 / 18.60 /
23.10 / 27.80 / 32.20 / 36.70 / 41.20`.

## 5. Rebuild

```bash
python extract_sheet.py        # sheets  -> 69 sprites (+ _contact.png)
python render_an2.py stills 2.6 7.5 13.0   # spot-check frames
python render_an2.py full      # out/ancient2_silent.mp4  (1380 frames, 1080x1920, 30 fps)
ffmpeg -y -i out/ancient2_silent.mp4 -i out/mix_an.wav -map 0:v -c:v copy \
       -map 1:a -c:a aac -b:a 256k -ar 48000 -movflags +faststart -shortest \
       out/AncientHumans_OwnArt_9x16.mp4
```

`video_law1/` is not imported for art any more; only the shared engine helpers
(`vlib.paper_bg`, `vlib.stamp`, `vlib.pill`, `put_text_scaled`, `flash`,
`apply_vignette`, `apply_grain`, the caption/optics constants) are reused, which
is exactly the channel's style layer.

## 6. QC checklist

- 46.00 s, 1080×1920, 30 fps, 1380 frames, `yuv420p`, faststart.
- Audio: −14.1 LUFS integrated, true peak −1.3 dBTP, no echo wash, no hiss.
- Stills reviewed at every beat; no floating props, no duplicated sprites, no
  pasted rectangle edges, no white halo around cut-outs.
