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
photopeople.py              card manifest, atlas, contact shadows, facing maths
rig.py                      13-bone skeleton + linear-blend skinning of the card
motion.py                   gait / idle animation (IK legs, physical timing)
actors.py                   place a skinned card with the pose its plate was shot in
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

## Movement: the cards have a skeleton

A photo card used to be a rigid quad, so a standing figure could only breathe.
Now each card is a **subdivided mesh (18×40 quads) bound to a 13-bone
skeleton** — pelvis, spine, chest, neck, head, upper arm / forearm per side,
thigh / shin / foot per side — with linear-blend skinning, four influences per
vertex (`rig.py`). The vertices really move in world space, so the depth buffer,
the sun shadow test, the fire's point light, fog and mist all follow the body.

Three details make it read as weight rather than as wobble:

* **Two-bone leg IK.** Every leg is solved from the *foot*: the stance ankle is
  pinned to the ground and the hip height decides the knee bend. The sole is its
  own bone, counter-rotated so it stays flat (heel-strike → flat → toe-off), and
  the mesh is snapped so the lowest sole is exactly y = 0. Nothing skates.
* **Plate-aware bind poses** (`actors.py`). Each card is bound to the pose it
  was *photographed* in, and motion is applied as a delta from that. A plate
  whose arms already reach forward is never rotated forward twice — that was
  what turned an arm into a smear in the first test.
* **Garment weights.** Leg weight is handed back to the pelvis as the tunic
  rises (0.34–0.41 × height), so a stride swings the skirt as one piece instead
  of tearing it at the crotch.

`motion.py` then supplies the animation principles:

| function | what it does |
| --- | --- |
| `walk` | 60 % stance gait: planted feet, pelvis bob twice per stride, hip/shoulder counter-rotation, arms opposite the legs with elbow lag, head held level |
| `step` | one deliberate step: anticipation, push-off, foot arc, heel-strike, weight transfer onto the new front foot, settle |
| `stand` | breathing, weight transfer foot to foot, micro-settle — knees bend because the hips move, not because a sine wave says so |
| `watch` | a guard's scan: the head leads, the chest arrives ~0.11 s later, then it settles |
| `warm` | hands to the fire: rub, heave toward the heat, lean in |
| `curve` | scripted beats (a look, a flinch) as smooth time-keyed curves |

## Shots (first 10 s)

| time | shot | what you see | why it reads |
| --- | --- | --- | --- |
| 0–5 s | `shot_night` | the hunter walks in watching the tree line, plants one deliberate step, holds — then his head snaps to something out there; behind him the camp fire burns, a companion looks up at him, a bedroll lies in the grass | the step shows real weight transfer, and the snap gives the shot its "why": *someone keeps watch* |
| 5–10 s | `shot_fire` | the woman and the elder warm their hands at a fire whose two point lights flicker on them; she looks across the flames, he answers, a spark makes him flinch; slow orbit; sparks, fireflies | two people *reacting* to each other and to the fire, with the light moving over both |

Fireflies, embers, smoke, grass, boulders, ridges and the pine treeline are all
procedural geometry; the fire is fourteen lofted, tapering flame tongues.

## Render

```bash
python3 tools/make_photo_cards.py         # rebuild the atlas from photo/*.png
python3 tools/fix_cards.py                # drop backdrop streaks the matte kept
python3 tools/decontaminate.py            # bleed interior colour into the matte ring
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
* A rigged card can move its limbs, but it cannot reveal a side or back that was
  never photographed: beyond ±20° from the lens the silhouette is still one
  view. More plates per character are the next quality step.
* `tools/decontaminate.py` bleeds interior colour through the half-transparent
  matte ring. Without it every silhouette wore a pale halo (the studio sweep)
  once the figure started to move and the edge stopped sitting on a dark edge.
* `tools/fix_cards.py` removes a horizontal streak of studio backdrop that the
  matte kept in `woman_warm` (a floor reflection, 3 px of grey). Flat on a
  billboard it was invisible; skinned onto the legs it swung through the frame.
* The card shader cuts alpha below 0.34 and ramps to 1.0 by 0.89. A skinned
  card stretches its faintest edge texels, and those were blending as ghosts.
