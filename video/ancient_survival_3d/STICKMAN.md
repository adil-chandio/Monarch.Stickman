# Stickman cut — 5 shots × 2.0 s

Style: `kaomei/stickman-video-director` **Style 1 (dark)** — black field, white
figure — with Style 3 (prehistoric) set dressing: a fire, a spear, a cold night.

This is not drawn: the figures come out of the **same skeleton and motion
module** as the photoreal cut (`rig.py`, `motion.py`), so the gait is IK-planted
and the weight transfers. The camera is a real 3D camera.

| # | time | shot | content |
|---|---|---|---|
| 1 | 0.0–2.0 | WIDE, 3/4 | the watch, slow push |
| 2 | 2.0–4.0 | CLOSE, 3/4 | head snaps to a sound |
| 3 | 4.0–6.0 | TRACK, profile | he walks across frame, camera trucks |
| 4 | 6.0–8.0 | FIRE | two of them warming hands, slow orbit |
| 5 | 8.0–10.0 | GROUP | all three, wide, camera rising |

**Every shot is exactly 2.0 s = 48 frames @ 24 fps.** Total 10.0 s.

## Drawing the figure

* limbs are emissive capsules with the stroke weight in `THICK` (skinning the
  photo card is a different code path; here the bones *are* the mesh)
* joints are beads, plus **clavicle and hip bars** — without them the figure
  reads as a bundle of sticks rather than a body
* head is a filled ball on the neck
* depth cue: the near-side limbs are 15% thicker than the far-side ones, which
  is what stops the 3/4 poses looking flat
* camera basis: person X → screen right, person Z → facing direction, matching
  `rig.build`. (Getting these swapped hides a walk's stride along the camera
  axis — it did, and the fix is in this file.)

## Framing

`frame_subject(target, height, frac, fov)` solves the camera distance from the
projection: `d = h / (2 tan(fov/2) frac)`. Every shot picks a fraction
(0.58–0.86) instead of an eyeballed position, so heads are never cropped.

Render: `bash /tmp/render_stick.sh` → `_build/stick.mp4` (~2.2 min, two halves),
then mux with `../ancient_survival/_build/final_mix.wav`.

Output: `video/Ancient_Survival_Stickman_10s.mp4` (1080×1920, 24 fps, AAC).
