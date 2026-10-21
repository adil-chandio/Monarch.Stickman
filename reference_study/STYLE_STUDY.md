# REFERENCE STUDY — kaomei/stickman-video-director

Source: Google Drive folder `1HtGXQ4U_JqczsSJ5tn4a379S6XpgQe6G`
(12 style previews + 1 screen recording of the GitHub README).
Upstream repo: https://github.com/kaomei/stickman-video-director (MIT)

## What the folder actually contains

| File | Res | FPS | Dur |
|---|---|---|---|
| light-theme-demo.mp4 | 1280×720 | 24 | 10 s |
| dark-theme-demo.mp4 | 1280×720 | 24 | 10 s |
| style-2a-demo.mp4 | 1920×1080 | 24 | 10 s |
| style-2b-demo.mp4 | 1920×1080 | 24 | 10 s |
| style-3-demo.mp4 | 1920×1080 | 30 | 30 s |
| style-3-community-fire.mp4 | 1280×720 | 24 | 30 s |
| style-4-cozy-cafe.mp4 | 1280×720 | 24 | 10 s |
| style-4-cozy-station.mp4 | 1280×720 | 24 | 10 s |
| style-5-japan.mp4 | 1280×720 | 30 | 30 s |
| style-5-egypt.mp4 | 1280×720 | 24 | 10 s |
| Screen_Recording_20261020_214840.mp4 | 720×1600 | ~16 | 82 s | (README scroll — no unique content) |

Key production facts taken from the repo's own skill contract:

* **Clip unit = 10 seconds.** 30 s → 3 clips, 60 s → 6 clips.
* Narration density ≈ **20–25 English words per 10 s** (60–75 words for 30 s).
* Every clip = **3 timed beats** ([0–3 s], [3–7 s], [7–10 s]) and **≥4 visual devices**,
  with a visual change every 2–3 seconds. Character must never be idle.
* 5-stage narrative arc: Golden Hook → Disrupt Assumptions → Insider Secrets →
  Ultimate Truth → Elevation + comment question.
* Formats: 16:9 (lateral staging, tracking) or 9:16 (depth, vertical reveals).
* Optional 2–5 word text overlays are added in post, never inside generation prompts.

## The five styles (what we must match)

### Style 1 — Classic Minimalist (light / dark)
Pure flat white (or pure black) canvas, **no gradient / texture / 3D depth**.
Hollow-circle head, single-line limbs, uniform medium stroke, no clothing.
Max **3 saturated accent colours**, and accents live on props/graphics only.
Best for: dense explainers, logic, psychology, numbers.

### Style 2A — Modern Studio Tech
Pure white high-key studio, faint light-grey perspective floor grid, soft contact
shadows, floating **cyan/electric-blue glass UI**. Character = red beanie (no pom-pom)
+ yellow T-shirt + black stick limbs. Negative rules: no circuit textures, no
sci-fi wall panels, no cracked concrete.

### Style 2B — Cinematic Story
Same beanie character dropped into **full-colour environments** with cinematic
lighting, fog, god-rays, depth layering (canyon, dusk ridge, summit).

### Style 3 — Prehistoric / Dark Comedy
Rough hand-drawn outline, white-filled expressive heads, dark stick limbs, animal
hide, earthy palette, fire glow, comic timing + reaction beats.

### Style 4 — Cozy Storytelling  ★ closest to "story" content
Full-colour flat 2D cartoon locations, gentle atmospheric light, **white-filled round
head with simple expressive face (dot eyes + eyebrow + small mouth) and white torso
"shirt" shape**, dark navy stick limbs. Camera grammar: **wide establishing → close-up
on emotion → tracking shot**, and a *new recognizable location every 10 s*.
Palettes track emotion (teal = anxiety, warm = comfort).

### Style 5 — Historical Cartoon
Same head grammar as Style 4 but **thicker bold outlines + cel shading**, era costume
(kimono, robes), painterly historical background, black oval eyes.

## Measured visual grammar (what makes it look "reference-accurate")

1. **Character construction**
   - head = white/near-white filled circle, 2.5–4 px dark outline, radius ≈ 0.34 of body height
   - face = 2 dot eyes + short eyebrows + 3-point mouth; eyes lead the facing direction
   - torso = filled shirt polygon (not a line), shoulders rounded
   - limbs = dark **capsule strokes** with rounded joints, feet = small ovals
   - line colour is dark navy (#1B2432-ish), never pure black on colour backgrounds
2. **Background construction**
   - 3–4 depth layers: sky gradient → far buildings (desaturated) → mid props → foreground
   - flat cel shading: one base + one shadow tone per object, no photorealism
   - soft contact shadow under every character
   - props do the storytelling (mug, phone, book, train, lantern, ledger)
3. **Motion**
   - 24 fps feel, snappy pose-to-pose with 2-frame holds, squash on impacts
   - blink + brow + mouth changes carry emotion in close-ups
   - camera: slow push-in, lateral tracking, hard cuts on beat
4. **Sound**
   - one continuous BGM bed, SFX on every action, narr-voice only (no speech bubbles,
     no on-screen dialogue text)

## What we will reproduce (engine plan)

| Reference element | Our implementation |
|---|---|
| White filled head + face | new `draw_char()` — filled circle, outline, dot eyes, brows, mouth, blink |
| Shirt torso + capsule limbs | filled shirt polygon + capsule strokes with rounded joints |
| Flat cartoon environments | procedural cel-shaded scene builders (cafe, station, tech studio, canyon) |
| 10 s clip structure, 3 beats | scene/camera timeline per 10 s block with hard cuts |
| 24 fps reference cadence | 24 fps master (cinematic) with 30 fps option |
| Wide → close → tracking grammar | camera rig: push-in, tracking, close-up cut |
| 20–25 words / 10 s VO | narration script + optional TTS voice track |
| BGM + SFX per beat | procedural score (already have the synth kit) |

## Gap vs our earlier films

Earlier v1–v3 used **glowing neon stick figures** (Style 1-ish but with heavy bloom).
The reference look is **flat, warm, character-first cartoon** — filled heads with
faces, colourful environments, story beats, close-ups. That is the upgrade path.
