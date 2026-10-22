# Photoreal humans, true 3D scene

The reel's cast is no longer procedural capsules. The people are
**AI-generated photoreal studio plates** that are cut out, packed into an atlas
and drawn as **3D geometry inside the same procedural world** — same camera,
depth buffer, sun shadow map, fire point-light, fog, ground mist, tone mapping,
bloom, depth of field and grain as the terrain, trees and fire.

```
photo/*.png                 AI-generated studio plates (full-body, plain sweep)
  -> tools/make_photo_cards.py     matte -> defringe -> crop -> atlas + manifest
  -> photo/people_atlas.png        one RGBA atlas
  -> photo/people.json             metres-per-card, atlas rects, uv bounds
photopeople.py              card -> quad mesh (material 21) in a Builder
raster.c                    set_texture() + photo-card pixel path
scenes_photo.py             the shots: who stands where, what the camera does
render_10s.py               frame driver -> 1080x1920 -> ffmpeg
```

## How a photo becomes part of the 3D scene

1. **Matte.** `tools/make_photo_cards.py` fits a quadratic surface to the studio
   sweep (it is never a flat colour: it vignettes and carries a floor shadow),
   thresholds the colour distance from that model, adds a neutral-darkening test
   so cast shadows go too, floods the backdrop from the border, keeps the
   largest connected blob, erodes a pixel of fringe, feathers, and unmixes the
   backdrop tint off the edge pixels (`C = a·F + (1-a)·B`).
2. **Depth, not decals.** The card is a quad at a real world position with a
   real world size (`height_m` from the manifest), so it is depth sorted against
   the rocks, occluded by the fire logs, fogged and misted by distance, and lit
   by the sun *and* the camp fire's point light. `raster.c` treats material ids
   ≥ 20 as textured: bilinear sample, sRGB→linear, alpha test, alpha blend,
   then the same shadow / fog / mist / grade path as everything else.
3. **Rounded bodies.** A flat card lights like a board. The quad's vertex
   colours carry the card-local `u` in the blue channel, and the shader swings
   the shading normal around the body axis by `(u-0.5)·2.7 rad`, so the light
   rolls off toward the silhouette and the figure reads as a cylinder.
4. **Facing.** A single-view card collapses to a sliver when turned sideways, so
   every figure is placed with `photopeople.yaw_for(pos, camera, aim=...)`: face
   the lens, lean toward what the character is looking at (the fire, a
   companion), clamped to ±0.22–0.42 rad.

## Shots (first 10 s)

| time | shot | what you see | why it reads |
| --- | --- | --- | --- |
| 0–5 s | `shot_night` | the hunter stands watch, spear planted, breath fogging; behind him the camp fire burns, a companion is awake, a bedroll lies in the grass | the subject is lit by the camp fire's warm rim against a cold moonlit world: *someone keeps watch* |
| 5–10 s | `shot_fire` | the woman and the elder warm their hands at a fire whose two point lights flicker on them; slow orbit; sparks, fireflies | bodies, hands and faces are readable, and the light on them changes with the flames |

Fireflies, embers, smoke, grass, boulders, ridges and the pine treeline are all
procedural geometry; the fire is fourteen lofted, tapering flame tongues.

## Render

```bash
python3 tools/make_photo_cards.py         # rebuild the atlas from photo/*.png
gcc -O2 -march=native -shared -fPIC -o libraster.so raster.c -lm
python3 render_10s.py                    # whole clip -> _build/p10_*.mp4
python3 render_10s.py --start 0 --end 120 --segment _build/a.mp4   # slice
```

Output: `video/Ancient_Survival_3D_10s_Photoreal.mp4` (1080×1920, 24 fps,
10.0 s, AAC 48 kHz).

## Notes / limits

* One card = one view. Rotating a character past ~20° from the lens is not
  possible without a second plate of the same person; the shots are staged so
  that never happens.
* Cards do not cast shadow-map shadows (a flat plane would cast a slab); they
  get a soft graded contact shadow instead, plus real point-light shading.
* No walk cycle yet: a photoreal walking figure needs a matched AI plate per
  pose. `photo/hunter_walk.png` exists and is already packed, so the walk shot
  can be enabled later by placing cards per stride.
