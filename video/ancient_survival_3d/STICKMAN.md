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

---

# v3 — the 2.5D pass (`stick25d.py`)

The 3D-raster stickman was rejected: capsule limbs and joint beads read as a
robot, and a figure lit by its own shader never sat in the plate. This pass
throws the rasteriser away and does what a pre-viz reel actually does.

```
layer 0   the photographic set, split into two parallax planes
layer 1   flat stick figures (circle head, spine, shoulder bar, 4 limbs)
layer 2   fire flicker, embers, ground fog, grain, vignette
```

The drawing is flat, but its joints are solved in 3D by the same rig and then
projected, so the stride foreshortens when he turns — the 2.5D contract.

## Figure construction

`build_points()` folds the rig's bone anchors into stick joints. Raw anchors
gave a V-shaped neck and a hip line hanging off one side; the derived set is:

* spine `hip → shoulder_mid`, neck `shoulder_mid → head_base`, head ball seated **on** the neck (centre = neck + dir·0.86r)
* shoulder bar `shoulder_l ↔ shoulder_r`, arms `shoulder → elbow → wrist`
* legs `hip → knee → ankle`, feet `ankle → toe` with a forced outward splay so
  they never collapse to a point when he walks at the lens
* in near-profile poses the bar is clamped to a minimum half-span (0.045 m) and
  the **whole arm slides out with it** — clamping the shoulder alone makes the
  upper arms slope back in and the figure grows a collar
* painter sort far→near, near side thicker and brighter; fire-side segments get
  a warm tint proportional to 1/d²

## Timing

Unchanged from v2: five shots, **exactly 2.0 s each**, 48 frames @ 24 fps.

| # | t | shot | action |
|---|---|---|---|
| 1 | 0.0–2.0 | WIDE | stands alone in the tree line |
| 2 | 2.0–4.0 | CLOSE | head turns toward a sound |
| 3 | 4.0–6.0 | TRACK | walks across frame, camera trucks |
| 4 | 6.0–8.0 | FIRE | two figures flank the pit, fire glow on them |
| 5 | 8.0–10.0 | GROUP | three on their feet, camera creeps in |

## Render

```
python3 stick25d.py --start 0 --end 60 --segment _build/s25_0000.mp4   # x4, then concat
```

Do **not** run four segments in parallel — each frame holds a 1620×2880 float
buffer and four at once gets OOM-killed (it happened to segment 1).

Output: `video/Ancient_Survival_Stickman25D_10s.mp4` (1080×1920, 24 fps, AAC).
